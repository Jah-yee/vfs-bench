"""Run the pinned original Kubernetes fixture in an owned E2B sandbox."""
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from urllib.parse import urlparse

import yaml

from server.kubernetes_proxy import serve as authenticated_proxy
from server.kubernetes_template import receipt
from server.sandbox import Tunnel, sandbox

REPO = Path(__file__).resolve().parents[2]
UPSTREAM = REPO / 'submodule/Toolathlon'
TASKS = {
    'k8s-deployment-cleanup': ('cluster-cleanup', 'k8s_deployment_cleanup.sh'),
    'k8s-safety-audit': ('cluster-safety-audit', 'k8s_safety_audit.sh'),
    'k8s-mysql': ('cluster-mysql', 'k8s_mysql.sh'),
    'k8s-redis-helm-upgrade': ('cluster-redis-helm', 'init_redis_helm.sh'),
    'k8s-pr-preview-testing':
    ('cluster-pr-preview', 'k8s_pr_preview_testing.sh'),
}
BINARIES = REPO / 'server/kubernetes-binaries.json'


def original(path: str) -> bytes:
    return subprocess.check_output(
        ['git', '-C', str(UPSTREAM), 'show', f'HEAD:{path}'])


def original_paths(prefix: str) -> list[str]:
    return subprocess.check_output([
        'git', '-C',
        str(UPSTREAM), 'ls-tree', '-r', '--name-only', 'HEAD', prefix
    ],
                                   text=True).splitlines()


def command(box, line, timeout=180):
    result = box.commands.run(line, timeout=timeout)
    if result.exit_code != 0:
        raise RuntimeError(f'Kubernetes setup failed: {result.stderr[-1500:]}')
    return result


def workspace_config(task, workdir, private, filename):
    """Preserve the original preprocessor's kubeconfig visibility."""
    directory = Path(workdir) / 'k8s_configs'
    if task in {'k8s-mysql', 'k8s-safety-audit', 'k8s-pr-preview-testing'}:
        # Both pinned preprocess/main.py files remove this directory after
        # setup; their MCP server and grader use the task-directory backup.
        shutil.rmtree(directory, ignore_errors=True)
        return Path(private) / filename
    return directory / filename


