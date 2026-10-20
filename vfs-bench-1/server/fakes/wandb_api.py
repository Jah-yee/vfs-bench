"""Own a fresh Mirage W&B API fixture for one benchmark arm."""
import gzip
import json
import os
import selectors
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[2]
API_KEY = "0123456789abcdef0123456789abcdef01234567"


@contextmanager
def serve(task_dir: Path):
    """Start the pinned API mock and restore the caller's environment."""
    config = json.loads((task_dir / "shared/wandb.json").read_text())
    with fixture_root(config['fixture']) as root, start(config, root) as base:
        yield base


@contextmanager
def fixture_root(name):
    """Materialize compressed captures without changing the foreign loader."""
    root = REPO / "task/toolathlon/shared/fixtures"
    fixture = root / "wandb" / f"{name}.json"
    if fixture.is_file():
        yield root
        return
    packed = fixture.with_suffix('.json.gz')
    if not packed.is_file():
        raise FileNotFoundError(f"Missing W&B capture: {packed}")
    with TemporaryDirectory(prefix='toolathlon-wandb-') as directory:
        root = Path(directory)
        (root / 'wandb').mkdir()
        with gzip.open(packed,
                       'rb') as source, (root / 'wandb' /
                                         fixture.name).open('wb') as out:
            shutil.copyfileobj(source, out)
        yield root


@contextmanager
def start(config, root):
    integ = REPO / "submodule/mirage/integ"
    previous = {
        key: os.environ.get(key)
        for key in ("WANDB_BASE_URL", "WANDB_API_KEY")
    }
    # The child is Mirage's foreign TypeScript mock, not a Python sibling.
    process = subprocess.Popen([
        str(integ / "node_modules/.bin/tsx"),
        str(REPO / "server/fakes/wandb_api.mjs"),
        "--port",
        "0",
        "--fixture",
        config["fixture"],
        "--fixture-root",
        str(root),
    ],
                               cwd=integ,
                               stdout=subprocess.PIPE,
                               text=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=30):
                raise RuntimeError("W&B fixture did not start within 30s")
            line = process.stdout.readline().strip()
        if not line.startswith("WANDB_BASE_URL=http://127.0.0.1:"):
            raise RuntimeError(
                f"W&B fixture failed to announce its port: {line}")
        os.environ["WANDB_BASE_URL"] = line.split("=", 1)[1]
        os.environ["WANDB_API_KEY"] = API_KEY
        yield os.environ["WANDB_BASE_URL"]
    finally:
        from server.seed.papers import close
        close(process)
        process.stdout.close()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
