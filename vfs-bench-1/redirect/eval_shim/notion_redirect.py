import os

_NOTION = os.environ.get("NOTION_URL", "").rstrip("/")
_TOKEN = os.environ.get("NOTION_TOKEN", "")
_REAL = "https://api.notion.com"

if _NOTION:
    import requests.api as _api

    _original_request = _api.request

    def _request(method, url, **kwargs):
        """Rewrite a Notion call onto the fake, and re-authenticate it."""
        if isinstance(url, str) and url.startswith(_REAL):
            url = _NOTION + url[len(_REAL):]
            if _TOKEN:
                headers = dict(kwargs.get("headers") or {})
                headers["Authorization"] = f"Bearer {_TOKEN}"
                kwargs["headers"] = headers
        return _original_request(method, url, **kwargs)

    _api.request = _request
    # ops.py calls `requests.request(...)`, which is this same function
    # re-exported on the package; rebinding only requests.api would leave that
    # call site pointing at the original.
    import requests as _requests

    _requests.request = _request