@contextmanager
def serve(task: str, workdir: str):
    """Keep the original cluster alive through tools and grading."""
    if task not in TASKS:
        raise ValueError(f'No Kubernetes fixture setup for {task}')
    revision = subprocess.check_output(
        ['git', '-C', str(UPSTREAM), 'rev-parse', 'HEAD'], text=True).strip()
    template = receipt()
    assets = json.loads(BINARIES.read_text())
    ports_path = UPSTREAM / 'configs/ports_config.yaml'
    ports = ports_path.read_bytes() if ports_path.is_file() else None
    suffix = str((yaml.safe_load(ports) or {}).get('instance_suffix',
                                                   '')) if ports else ''
    cluster_name, setup_script = TASKS[task]
    cluster = cluster_name + suffix
    remote_config = f'/work/k8s_configs/{cluster}-config.yaml'
    with sandbox(template['template_id'], {
            'task': task,
            'toolathlon_revision': revision
    }) as box, ExitStack() as resources:
        print(f'e2b sandbox={box.sandbox_id}', flush=True)
        prefix = f'tasks/finalpool/{task}'
        paths = original_paths(prefix)
        files = [
            path for path in paths
            if any(f'/{part}/' in path
                   for part in ('scripts', 'k8s_resources', 'data',
                                'initial_workspace'))
        ]
        files.append('scripts/lib/kind_image_loader.sh')
        checks = {
            **{
                f'/usr/local/bin/{name}': digest
                for name, digest in assets['docker']['installed_sha256'].items(
                )
            },
            '/usr/local/bin/kind': assets['kind']['sha256'],
            '/usr/local/bin/kubectl': assets['kubectl-linux-amd64']['sha256'],
        }
        command(
            box, 'printf %s ' +
            shlex.quote(''.join(f'{digest}  {path}\n'
                                for path, digest in checks.items())) +
            ' | sha256sum -c -')
        hashes = {}
        if ports is not None:
            box.files.write('/opt/toolathlon/configs/ports_config.yaml',
                            ports,
                            user='root')
        for path in files:
            data = original(path)
            box.files.write('/opt/toolathlon/' + path, data, user='root')
            hashes[path] = hashlib.sha256(data).hexdigest()
        settings = original('configs/global_configs_example.py')
        hashes['configs/global_configs_example.py'] = hashlib.sha256(
            settings).hexdigest()
        box.files.write('/opt/toolathlon/configs/global_configs.py',
                        settings,
                        user='root')
        command(box, 'sudo python3 -m pip install --break-system-packages -q '
                'uv==0.8.22 addict==2.4.0 PyYAML==6.0.2',
                timeout=180)
        shared = None
        if task in {'k8s-mysql', 'k8s-pr-preview-testing'}:
            from server.shared_workspace import mounted, s3_config
            shared = s3_config(task, Path(workdir).name)
            if task == 'k8s-mysql':
                resources.enter_context(mounted(box, shared))
        command(box, 'sudo mkdir -p /work && sudo chown user:user /work')
        box.commands.run('sudo dockerd > /tmp/dockerd.log 2>&1',
                         background=True,
                         timeout=0)
        command(
            box, 'for i in $(seq 1 30); do sudo docker info >/dev/null 2>&1 '
            '&& exit 0; sleep 1; done; cat /tmp/dockerd.log; exit 1')
        for path in paths:
            marker = prefix + '/initial_workspace/'
            if path.startswith(marker):
                box.files.write('/work/' + path.removeprefix(marker),
                                original(path),
                                user='root')
        if task == 'k8s-redis-helm-upgrade':
            from server.mcp.setup_helm import install_remote
            install_remote(box)
        setup_args = (' start /work/config/redis-values.yaml /work'
                      if task == 'k8s-redis-helm-upgrade' else ' start /work')
        if task == 'k8s-pr-preview-testing':
            setup_args = ' 30123 start /work'
        print(f'Initializing original {task} fixture...', flush=True)
        setup = command(box,
                        'cd /opt/toolathlon && sudo -E bash ' +
                        shlex.quote(f'{prefix}/scripts/{setup_script}') +
                        setup_args,
                        timeout=900)
        if task == 'k8s-deployment-cleanup':
            # The upstream shell does not stop on every failed inner command.
            live = json.loads(
                command(
                    box,
                    'sudo kubectl --kubeconfig=' + shlex.quote(remote_config) +
                    ' get deployments --all-namespaces -o json').stdout)
            expected = [
                item for item in yaml.safe_load_all(
                    original(
                        f'{prefix}/k8s_resources/k8s_deployment_cleanup.yaml'))
                if item and item.get('kind') == 'Deployment'
            ]
            actual = {
                (item['metadata']['namespace'], item['metadata']['name']): item
                for item in live['items']
            }
            fixture_namespaces = {
                item['metadata']['namespace']
                for item in expected
            }
            if sum(ns in fixture_namespaces
                   for ns, _ in actual) != len(expected):
                raise RuntimeError(
                    'Original Kubernetes fixture has missing or extra '
                    'deployments')
            for item in expected:
                key = (item['metadata']['namespace'], item['metadata']['name'])
                found = actual[key]
                if (found['spec']['replicas'] != item['spec']['replicas']
                        or not found['metadata'].get(
                            'annotations',
                            {}).get('app-version-release-date')):
                    raise RuntimeError(
                        f'Original Kubernetes setup incomplete: {key}')
        else:
            command(
                box, 'sudo kubectl --kubeconfig=' +
                shlex.quote(remote_config) + ' get namespaces -o json')
        print(f'{task}: cluster initialized', flush=True)
        if shared is not None:
            if task == 'k8s-pr-preview-testing':
                from server.seed.browser import preview_source
                preview_source(box)
            from server.shared_workspace import remote_workspace
            with remote_workspace(
                    box,
                    shared,
                    workdir,
                    remote_config,
                    assets,
                    browser=task == 'k8s-pr-preview-testing',
                    shared_disk=task == 'k8s-pr-preview-testing') as remote:
                from server.shared_workspace import run
                images = json.loads(
                    run(
                        box, 'docker image inspect ' + ' '.join(
                            run(box, 'docker image ls -q --no-trunc').stdout.
                            split())).stdout)
                record = {
                    'sandbox_id':
                    box.sandbox_id,
                    'template':
                    template,
                    'binaries':
                    assets,
                    'images': [{
                        key: row[key]
                        for key in ('Id', 'RepoTags', 'RepoDigests')
                    } for row in images],
                    'toolathlon_revision':
                    revision,
                    'inputs_sha256':
                    hashes,
                    'ports_config_sha256':
                    hashlib.sha256(ports).hexdigest() if ports else None,
                    'instance_suffix':
                    suffix,
                    'transport':
                    ('native-e2b-with-ssh-workspace-and-s3-artifacts'
                     if remote.shared_disk else
                     'native-e2b-with-s3-fuse-and-ssh-stdio'),
                    'workspace': {
                        key: shared[key]
                        for key in ('bucket', 'region', 'key_prefix')
                    },
                }
                evidence = REPO / 'state/kubernetes'
                evidence.mkdir(parents=True, exist_ok=True)
                source_record = evidence / f'{box.sandbox_id}.json'
                source_record.write_text(json.dumps(record, indent=2) + '\n')
                (evidence / f'{box.sandbox_id}.log').write_text(setup.stdout +
                                                                setup.stderr)
                previous_record = os.environ.get('K8S_SOURCE_RECORD')
                os.environ['K8S_SOURCE_RECORD'] = str(source_record)
                try:
                    yield record
                finally:
                    remote.collect()
                    if previous_record is None:
                        os.environ.pop('K8S_SOURCE_RECORD', None)
                    else:
                        os.environ['K8S_SOURCE_RECORD'] = previous_record
            return
        captured = box.files.read(remote_config)
        config = yaml.safe_load(captured)
        endpoint = config['clusters'][0]['cluster']['server']
        port = urlparse(endpoint).port
        websocket = assets['websocat']
        command(
            box, 'curl -fsSL ' + shlex.quote(websocket['url']) +
            ' -o /tmp/websocat && printf %s ' +
            shlex.quote(websocket['sha256'] + '  /tmp/websocat\n') +
            ' | sha256sum -c - && chmod 755 /tmp/websocat')
        box.commands.run(
            f'/tmp/websocat -b --exit-on-eof '
            f'ws-l:0.0.0.0:8083 tcp:127.0.0.1:{port}',
            background=True,
            timeout=0)
        # Mutual TLS remains end-to-end inside the byte tunnel.
        tunnel = Tunnel(f'wss://{box.get_host(8083)}')
        keys = ('KUBECONFIG', 'KUBECONFIG_PATH', 'KUBECTL', 'PATH',
                'K8S_SOURCE_RECORD', 'KUBECTL_NATIVE', 'K8S_PROCESS_DIR',
                'HELM', 'HELM_NATIVE', 'HELM_FIXTURE_URL', 'HELM_CONFIG_HOME',
                'HELM_CACHE_HOME', 'HELM_DATA_HOME')
        previous = {key: os.environ.get(key) for key in keys}
        filename = f'{cluster}-config.yaml'
        backup = UPSTREAM / prefix / 'k8s_configs' / filename
        previous_backup = backup.read_bytes() if backup.is_file() else None
        previous_mode = backup.stat().st_mode if backup.is_file() else None
        connections = ExitStack()
        process_dir = Path(
            connections.enter_context(
                tempfile.TemporaryDirectory(prefix='toolathlon-kubernetes-')))
        target = workspace_config(task, workdir, process_dir, filename)
        launcher = process_dir / 'kubectl'
        shutil.copyfile(REPO / 'server/kubectl.sh', launcher)
        launcher.chmod(0o755)
        try:
            config['clusters'][0]['cluster'][
                'server'] = f'https://127.0.0.1:{tunnel.port}'
            binary = REPO / 'vendor/kubernetes-bin/kubectl'
            if not binary.is_file():
                raise FileNotFoundError(
                    'Run server/mcp/setup_kubernetes.py first')
            installed = json.loads(binary.with_name('source.json').read_text())
            if (installed not in assets.values() or hashlib.sha256(
                    binary.read_bytes()).hexdigest() != installed['sha256']):
                raise RuntimeError(
                    'Local kubectl differs from its pinned release')
            public_config = connections.enter_context(
                authenticated_proxy(config, binary))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(yaml.safe_dump(public_config))
            target.chmod(0o600)
            # Upstream writes both paths, and its grader prefers the backup.
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(target.read_bytes())
            backup.chmod(0o600)
            os.environ.update(KUBECONFIG=str(target),
                              KUBECONFIG_PATH=str(target),
                              KUBECTL=str(launcher),
                              KUBECTL_NATIVE=str(binary),
                              K8S_PROCESS_DIR=str(process_dir),
                              PATH=str(process_dir) + os.pathsep +
                              str(binary.parent) + os.pathsep +
                              os.environ['PATH'])
            if task == 'k8s-redis-helm-upgrade':
                from server.mcp.setup_helm import configure
                configure(process_dir, workdir, connections)
            for attempt in range(20):
                check = subprocess.run(
                    [str(binary), 'get', 'namespaces', '-o', 'json'],
                    capture_output=True,
                    text=True,
                    timeout=20)
                if check.returncode == 0:
                    break
                if attempt == 19:
                    raise RuntimeError(check.stderr)
                time.sleep(.2)
            image_ids = command(
                box, 'sudo docker image ls -q --no-trunc').stdout.split()
            images = json.loads(
                command(
                    box, 'sudo docker image inspect ' +
                    ' '.join(map(shlex.quote, sorted(set(image_ids))))).stdout)
            record = {
                'sandbox_id':
                box.sandbox_id,
                'template':
                template,
                'binaries':
                assets,
                'local_kubectl':
                installed,
                'images': [{
                    key: row[key]
                    for key in ('Id', 'RepoTags', 'RepoDigests')
                } for row in images],
                'toolathlon_revision':
                revision,
                'ports_config_sha256':
                hashlib.sha256(ports).hexdigest() if ports else None,
                'instance_suffix':
                suffix,
                'transport':
                'loopback-kubectl-proxy-over-e2b-websocket',
                'inputs_sha256':
                hashes,
            }
            # Runtime evidence is kept outside the model's workspace.
            evidence = REPO / 'state/kubernetes'
            evidence.mkdir(parents=True, exist_ok=True)
            source_record = evidence / f'{box.sandbox_id}.json'
            source_record.write_text(json.dumps(record, indent=2) + '\n')
            os.environ['K8S_SOURCE_RECORD'] = str(source_record)
            (evidence / f'{box.sandbox_id}.log').write_text(setup.stdout +
                                                            setup.stderr)
            yield record
        finally:
            if previous_backup is None:
                backup.unlink(missing_ok=True)
            else:
                backup.write_bytes(previous_backup)
                backup.chmod(previous_mode)
            stop_forwards(process_dir, target)
            connections.close()
            tunnel.close()
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def stop_forwards(process_dir, target):
    """Close this run's forwards after grading, before MCP teardown."""
    for pidfile in Path(process_dir).glob('*.pid'):
        pid = int(pidfile.read_text())
        result = subprocess.run(
            ['ps', '-p', str(pid), '-o', 'command='],
            capture_output=True,
            text=True)
        if str(target) in result.stdout and 'port-forward' in result.stdout:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
