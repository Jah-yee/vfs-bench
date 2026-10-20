import os

_HF = os.environ.get("HF_ENDPOINT", "").rstrip("/")
_TOKEN = os.environ.get("HF_TOKEN", "")
_REAL = "https://huggingface.co"

# `huggingface_hub` reads HF_ENDPOINT itself, so nothing here is needed for a
# client that goes through the library. What needs it is an evaluator that
# does not: `dataset-license-issue` reads each card back with a literal
# `requests.get("https://huggingface.co/datasets/<id>/raw/main/README.md")`
# -- no endpoint override, no token, and a status check that exits 1 on
# anything but 200. Against the live Hub that reads two repositories which do
# not exist there, so the grade would be decided by a 404 rather than by what
# the agent wrote.
#
# The bearer is added because on this fake it IS the tenant: an anonymous
# read of a seeded repository is a 401, and the run's own HF_TOKEN is the
# tenant every other part of the grade already uses.
if _HF and _HF != _REAL:
    import requests

    _original_request = requests.sessions.Session.request

    def _request(self, method, url, *args, **kwargs):
        """Rewrite a huggingface.co call onto the fake, pass others on."""
        if isinstance(url, str) and url.startswith(_REAL):
            url = _HF + url[len(_REAL):]
            if _TOKEN:
                headers = dict(kwargs.get("headers") or {})
                headers.setdefault("Authorization", f"Bearer {_TOKEN}")
                kwargs["headers"] = headers
        return _original_request(self, method, url, *args, **kwargs)

    requests.sessions.Session.request = _request
