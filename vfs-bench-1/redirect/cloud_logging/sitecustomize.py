import importlib.util
import os
import sys
from pathlib import Path

# The package is registered from its own files rather than found on
# sys.path: inside the runtime boundary the repository root is readable but
# not listable, and a path finder lists a directory before it looks inside.
REPO = Path(__file__).resolve().parents[2]
for name, folder in (('server', REPO / 'server'), ('server.clients',
                                                   REPO / 'server/clients')):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            name,
            folder / '__init__.py',
            submodule_search_locations=[str(folder)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)

# The store itself lives behind server/api/app.py;
# `server/clients/cloud_logging.py` is
# the stdlib HTTP client on the task's own /api/<task>/logging endpoint. The
# gapic-facing classes below cannot move there: neither client library
# honours an endpoint override, so replacing the transport at interpreter
# start-up is still the only door -- but the replacement is a thin client,
# and the filter parser runs in exactly one place, the server.
from server.clients import cloud_logging as store  # noqa: E402


class StoreLoggingAPI:
    """The transport `Client.logging_api` hands to loggers and queries.

    Attributes:
        _client: the client that owns it, needed to build entry objects.
    """

    def __init__(self, client) -> None:
        self._client = client

    def list_entries(self,
                     resource_names,
                     *,
                     filter_=None,
                     order_by=None,
                     max_results=None,
                     page_size=None,
                     page_token=None):
        """Return a generator of entries, as the gRPC transport does.

        `page_size` and `page_token` are accepted and ignored: they page an
        answer the caller receives one entry at a time either way, and this
        store has no pages.

        Args:
            resource_names (Sequence[str]): `projects/P` and friends; an
                entry outside them is not visible to the query.
            filter_ (str | None): an advanced filter.
            order_by (str | None): `timestamp asc` or `timestamp desc`.
            max_results (int | None): cap on the number returned.
            page_size (int | None): ignored.
            page_token (str | None): ignored.

        Returns:
            Generator: the matching entries.
        """
        from google.cloud.logging_v2._helpers import entry_from_resource

        rows = store.select(filter_, order_by, max_results)
        scopes = tuple(f"{name}/logs/" for name in (resource_names or []))
        loggers: dict = {}

        def pager():
            for row in rows:
                name = row.get("logName") or ""
                if scopes and not name.startswith(scopes):
                    continue
                yield entry_from_resource(row, self._client, loggers=loggers)

        return pager()

    def write_entries(self,
                      entries,
                      *,
                      logger_name=None,
                      resource=None,
                      labels=None,
                      partial_success=True,
                      dry_run=False):
        """Append entries to the store.

        Args:
            entries (Sequence[Mapping]): entries in `LogEntry` API form.
            logger_name (str | None): request-level default log name.
            resource: request-level default monitored resource.
            labels (Mapping | None): request-level labels.
            partial_success (bool): accepted; nothing here rejects an entry.
            dry_run (bool): if set, validate and store nothing.
        """
        if dry_run:
            return
        # A request-level Resource is an object; it has to be plain before
        # it crosses HTTP. Entries are already in API form.
        plain = (resource._to_dict()
                 if hasattr(resource, "_to_dict") else resource)
        store.write(list(entries), logger_name, plain, labels)

    def logger_delete(self, logger_name):
        """Drop every entry of one log, as `Logger.delete` does.

        Args:
            logger_name (str): the full `projects/P/logs/NAME` form.
        """
        store.delete_log(logger_name)


def bucket_name(request, keyword) -> str:
    """The resource name one config-service call addresses.

    Callers spell these three ways -- a dict, a proto request, or a keyword
    -- and upstream's preprocess uses two of them in the same file.

    Args:
        request: the positional request, a dict or a proto or None.
        keyword (str | None): the keyword form, if it was used.

    Returns:
        str: the resource name, or "".
    """
    if keyword:
        return keyword
    if isinstance(request, dict):
        return request.get("name") or request.get("parent") or ""
    return getattr(request, "name", "") or getattr(request, "parent", "")


