# Git milestone

Look up four GitHub repositories by numeric id — the 1st, the 1,000th, the
millionth and the billionth — and record eight fields of each in
`github_info.json`, skipping any that does not exist. One of the four does
not.

## Both arms read GitHub live, as upstream does

Upstream's `fetch` server is a wrapper around `fetch()`, so this task reaches
the live GitHub API, and so does its evaluator: at grading time it
re-fetches all four repositories, writes them to `after_task.json`, and
accepts a star count anywhere between that and the `before_task.json`
committed months earlier.

This task used to be offline instead. A committed capture answered the
`fetch` server, the mirage arm's `fetch` CLI and, through an eval shim, the
evaluator, so the band closed on values the agent could have seen. That held
only while the capture was the agent's one door to GitHub. Once the MCP
arm's terminal ran in upstream's task image, with its network, the model
could curl the live API, and the capture's band would reject live counts.

It is now one of the research tasks (`server/seed/research.py`): the `fetch`
server and the `fetch` CLI read the live web through the same recorded
transport, and the evaluator re-fetches live as upstream's does. It signs
those calls with the token in upstream's `configs/token_key_session.py`,
which ships as the placeholder "XX" for the operator to fill in; GitHub
answers "XX" with a 401, and the evaluator then falls back to its committed
`before_task.json`, so the band closes on months-old counts. The task's
eval shim ([`github_token.py`](../../../redirect/eval_shim/github_token.py))
signs them with the operator's `GITHUB_TOKEN` instead. Without a
`GITHUB_TOKEN` the grade still runs as upstream's would on "XX", and the
shim says so on stderr, in the grade's log.

## What the grader actually checks

Less than it appears. `star_count` and `fork_count` must fall in the
before/after band; `repo_name`, `owner`, `language`, `description` and
`repo_url` are compared with normalisation. `creation_time` is not compared
at all — the reference records it under `creation_date` and the comparison
loop only visits keys the reference has, so the field the task asks for is
checked for presence and nothing else.

Repo 1000 is the interesting one: absent from the results is correct, and so
is present-but-marked-unknown.
