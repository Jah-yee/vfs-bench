#!/usr/bin/env python
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "task"))
sys.path.insert(0, str(REPO_ROOT / "agent"))

import dataset  # noqa: E402
from atlas.constants import ANTHROPIC  # noqa: E402

# This script lives inside the dataset it serves, so it names it from its own
# path rather than inheriting whatever the caller happened to have loaded.
# `grading.child_env` sets BENCH_DATASET for the children *it* spawns, but dvc
# and a bare shell do not, and the default would quietly be the other dataset
# -- which is how this first resolved `task/toolathlon/fantasy-sports-average`.
dataset.use(Path(__file__).resolve().parents[1].name)

# Upstream's own scorer, `services/scoring/score_claims.py` at the submodule
# pin. An LLM judge reads the final message once per claim and answers
# fulfilled, partially_fulfilled or not_fulfilled, worth 1, 0.5 and 0, and the
# run's coverage is their mean. Upstream reports the share of tasks at 0.50
# and at 0.75 coverage and leads with `pass_rate_0.75`, so a run passes at
# 0.75.
SCORER = ("services", "scoring")
REQUIREMENTS = ("requirements.txt", )
PASS = 0.75

# The judge upstream's scorer defaults to, `gemini/gemini-3.1-pro-preview`
# (`EvaluatorConfig.model_name`), as this repo's gateway names it.
JUDGE = "google/gemini-3.1-pro-preview"

# Divergence: the endpoint. Upstream's scorer posts to a LiteLLM proxy's
# `/v1/chat/completions` on its own key; here it posts to the gateway the run
# used, on the run's key, which speaks the same API. The dump names both,
# `base_url` and `api_key_env`; one that does not name the key's variable is
# graded on `run_agent.py`'s default. A Claude model is asked on Anthropic's
# own API (`atlas.constants.ANTHROPIC`), which serves no judge, so its run is
# graded on the gateway, at `run_agent.py`'s default address and key.
KEY = "INFRON_API_KEY"
GATEWAY = os.environ.get("TOOLATHLON_OPENAI_BASE_URL",
                         "https://llm.onerouter.pro/v1")

# Run in upstream's own environment, installed from upstream's own
# requirements file, rather than imported: the module applies `nest_asyncio`
# to the whole process on import, needs matplotlib, which this project does
# not, and `grading.grade` calls this grader on a worker thread of the
# runner's. The child hands one row to `evaluate_dataframe_async`, so the
# empty-answer rule, the truncation and the claim cleaning are upstream's too.
CHILD = """
import asyncio, json, sys
sys.path.insert(0, sys.argv[1])
import pandas
import score_claims as upstream
row = json.load(sys.stdin)
config = upstream.EvaluatorConfig(model_name=row.pop("judge"))
evaluator = upstream.CoverageEvaluator(upstream.AsyncLiteLLMClient(config),
                                       config)
scored = asyncio.run(
    upstream.evaluate_dataframe_async(pandas.DataFrame([row]), evaluator,
                                      "response"))
print(scored.loc[0, "coverage_details_json"])
"""


def upstream(*parts: str) -> Path:
    """A path in the pinned MCP-Atlas checkout.

    Args:
        *parts (str): its components below the checkout.

    Returns:
        Path: the path.
    """
    return REPO_ROOT.joinpath(*dataset.SUBMODULE, *parts)


def digest(task: str) -> str:
    """A digest of what this task is graded against.

    The other dataset prints the sha of upstream's evaluator tree, so that
    both arms of a draw visibly ran the same grader. Here that is the claims,
    upstream's scorer and the requirements it is installed from, the judge
    it is pointed at, and this file, which reads them.

    Args:
        task (str): the task name.

    Returns:
        str: a short hex digest.
    """
    together = hashlib.sha256()
    for part in (dataset.evaluator(task), upstream(*SCORER, "score_claims.py"),
                 upstream(*REQUIREMENTS), Path(__file__)):
        together.update(part.read_bytes())
    together.update(JUDGE.encode())
    return together.hexdigest()[:12]


def answer_of(dump: Path) -> str:
    """What the model said last.

    Atlas scores the agent's final message, not the state it left behind
    (`score_claims.py`), so the run's transcript is the input and the
    workspace is not consulted at all.

    Args:
        dump (Path): the run dump.

    Returns:
        str: the final output.
    """
    return str(json.loads(dump.read_text()).get("final_output") or "")


