# Git repo

Read a paper, find the unofficial implementation of it on GitHub with the
most stars, and write that URL into `result.json`.

## The task is not "sort by stars", and the fixture is what keeps that true

The paper is *Mixture-of-Depths: Dynamically allocating compute in
transformer-based language models*, and the expected answer is
`astramind-ai/Mixture-of-depths` at 176 stars. Searching GitHub for
`Mixture-of-Depths` sorted by stars puts **three repositories above it**:

| stars | repository | what it actually is |
|---:|---|---|
| 581 | `raymin0223/mixture_of_recursions` | Mixture-of-**Recursions**, a different paper |
| 300 | `dingo-actual/infini-transformer` | Infini-Transformer, a different paper |
| 274 | `hustvl/MoDA` | Mixture-of-Depths **Attention**, a different paper |
| **176** | **`astramind-ai/Mixture-of-depths`** | **unofficial implementation of this paper** |
| 123 | `kyegomez/Mixture-of-Depths` | also an implementation of this paper |
| 31 | `CASE-Lab-UMD/Router-Tuning-...` | says "official implementation", of another paper |

Taking the top row fails. Passing means reading the descriptions and
deciding which repositories implement *this* paper — and, one row further
down, that "official" disqualifies a candidate the brief asks for the
unofficial version of.

**That is only stable if the ranking is frozen.** Star counts move, and
upstream grades against a URL recorded months ago, so against the live API
the answer depends on the day. `shared/capture_repos.py` captures the
search — five plausible phrasings of the paper's title, unioned, 32
repositories with descriptions and star counts — and `shared/fixtures/
repos.json` is what both arms read. Same reasoning as
[git-milestone](../git-milestone/README.md), where the evaluator refetches
star counts at grading time and the band an answer must land in depends on
the hour.

The margin is thin enough to be worth stating plainly: 176 against 274 is
not much, and one more push to `hustvl/MoDA` would not change the right
answer but would make an arm that sorts blindly look even more wrong.

## Repositories that are metadata, not trees

This is the first task that picks *between* repositories rather than reading
inside one, so the fake grew a second seeding mode. `--metadata` takes a
JSON file keyed by `owner/name` and creates repositories that have
descriptions, star counts, languages and topics and no files at all. The
tree, contents and README endpoints answer 404 for them — which is what
GitHub says about a repository with no README, and now means that rather
than "no such endpoint".

`search/repositories` gained `sort=stars` and matches against the
description as well as the name, since a repository is found by what it says
it does at least as often as by what it is called.

**Neither arm can ask for star-sorted results, and for different reasons.**
The MCP `search_repositories` tool has no `sort` parameter at all — query,
page, perPage and `minimal_output`, nothing else — so it always gets
GitHub's relevance ordering and has to read `stargazers_count` off the
items. mirage reaches the same endpoint through `gh api search/repositories
-f sort=stars`, which the fake honours.

## Reproducing

```bash
uv run python server/mcp/setup_github.py        # needs Go; once per machine
uv run python agent/run_agent.py toolathlon/git-repo --tools vfs
uv run python agent/run_agent.py toolathlon/git-repo --tools mcp
```

Re-capturing the fixture (`shared/capture_repos.py`) needs network and will
change the star counts. Do not do it casually: the expected answer is only
correct for a ranking in which the three repositories above it belong to
other papers, and that is a property of the capture, not of GitHub.

The evaluator is local-only — it compares `result.json` against the
groundtruth URL — so no shim is needed. It does read `--res_log_file`
unconditionally, which the batch supplies as a stub.
