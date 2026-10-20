import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
# The dataset seam, not a spelled path: these used to live inside
# `task/toolathlon/` and hardcode it, which is the one thing the seam
# exists to stop.
sys.path.insert(0, str(REPO_ROOT / "agent"))
import dataset  # noqa: E402

BOOLEANS = {"true", "false"}


def is_integer(value: str) -> bool:
    """Whether a cell is an integer with nothing else in it.

    Args:
        value (str): the cell.
    """
    try:
        int(value)
    except ValueError:
        return False
    return True


def is_float(value: str) -> bool:
    """Whether a cell is a number.

    `float` also accepts `nan` and `inf`, which are words a text column may
    legitimately hold, so they are excluded.

    Args:
        value (str): the cell.
    """
    if value.strip().lower().lstrip("+-") in {"nan", "inf", "infinity"}:
        return False
    try:
        float(value)
    except ValueError:
        return False
    return True


def column_type(values: list[str]) -> str:
    """The BigQuery type for one column's worth of cells.

    Args:
        values (list[str]): every non-empty cell in the column.

    Returns:
        str: an emulator column type.
    """
    if not values:
        return "STRING"
    if all(is_integer(value) for value in values):
        return "INT64"
    if all(is_float(value) for value in values):
        return "FLOAT64"
    if all(value.strip().lower() in BOOLEANS for value in values):
        return "BOOL"
    return "STRING"


def typed(value: str, kind: str) -> Any:
    """One cell, as the type its column was given.

    An empty cell is NULL whatever the column is: a CSV cannot distinguish
    the empty string from a missing value, and BigQuery's loader reads it as
    the latter.

    Args:
        value (str): the cell.
        kind (str): the column's type.

    Returns:
        Any: the value for the seed file.
    """
    if value == "":
        return None
    if kind == "INT64":
        return int(value)
    if kind == "FLOAT64":
        return float(value)
    if kind == "BOOL":
        return value.strip().lower() == "true"
    return value


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read one CSV into rows and its header order.

    Args:
        path (Path): the file.

    Returns:
        tuple[list[dict[str, str]], list[str]]: the rows, and the column
            names in the order the header wrote them.

    Raises:
        SystemExit: the file is missing or has no header.
    """
    if not path.is_file():
        sys.exit(f"no such fixture: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            sys.exit(f"no header row in {path}")
        return list(reader), list(reader.fieldnames)


def table_of(spec: dict[str, Any], task_dir: Path) -> dict[str, Any]:
    """Build one emulator table from one CSV.

    Args:
        spec (dict[str, Any]): a `tables` entry from `shared/bigquery.json`.
        task_dir (Path): the upstream task directory the CSV is relative to.

    Returns:
        dict[str, Any]: the table, as the emulator's YAML wants it.
    """
    rows, header = read_csv(task_dir / spec["csv"])
    # A column the task names explicitly keeps that type; everything else is
    # inferred. The override exists because inference reads only this
    # fixture, and a column that happens to be all-digits here may be a
    # string upstream.
    declared = spec.get("types", {})
    kinds = {
        name:
        declared.get(name)
        or column_type([r[name] for r in rows if r.get(name)])
        for name in header
    }
    return {
        "id":
        spec["table"],
        "columns": [{
            "name": name,
            "type": kinds[name]
        } for name in header],
        "data": [{
            name: typed(row[name], kinds[name])
            for name in header
        } for row in rows],
    }


def build(task: str) -> dict[str, Any]:
    """The whole seed document for one task.

    Args:
        task (str): the task name, shared by both trees.

    Returns:
        dict[str, Any]: the emulator's `projects:` document.

    Raises:
        SystemExit: the task has no `shared/bigquery.json`.
    """
    manifest_path = dataset.local(task) / "shared" / "bigquery.json"
    if not manifest_path.is_file():
        sys.exit(f"no bigquery manifest at {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    task_dir = dataset.task_dir(task)

    # A dataset with no tables is a real fixture, not an empty one:
    # price-comparison's preprocess deletes and recreates
    # `bigquery_pricing_analysis` empty, and the task is to make the table.
    # Seeding the dataset but not the table is what upstream leaves behind.
    datasets: dict[str, list[dict[str, Any]]] = {
        name: []
        for name in manifest.get("datasets", [])
    }
    for spec in manifest.get("tables", []):
        datasets.setdefault(spec["dataset"],
                            []).append(table_of(spec, task_dir))
    if not datasets:
        sys.exit(f"{manifest_path} names neither datasets nor tables")
    return {
        "projects": [{
            "id":
            manifest["project"],
            "datasets": [{
                "id": name,
                **({
                    "tables": tables
                } if tables else {}),
            } for name, tables in datasets.items()],
        }]
    }


def write(task: str, out: Path) -> dict:
    """Build one task's emulator seed file and report what went in it.

    Args:
        task (str): the task name.
        out (Path): where to write the seed file.

    Returns:
        dict: the document written.
    """
    document = build(task)
    out.parent.mkdir(parents=True, exist_ok=True)
    # `default_flow_style=False` keeps it block-shaped and diffable, and
    # `sort_keys=False` keeps the columns in the header's order, which is the
    # order `SELECT *` will show them in.
    out.write_text(
        yaml.safe_dump(document, default_flow_style=False, sort_keys=False))

    # `bq_dataset`, not `dataset`: the seam is imported under that name.
    for bq_dataset in document["projects"][0]["datasets"]:
        # A dataset with no `tables` key is the deliberate empty fixture --
        # price-comparison's, where making the table is the task -- so it is
        # reported rather than skipped, to distinguish it from a manifest
        # whose CSV silently read as zero rows.
        if "tables" not in bq_dataset:
            print(f"{bq_dataset['id']}: empty dataset, no tables")
        for table in bq_dataset.get("tables", []):
            print(f"{bq_dataset['id']}.{table['id']}: "
                  f"{len(table['data'])} rows")
    print(f"-> {out}")
    return document


def main() -> int:
    """Entry point.

    Returns:
        int: process exit status.
    """
    parser = argparse.ArgumentParser(
        description="Turn a task's committed CSVs into a "
        "bigquery-emulator seed file.")
    parser.add_argument("task",
                        help="the task name, e.g. flagged-transactions")
    parser.add_argument("-o",
                        "--out",
                        type=Path,
                        required=True,
                        help="where to write the seed file")
    args = parser.parse_args()
    write(args.task, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
