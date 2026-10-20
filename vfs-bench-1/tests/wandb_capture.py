"""A failed refresh must leave the last complete capture usable."""
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "task/toolathlon/script"))
import capture_wandb as capture  # noqa: E402
import check_wandb  # noqa: E402


class Capture(unittest.TestCase):

    def test_failed_refresh_preserves_previous_snapshot(self):

        def initial(entity, project, destination):
            path = destination / f"{project}.json"
            path.write_text('{"source":{}}')
            return path

        for phase in ("capture_selected", "capture_windows", "check_snapshot"):
            with self.subTest(
                    phase=phase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                target = root / "deepscaler-1.5b.json"
                target.write_bytes(b"previous complete snapshot")
                with ExitStack() as patches:
                    patches.enter_context(patch.object(capture, "DEST", root))
                    patches.enter_context(
                        patch.object(capture, "capture", side_effect=initial))
                    for name in ("capture_selected", "capture_windows",
                                 "check_snapshot"):
                        error = RuntimeError(
                            "interrupted") if name == phase else None
                        patches.enter_context(
                            patch.object(capture, name, side_effect=error))
                    with self.assertRaisesRegex(RuntimeError, "interrupted"):
                        capture.main()
                self.assertEqual(target.read_bytes(),
                                 b"previous complete snapshot")
                self.assertEqual(list(root.iterdir()), [target])

    def test_complete_refresh_publishes_provenance(self):

        def initial(entity, project, destination):
            path = destination / f"{project}.json"
            path.write_text('{"source":{}}')
            return path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(capture, "DEST", root), \
                    patch.object(capture, "capture", side_effect=initial), \
                    patch.object(capture, "capture_selected"), \
                    patch.object(capture, "capture_windows"), \
                    patch.object(capture, "check_snapshot"):
                capture.main()
            files = list(root.iterdir())
            self.assertEqual(len(files), 1)
            source = json.loads(files[0].read_text())["source"]
            self.assertEqual(len(source["toolathlon"]["task_sha256"]), 2)
            self.assertIn("uv.lock", source["capture_sha256"])

    def test_live_check_reports_each_moved_observation(self):
        run = {
            "name":
            "r",
            "config": {},
            "summaryMetrics": {},
            "systemMetrics": {},
            "historyKeys": {
                "lastStep": 1
            },
            "history": [{
                "_step": 0,
                "m": 1
            }, {
                "_step": 1,
                "m": 2
            }],
            "historySamples": [{
                "args": {},
                "rows": ['{"_step":0}']
            }, {
                "args": {
                    "minStep": 0,
                    "maxStep": 1
                },
                "rows": ['{"_step":0}']
            }],
            "selectedHistorySamples": [{
                "spec": {
                    "keys": ["m"],
                    "samples": 5
                },
                "rows": [{
                    "m": 1
                }]
            }],
        }
        fixture = {
            "source": {},
            "projects": {
                "e/p": {
                    "id": "P",
                    "runCount": 1
                }
            },
            "entities": {
                "e": {
                    "p": [run]
                }
            },
        }
        live = {
            "project": {
                "id": "P",
                "runCount": 1
            },
            "runs": [{
                key: value
                for key, value in run.items()
                if key not in ("history", "historySamples",
                               "selectedHistorySamples")
            }],
            "history": ['{"_step":0,"m":1}', '{"_step":1,"m":2}'],
            "sample": ['{"_step":0}'],
            "windows": {
                "h0": ['{"_step":0}']
            },
            "selected": [[{
                "m": 1
            }]],
        }

        def query(session, text, variables):
            if text is capture.PROJECT:
                return {"project": live["project"]}
            if text is capture.HISTORY:
                return {"project": {"run": {"history": live["history"]}}}
            if "sampledHistory" in text:
                return {
                    "project": {
                        "run": {
                            "sampledHistory": live["selected"]
                        }
                    }
                }
            if "h0:history(" in text:
                return {"project": {"run": live["windows"]}}
            return {"project": {"run": {"history": live["sample"]}}}

        def pages(session, text, variables, keys):
            return [dict(item) for item in live["runs"]]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.json"
            path.write_text(json.dumps(fixture))
            with patch.object(capture, "query", side_effect=query), \
                    patch.object(capture, "pages", side_effect=pages):
                self.assertEqual(check_wandb.check(path), [])
                live["sample"] = ['{"_step":1}']
                live["selected"] = [[{"m": 2}]]
                live["runs"][0]["summaryMetrics"] = {"m": 2}
                drift = check_wandb.check(path)
        self.assertEqual(
            sorted(drift),
            sorted([
                "r.summaryMetrics: changed",
                "r.history(): sample changed (1 -> 1 rows)",
                "r: 1/1 selected-history samples changed",
            ]))


if __name__ == "__main__":
    unittest.main()
