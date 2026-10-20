import os

_GITHUB = os.environ.get("GITHUB_URL", "").rstrip("/")
_REAL = "https://api.github.com"

if _GITHUB:
    import requests

    _original_request = requests.sessions.Session.request

    def _request(self, method, url, *args, **kwargs):
        """Rewrite an api.github.com call onto the fake, pass others on."""
        if isinstance(url, str) and url.startswith(_REAL):
            url = _GITHUB + url[len(_REAL):]
        return _original_request(self, method, url, *args, **kwargs)

    requests.sessions.Session.request = _request
