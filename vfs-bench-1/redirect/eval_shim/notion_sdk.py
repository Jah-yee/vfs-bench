import os

_NOTION = os.environ.get("NOTION_URL", "").rstrip("/")
_TOKEN = os.environ.get("NOTION_TOKEN", "")

if _NOTION:
    try:
        import notion_client
    except ImportError:  # pragma: no cover - the SDK is a task dependency
        notion_client = None

    if notion_client is not None:

        def _patch(cls: type) -> None:
            """Make one SDK client class construct against the fake.

            Args:
                cls (type): `Client` or `AsyncClient`.
            """
            original = cls.__init__

            def __init__(self, *args, **kwargs):
                """Force the fake's base URL and this run's workspace token."""
                options = kwargs.get("options")
                if isinstance(options, dict):
                    options = dict(options)
                    options["base_url"] = _NOTION
                    if _TOKEN:
                        options["auth"] = _TOKEN
                    kwargs["options"] = options
                elif options is None:
                    kwargs["base_url"] = _NOTION
                    if _TOKEN:
                        kwargs["auth"] = _TOKEN
                else:
                    # A ClientOptions instance: mutate it, since replacing it
                    # would drop whatever else the caller set on it.
                    options.base_url = _NOTION
                    if _TOKEN:
                        options.auth = _TOKEN
                original(self, *args, **kwargs)

            cls.__init__ = __init__

        for _name in ("Client", "AsyncClient"):
            _cls = getattr(notion_client, _name, None)
            if _cls is not None:
                _patch(_cls)