def judged(claims: list[str], answer: str, base_url: str, key: str) -> dict:
    """Upstream's scorer's verdict on one answer.

    Args:
        claims (list[str]): the row's claims.
        answer (str): the model's final message.
        base_url (str): the gateway the run used.
        key (str): the variable the run read its key from.

    Returns:
        dict: upstream's `coverage_details_json` for the row.

    Raises:
        RuntimeError: the run's key is not set, or the scorer did not answer.
    """
    if not os.environ.get(key):
        raise RuntimeError(f"{key}, the run's key, is not set")
    environment = {
        name: value
        for name, value in os.environ.items() if name != "VIRTUAL_ENV"
    }
    # Upstream's client appends `/v1/chat/completions` itself.
    environment["EVAL_LLM_BASE_URL"] = base_url.rstrip("/").removesuffix("/v1")
    environment["EVAL_LLM_API_KEY"] = os.environ[key]
    done = subprocess.run([
        "uv", "run", "--isolated", "--no-project", "--python", "3.12",
        "--with-requirements",
        str(upstream(*REQUIREMENTS)), "python", "-c", CHILD,
        str(upstream(*SCORER))
    ],
                          input=json.dumps({
                              "GTFA_CLAIMS": claims,
                              "response": answer,
                              "judge": JUDGE
                          }),
                          capture_output=True,
                          text=True,
                          env=environment,
                          cwd=upstream(),
                          check=False)
    lines = done.stdout.strip().splitlines()
    if done.returncode != 0 or not lines:
        raise RuntimeError(f"the scorer failed: {done.stderr.strip()[-2000:]}")
    return json.loads(lines[-1])


def main(argv=None) -> int:
    """Score one run's answer against the claims its Atlas row was cut from.

    With upstream's own scorer and judge, and upstream's pass mark. The
    verdict is written into the dump beside the answer it judged, because a
    judge asked again need not answer the same.

    Returns:
        int: 0 when coverage reaches the pass mark; 1 when it does not; 2
            when there is no dump, the run's key is not set, or the scorer
            did not answer.
    """
    parser = argparse.ArgumentParser(
        description="Grade one MCP-Atlas run against its claims.")
    parser.add_argument("task")
    parser.add_argument("--dump", default=None, help="the run dump to grade")
    parser.add_argument("--print-sha",
                        action="store_true",
                        help="print the claims digest and exit")
    parser.add_argument("--agent-workspace",
                        default=None,
                        help="accepted for symmetry with the other dataset's "
                        "grader; Atlas grades the answer, not the workspace")
    parser.add_argument("--launch-time", default=None, help="likewise unused")
    args = parser.parse_args(argv)

    if args.print_sha:
        print(digest(args.task))
        return 0

    if not args.dump:
        print("grade_task: --dump is required; Atlas grades the transcript",
              file=sys.stderr)
        return 2
    dump = Path(args.dump)
    if not dump.is_file():
        print(f"grade_task: no dump at {dump}", file=sys.stderr)
        return 2

    written = json.loads(dump.read_text())
    base_url, key = written["base_url"], written.get("api_key_env", KEY)
    if written.get("model", "").startswith(ANTHROPIC):
        base_url, key = GATEWAY, KEY
    try:
        verdict = judged(
            dataset.declaration(args.task)["claims"], answer_of(dump),
            base_url, key)
    except RuntimeError as error:
        print(f"grade_task: {error}", file=sys.stderr)
        return 2
    coverage = verdict.get("coverage_score")
    if coverage is None:
        print(f"grade_task: {verdict.get('explanation')}", file=sys.stderr)
        return 2
    written["judge"] = {
        "model": JUDGE,
        "base_url": base_url,
        "api_key_env": key,
        "coverage_details": verdict
    }
    dump.write_text(json.dumps(written, indent=2) + "\n")

    for claim in verdict["per_claim"]:
        print(f"{claim['score']:.1f}: {claim['claim']}")
        print(f"      {claim['reason']}")
    print(f"coverage {coverage:.3f}; a run passes at {PASS}")
    return 0 if coverage >= PASS else 1


if __name__ == "__main__":
    sys.exit(main())
