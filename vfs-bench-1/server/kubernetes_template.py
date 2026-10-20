"""Build the E2B image used by the Kubernetes fixture, once per account."""
import asyncio
import dataclasses
import hashlib
import json
from pathlib import Path

from e2b import AsyncTemplate

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / 'state/kubernetes-template.json'
INSTALL = Path(__file__).with_name('kubernetes-template.sh').read_text()


def recipe_sha():
    return hashlib.sha256(INSTALL.encode()).hexdigest()


def receipt():
    """Require a template built from this recipe; never fall back to base."""
    if not RECEIPT.is_file():
        raise FileNotFoundError(
            'Run uv run python server/kubernetes_template.py first')
    record = json.loads(RECEIPT.read_text())
    if record['recipe_sha256'] != recipe_sha():
        raise ValueError(
            'Kubernetes template recipe changed; rebuild the template')
    return record


async def main():
    template = AsyncTemplate().from_base_image().run_cmd(INSTALL, user='root')
    build = await AsyncTemplate.build(
        template,
        alias='vfs-bench-kubernetes',
        cpu_count=2,
        memory_mb=4096,
        on_build_logs=lambda entry: print(entry, flush=True))
    record = {
        **dataclasses.asdict(build), 'recipe_sha256': recipe_sha(),
        'cpu_count': 2,
        'memory_mb': 4096
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(record, indent=2, default=str) + '\n')
    print(f'Template ready: {build.template_id}')


if __name__ == '__main__':
    asyncio.run(main())
