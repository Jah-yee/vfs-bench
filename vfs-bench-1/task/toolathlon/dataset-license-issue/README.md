# Dataset license issue

Someone filed an issue asking which licence two released datasets carry.
Find the sources each was built from, take the most permissive, reply in a
fixed format, close the issue, and append the same line to both dataset
cards on the Hub.

## The expected answer

The expected answer is `odc-by` for both datasets; the evaluator accepts
three spellings of it.

The trail is two hops. The raw card says its
data is "adopted from the original dataset from HuggingfaceTB team", and
`HuggingFaceTB/smollm-corpus` declares `license: odc-by`. The reasoning card says its responses were
"synthesizing all the desired responses using DeepSeek-V2.5", and
`deepseek-ai/DeepSeek-V2.5` declares `license: other` with a
`license_name: deepseek` and a link to a bespoke model licence.

What the ask actually wants there is a comparison rather than a lookup --
"if there are multiple sources, I'll use the one with the most permissive
permissions" -- so a bespoke model licence loses to ODC-BY and the answer is
`odc-by` again. That step is the task.

`tests/parity.json`'s first case re-seeds and asks the GitHub and Hub
servers `github_search_repositories("Annoy-DataSync")` and
`hub_repo_search("Annoy-PyEdu", datasets)`, which answer `1` and `2`, so
the seeded repositories' visibility is checked rather than remembered.

## Two endpoints the fakes did not have

Neither is reachable from any mirage client, so both are covered by the
selftests in mirage rather than by the battery.

**`GET /<kind>/:ns/:name/raw/:rev/*path` on the Hub fake.** The evaluator
reads each card back with a bare
`requests.get("https://huggingface.co/datasets/<id>/raw/main/README.md")`.
`/raw/` is not a synonym for `/resolve/`: it answers `text/plain` with no
redirect, and on an LFS-tracked path it serves the git-lfs POINTER rather
than the file -- 133 bytes against 37MB, probed on the live Hub.

**`GET /repos/:owner/:repo/issues/:number/comments` on the GitHub fake.**
The evaluator reads `comments[-1]` and checks its author and its body, so
the listing has to exist and has to be oldest-first.

`toolathlon/eval_shim` loads three redirects rather than the usual one:
`github_host` for the hardcoded api.github.com, `hf_token` for the token
upstream ships unfilled, and a new `hf_host` for that one `requests.get`
that goes around `huggingface_hub` entirely and so never sees `HF_ENDPOINT`.

## Grading this task destroys its fixture

`evaluation/main.py` ends in a `finally` that deletes the GitHub repository
and both Hub datasets, and both fakes implement those deletes. A measured
run is unaffected -- each arm seeds before it starts -- but a grader run
twice by hand fails the second time on a repository that is not there, and
that failure is not the run's.

## The linked model licence is captured

The DeepSeek-V2.5 card at revision
`c85b5ede86f2a598af339624cac5723861e557ed` declares `license: other` and
links to DeepSeek-V2's `LICENSE-MODEL`. That document is evidence the task
requires: it grants derivative rights but requires downstream licences to
retain its use restrictions, which is what an agent must compare with
ODC-BY.

Both arms now read the same frozen web fixture. It contains the exact
branch URL from the card, the equivalent GitHub page at commit
`da42dcd40b41803c68a712ddd210eeb10e71e598`, where the file last changed,
and the immutable raw document. The raw body is 13,760 bytes with SHA-256
`a3a0e9449cb691a12f4de1d03725fd41326614fdeaf5d80b28c51187da0bed0e`.
`shared/web_source.json` records the card revision, URLs and response
checksums. MCP uses upstream `fetch`; VFS runs the same tools as the `fetch` CLI, and
`tests/parity.json` checks that both extract the same derivative-use term.

## The Dataset Viewer answers are the live server's — 2026-09-19

The MCP arm reads the corpus card through `hub_repo_details`, whose
`dataset_structure` and `dataset_preview` operations mirage's Hub fake
refuses. `shared/hub-viewer/` holds 52 responses captured from
`huggingface.co/mcp` (server 0.4.20) on 2026-09-19 for
`HuggingFaceTB/smollm-corpus` at the revision the fixture pins: its
structure, alone and beside the other operations, and preview pages for
each of its three configs. `server/fakes/hub_viewer.py` answers those
requests from the capture in front of the fake, for both arms; everything
else still reaches the fake.