def as_bucket(name: str, fields: dict):
    """One stored bucket as the proto the caller expects back.

    Args:
        name (str): the full resource name.
        fields (dict): the stored settings.

    Returns:
        LogBucket: the message.
    """
    from google.cloud.logging_v2.types import LifecycleState, LogBucket
    return LogBucket(
        name=name,
        description=fields.get("description", ""),
        retention_days=int(fields.get("retention_days", 30)),
        # Upstream's own preprocess skips a bucket whose lifecycle_state is
        # not ACTIVE, so leaving this at the proto default of UNSPECIFIED
        # would make every fixture bucket invisible to the code that made
        # it.
        lifecycle_state=LifecycleState.ACTIVE,
    )


def install_config_service() -> None:
    """Answer the five log-bucket calls out of the store."""
    from google.api_core import exceptions
    from google.cloud.logging_v2.services.config_service_v2 import \
        ConfigServiceV2Client

    def list_buckets(self, request=None, *, parent=None, **_kwargs):
        """Every bucket under one parent; `locations/-` matches all.

        Args:
            request: a `ListBucketsRequest` or dict.
            parent (str | None): the keyword form.

        Returns:
            list: the buckets, which is what every caller iterates.
        """
        scope = bucket_name(request, parent)
        prefix = scope.replace("/locations/-", "/locations/")
        return [
            as_bucket(name, fields)
            for name, fields in sorted(store.buckets().items())
            if name.startswith(prefix)
        ]

    def get_bucket(self, request=None, *, name=None, **_kwargs):
        """One bucket.

        Args:
            request: a `GetBucketRequest` or dict.
            name (str | None): the keyword form.

        Returns:
            LogBucket: the bucket.

        Raises:
            NotFound: there is no such bucket, which is the branch
                upstream's preprocess catches to decide whether to create.
        """
        full = bucket_name(request, name)
        fields = store.buckets().get(full)
        if fields is None:
            raise exceptions.NotFound(f"log bucket {full} not found")
        return as_bucket(full, fields)

    def create_bucket(self, request=None, **_kwargs):
        """Create one bucket under `parent` with id `bucket_id`.

        Args:
            request: a `CreateBucketRequest` or dict.

        Returns:
            LogBucket: the new bucket.

        Raises:
            AlreadyExists: a bucket of that name is already there.
        """
        if isinstance(request, dict):
            parent = request.get("parent", "")
            bucket_id = request.get("bucket_id", "")
            body = request.get("bucket")
        else:
            parent = getattr(request, "parent", "")
            bucket_id = getattr(request, "bucket_id", "")
            body = getattr(request, "bucket", None)
        full = f"{parent}/buckets/{bucket_id}"
        if full in store.buckets():
            raise exceptions.AlreadyExists(f"log bucket {full} exists")
        store.put_bucket(
            full, {
                "retention_days": int(
                    getattr(body, "retention_days", 0) or 30),
                "description": getattr(body, "description", "") or "",
            })
        return as_bucket(full, store.buckets()[full])

    def update_bucket(self, request=None, **_kwargs):
        """Replace one bucket's settings.

        Args:
            request: an `UpdateBucketRequest` or dict.

        Returns:
            LogBucket: the bucket as it now stands.

        Raises:
            NotFound: there is no such bucket.
        """
        full = bucket_name(request, None)
        fields = store.buckets().get(full)
        if fields is None:
            raise exceptions.NotFound(f"log bucket {full} not found")
        body = (request.get("bucket") if isinstance(request, dict) else
                getattr(request, "bucket", None))
        if getattr(body, "retention_days", 0):
            fields["retention_days"] = int(body.retention_days)
        if getattr(body, "description", ""):
            fields["description"] = body.description
        store.put_bucket(full, fields)
        return as_bucket(full, fields)

    def delete_bucket(self, request=None, *, name=None, **_kwargs):
        """Delete one bucket.

        Args:
            request: a `DeleteBucketRequest` or dict.
            name (str | None): the keyword form.

        Raises:
            NotFound: there is no such bucket.
        """
        full = bucket_name(request, name)
        if not store.drop_bucket(full):
            raise exceptions.NotFound(f"log bucket {full} not found")

    def list_sinks(self, request=None, *, parent=None, **_kwargs):
        """No sinks, because this environment's logging has none.

        Not a stub for something unimplemented: the fake stores buckets and
        entries, a sink is neither, and a project with no sinks answers
        exactly this. What makes it necessary is that a caller can reach
        `list_sinks` without meaning to. `logging_list_logs` lists the
        buckets, then lists the sinks to show which route where -- so the
        one unpatched method turned the whole tool into `401 Request had
        invalid authentication credentials`, from the real Cloud Logging,
        for an agent that only wanted the name of a bucket.

        The cost of that lands somewhere unrecognisable.
        `live-transactions` says "the log bucket whose name prefixed by
        Trading_Logging", so listing is how the full name is found. The MCP
        arm could not list, guessed the bare prefix, and was denied by the
        allow-list gate -- reported as an agent that failed to write the
        entry rather than as a harness that hid the name from it.

        Args:
            request: a `ListSinksRequest` or dict.
            parent (str | None): the keyword form.

        Returns:
            list: empty, which is what every caller iterates.
        """
        return []

    # The constructor is left doing its real work -- a gRPC channel is lazy,
    # so it costs nothing and no call ever reaches it -- apart from the
    # credential it insists on.
    anonymous(ConfigServiceV2Client)
    # Exclusions and views are still not replaced -- no ported task reaches
    # one, and a stub that answered them would be inventing behaviour
    # nothing has checked. Sinks used to be in that sentence; the premise
    # expired the moment a task called `logging_list_logs`.
    ConfigServiceV2Client.list_buckets = list_buckets
    ConfigServiceV2Client.get_bucket = get_bucket
    ConfigServiceV2Client.create_bucket = create_bucket
    ConfigServiceV2Client.update_bucket = update_bucket
    ConfigServiceV2Client.delete_bucket = delete_bucket
    ConfigServiceV2Client.list_sinks = list_sinks


