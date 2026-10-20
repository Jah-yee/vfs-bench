import os

_GWS = os.environ.get("GWS_MOCK_URL", "").rstrip("/")

# Service path per API, as the mock server routes them.
_SERVICE_PATHS = {"drive": "/drive/v3/", "sheets": "/"}
# gspread's URL constants, and where each lives on the mock. `%s` survives
# the rewrite because only the host and any /v3 prefix change.
_GSPREAD_HOSTS = (
    "https://sheets.googleapis.com",
    "https://www.googleapis.com",
)

if _GWS:
    import googleapiclient.discovery as _discovery
    from google.api_core.client_options import ClientOptions

    _original_build = _discovery.build

    def _build(serviceName, version=None, *args, **kwargs):  # noqa: N803
        """Inject the mock endpoint for services the mock implements."""
        path = _SERVICE_PATHS.get(serviceName)
        if path is not None and not kwargs.get("client_options"):
            kwargs["client_options"] = ClientOptions(api_endpoint=_GWS + path)
        kwargs.setdefault("cache_discovery", False)
        return _original_build(serviceName, version, *args, **kwargs)

    _discovery.build = _build

    try:
        import gspread.http_client as _http
        import gspread.urls as _urls
    except ImportError:  # an evaluator that never touches gspread
        _http = None

    if _http is not None:
        for _name in dir(_urls):
            if _name.startswith("_"):
                continue
            _value = getattr(_urls, _name)
            if not isinstance(_value, str):
                continue
            for _host in _GSPREAD_HOSTS:
                if _value.startswith(_host):
                    _value = _GWS + _value[len(_host):]
                    break
            else:
                # docs.google.com URLs are the human-facing spreadsheet links
                # gspread builds for `Spreadsheet.url`; nothing requests them.
                continue
            setattr(_urls, _name, _value)
            if hasattr(_http, _name):
                setattr(_http, _name, _value)
