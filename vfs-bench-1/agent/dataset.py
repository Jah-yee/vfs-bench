import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

# Underscored, every one. A name defined here shadows the seam's: PEP 562
# `__getattr__` fires only when normal lookup fails, so a plain `POOL`
# here silently answered `dataset.POOL` with this module's path instead
# of the seam's `("tasks", "finalpool")`, and `grade_task.py` got a
# TypeError from `joinpath(*a_path)`. The public names below -- `names`,
# `use`, `loaded`, `split`, `DEFAULT` -- are checked against the seam's
# and do not collide.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_POOL = _REPO_ROOT / "task"

# A dataset's seam is the package under `task/<name>/`, so the directory
# supplies the module name and `task/` is what has to be importable.
if str(_POOL) not in sys.path:
    sys.path.insert(0, str(_POOL))

DEFAULT = os.environ.get("BENCH_DATASET", "toolathlon")

_LOADED: ModuleType | None = None


def names() -> list[str]:
    """Every dataset this checkout carries.

    Returns:
        list[str]: names, sorted.
    """
    return sorted(d.name for d in _POOL.iterdir()
                  if (d / "__init__.py").is_file())


def use(name: str) -> ModuleType:
    """Select the dataset every later `dataset.<attr>` reads through.

    Args:
        name (str): a directory under `task/` carrying a seam.

    Returns:
        ModuleType: the seam module.

    Raises:
        SystemExit: no such dataset.
    """
    global _LOADED
    if name not in names():
        raise SystemExit(f"no dataset {name!r}; this checkout has "
                         f"{', '.join(names())}")
    _LOADED = importlib.import_module(name)
    return _LOADED


def loaded() -> ModuleType:
    """The selected dataset, defaulting on first use.

    Returns:
        ModuleType: the seam module.
    """
    return _LOADED if _LOADED is not None else use(DEFAULT)


def carrying(task: str) -> list[str]:
    """Which datasets have a task by that name.

    Args:
        task (str): the task name.

    Returns:
        list[str]: dataset names, sorted.
    """
    found = []
    for name in names():
        seam = importlib.import_module(name)
        if (seam.local(task) / "shared" / "task.md").is_file():
            found.append(name)
    return found


def split(spelling: str) -> tuple[str, str]:
    """Read a `<dataset>/<task>` argument, and select the dataset.

    The bare form is accepted only while it cannot be ambiguous -- one
    dataset in the checkout, or one that carries this task. With two it is
    refused by name rather than resolved to a default, because a default
    that looks like a decision is how this repo has been bitten before:
    the hardcoded server list, the per-task `setdefault`, the config read
    off a patched working tree.

    Args:
        spelling (str): `toolathlon/nhl-b2b-analysis` or `nhl-b2b-analysis`.

    Returns:
        tuple[str, str]: the dataset name and the task name.

    Raises:
        SystemExit: a bare name that more than one dataset carries.
    """
    name, sep, task = spelling.rpartition("/")
    if not sep:
        found = carrying(task) or names()
        if len(found) > 1:
            raise SystemExit(f"{task!r} is in {', '.join(found)}; say which "
                             f"-- e.g. {found[0]}/{task}")
        name = found[0]
    use(name)
    return name, task


# Everything this module does not define itself comes from the selected
# dataset, so `import dataset` reads the same as the `import toolathlon as
# dataset` it replaces -- and a second benchmark is `use()` rather than an
# edit to arms, grading, mcp_servers or the parity suite.
def __getattr__(attr: str):
    """Forward an unknown attribute to the selected dataset.

    Args:
        attr (str): the attribute name.

    Returns:
        object: whatever the seam defines under that name.
    """
    return getattr(loaded(), attr)