def anonymous(cls) -> None:
    """Let one client class be built without a credential.

    Nothing here is authenticated, and both client classes call
    `google.auth.default()` when handed no credential, which raises on a
    machine that has none. Same substitution `STORAGE_EMULATOR_HOST` makes
    for Cloud Storage; a caller that passes a real credential keeps it.

    Args:
        cls (type): the client class to patch.
    """
    original = cls.__init__

    def __init__(self, *args, **kwargs):
        """Construct, defaulting the credential the fake does not check.

        Args:
            *args: as the real constructor.
            **kwargs: as the real constructor.
        """
        if kwargs.get("credentials") is None:
            from google.auth.credentials import AnonymousCredentials
            kwargs["credentials"] = AnonymousCredentials()
        original(self, *args, **kwargs)

    cls.__init__ = __init__


def install() -> None:
    """Replace the logging transport and the log-bucket calls."""
    from google.cloud.logging_v2.client import Client
    from google.oauth2.service_account import Credentials

    def logging_api(self):
        """The store-backed transport, built once per client.

        Returns:
            StoreLoggingAPI: the transport.
        """
        if getattr(self, "_shim_logging_api", None) is None:
            self._shim_logging_api = StoreLoggingAPI(self)
        return self._shim_logging_api

    Client.logging_api = property(logging_api)
    anonymous(Client)
    # Recent google-auth releases start a background
    # iamcredentials.googleapis.com `allowedLocations` lookup after the
    # local token refresh. The fixture has no regional access boundary and
    # the request is unrelated to Cloud Logging, so keep the unchanged MCP
    # server entirely on its declared local transports.
    Credentials._is_regional_access_boundary_lookup_required = lambda _: False
    install_config_service()


if os.environ.get(store.ENV):
    install()
