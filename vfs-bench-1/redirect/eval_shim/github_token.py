import os

# An evaluator that refetches api.github.com itself signs with the token in
# Toolathlon's own `configs/token_key_session.py`, where it is the literal
# "XX" that upstream ships for its operator to fill in. GitHub answers "XX"
# with a 401, and `git-milestone`'s evaluator then falls back to its committed
# `before_task.json` and grades against a band that closed months ago.
#
# `requests` is patched rather than the config for the reason `hf_token`
# gives: `sitecustomize` runs before `configs` is importable. Only requests to
# api.github.com are signed, and with the operator's own token, as upstream's
# would be.
_TOKEN = os.environ.get("GITHUB_TOKEN", "")

if _TOKEN:
    import requests

    _original_request = requests.Session.request

    def _request(self, method, url, *args, **kwargs):
        """Sign a call to the live GitHub API with the operator's token."""
        if str(url).startswith("https://api.github.com/"):
            kwargs["headers"] = {
                **(kwargs.get("headers") or {}), "Authorization":
                f"token {_TOKEN}"
            }
        return _original_request(self, method, url, *args, **kwargs)

    requests.Session.request = _request
else:
    import sys

    # Upstream grades the same way when its operator leaves "XX" in place,
    # so the grade stands, but not silently: the band it closes on is
    # `before_task.json`'s.
    print(
        "github_token: GITHUB_TOKEN is unset, so api.github.com refuses "
        "the evaluator's refetch and it grades against before_task.json",
        file=sys.stderr)
