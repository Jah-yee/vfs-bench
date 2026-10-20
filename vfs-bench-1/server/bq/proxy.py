#!/usr/bin/env python
import argparse
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# What the emulator says, and what BigQuery would have said. Both spellings
# describe a query the server could not run; only the second tells the client
# that running it again will not help.
WRONG = "jobInternalError"
RIGHT = "invalidQuery"
# Every caller gives a query up after 30 s: upstream's google-cloud MCP
# config sets `client_session_timeout_seconds: 30`, and the VFS arm's
# google-cloud CLI waits as long. The emulator runs one query at a time and
# stops one only when its caller hangs up, so a query this proxy kept waiting
# past that would hold every later query behind a result nobody reads.
DEADLINE = 30
TIMEOUT = {
    "message": "The job timed out.",
    "domain": "global",
    "reason": "timeout"
}
TIMED_OUT = json.dumps({
    "error": {
        "code": 400,
        "message": TIMEOUT["message"],
        "errors": [TIMEOUT],
        "status": "INVALID_ARGUMENT"
    }
}).encode()
# Hop-by-hop headers belong to one connection and must not be forwarded.
DROP = {
    "connection", "keep-alive", "transfer-encoding", "upgrade",
    "proxy-authenticate", "proxy-authorization", "te", "trailers",
    "content-length", "content-encoding"
}

# A job's times, which BigQuery gives in milliseconds and the emulator in
# seconds. The client reads them as milliseconds, so a job it types comes
# back created in 1970, and one it cannot type fails on the string outright.
JOB_TIMES = ("creationTime", "startTime", "endTime")
# Seconds until the year 2286; a time in milliseconds has thirteen digits.
SECONDS = re.compile(r"\d{1,11}")
# A query job's byte counts: processed on the job and on its query
# statistics, billed on the latter. The emulator sets all three on every
# query job, dry run or not, but its Go structs drop an int64 that is zero,
# so a query that scanned nothing reaches the client as None where BigQuery
# says "0". Upstream's server prints the None, and divides by it on a dry
# run.
QUERY_BYTES = ("totalBytesProcessed", "totalBytesBilled")
JOBS = re.compile(r"/projects/(?P<project>[^/?]+)/jobs(?:/(?P<job>[^/?]+))?"
                  r"(?:\?|$)")
DATASETS = re.compile(r"/projects/(?P<project>[^/?]+)/datasets"
                      r"(?:/(?P<dataset>[^/?]+))?(?:\?|$)")
# What an insert says about a dataset that `datasets.get` gives back on
# BigQuery and the emulator drops, keeping only the reference.
DATASET_FIELDS = ("description", "location", "friendlyName", "labels",
                  "defaultTableExpirationMs", "defaultPartitionExpirationMs")

# Only relation tokens are replaced, never SQL inside literals/comments.
# Metadata is read afresh from the emulator, so writes by either arm appear.
SQL_TOKEN = re.compile(
    r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|--[^\n]*|/\*.*?\*/"
    r"|`[^`]+`", re.DOTALL)
INFORMATION_VIEW = re.compile(
    r"(?:(?P<project>[\w-]+)\.)?(?P<dataset>\w+)"
    r"\.INFORMATION_SCHEMA\.(?P<view>TABLES|COLUMNS)")


def tables(upstream: str, project: str, dataset: str) -> list[dict]:
    """Read every table in one dataset from the emulator's live catalog."""
    base = (f"{upstream}/bigquery/v2/projects/"
            f"{urllib.parse.quote(project, safe='')}/datasets/"
            f"{urllib.parse.quote(dataset, safe='')}/tables")
    rows, page = [], ""
    while True:
        suffix = "?" + urllib.parse.urlencode({"pageToken": page
                                               }) if page else ""
        listing = json.loads(fetch(base + suffix))
        rows.extend(listing.get("tables", []))
        page = listing.get("nextPageToken", "")
        if not page:
            return rows


def tables_relation(upstream: str, project: str, dataset: str) -> str:
    """Expose TABLES identity/type columns from the emulator's live catalog.

    This is a partial INFORMATION_SCHEMA view: unsupported metadata columns
    still fail explicitly. Query projection, filtering, ordering and limits
    remain the emulator's SQL engine's responsibility.
    """
    rows = []
    for table in tables(upstream, project, dataset):
        ref = table["tableReference"]
        kind = table["type"]
        # REST TABLE corresponds to INFORMATION_SCHEMA's BASE TABLE.
        kind = {
            "TABLE": "BASE TABLE",
            "MATERIALIZED_VIEW": "MATERIALIZED VIEW"
        }.get(kind, kind)
        values = (ref["projectId"], ref["datasetId"], ref["tableId"], kind)
        fields = ("table_catalog", "table_schema", "table_name", "table_type")
        rows.append("STRUCT(" +
                    ", ".join(f"{json.dumps(value)} AS {field}"
                              for value, field in zip(values, fields)) + ")")
    schema = ("ARRAY<STRUCT<table_catalog STRING, table_schema STRING, "
              "table_name STRING, table_type STRING>>")
    return "UNNEST(" + schema + "[" + ", ".join(rows) + "])"


def google_type(field: dict) -> str:
    """Render a REST table-field schema type as its GoogleSQL name."""
    kind = str(field.get("type", "STRING")).upper()
    kind = {
        "BOOLEAN": "BOOL",
        "FLOAT": "FLOAT64",
        "INTEGER": "INT64",
        "RECORD": "STRUCT",
    }.get(kind, kind)
    if kind == "STRUCT":
        nested = field.get("fields") or []
        if nested:
            kind += "<" + ", ".join(
                f"`{child['name'].replace('`', '``')}` {google_type(child)}"
                for child in nested) + ">"
    if field.get("mode") == "REPEATED":
        kind = f"ARRAY<{kind}>"
    return kind


def columns_relation(upstream: str, project: str, dataset: str) -> str:
    """Expose the core COLUMNS fields from every live table schema."""
    rows = []
    for table in tables(upstream, project, dataset):
        ref = table["tableReference"]
        quoted = [
            urllib.parse.quote(ref[key], safe="")
            for key in ("projectId", "datasetId", "tableId")
        ]
        described = json.loads(
            fetch(f"{upstream}/bigquery/v2/projects/{quoted[0]}"
                  f"/datasets/{quoted[1]}/tables/{quoted[2]}"))
        for ordinal, field in enumerate(
                described.get("schema", {}).get("fields", []), 1):
            values = (
                json.dumps(ref["projectId"]),
                json.dumps(ref["datasetId"]),
                json.dumps(ref["tableId"]),
                json.dumps(field["name"]),
                str(ordinal),
                json.dumps("YES" if field.get("mode", "NULLABLE") ==
                           "NULLABLE" else "NO"),
                json.dumps(google_type(field)),
            )
            fields = ("table_catalog", "table_schema", "table_name",
                      "column_name", "ordinal_position", "is_nullable",
                      "data_type")
            rows.append("STRUCT(" +
                        ", ".join(f"{value} AS {name}"
                                  for value, name in zip(values, fields)) +
                        ")")
    schema = ("ARRAY<STRUCT<table_catalog STRING, table_schema STRING, "
              "table_name STRING, column_name STRING, ordinal_position "
              "INT64, is_nullable STRING, data_type STRING>>")
    return "UNNEST(" + schema + "[" + ", ".join(rows) + "])"


def catalog_query(query: str, upstream: str, project: str) -> str:
    """Resolve quoted dataset TABLES views using the request's project."""

    def replace(match: re.Match) -> str:
        token = match.group(0)
        view = (INFORMATION_VIEW.fullmatch(token[1:-1])
                if token[0] == "`" else None)
        if not view:
            return token
        prefix = SQL_TOKEN.sub(lambda m: " " * len(m.group(0)),
                               query[:match.start()])
        if not re.search(r"\b(?:FROM|JOIN)\s*$", prefix, re.IGNORECASE):
            return token
        target_project = view.group("project") or project
        if view.group("view") == "TABLES":
            return tables_relation(upstream, target_project,
                                   view.group("dataset"))
        return columns_relation(upstream, target_project,
                                view.group("dataset"))

    return SQL_TOKEN.sub(replace, query)


def catalog_body(body: bytes | None, path: str, upstream: str) -> bytes | None:
    """Rewrite query jobs and synchronous queries through the same catalog."""
    route = re.search(r"/projects/([^/]+)/(?:jobs|queries)$",
                      path.split("?", 1)[0])
    if not body or not route:
        return body
    document = json.loads(body)
    config = document.get("configuration", {}).get("query", document)
    query = config.get("query")
    if not isinstance(query, str) or config.get("useLegacySql") is True:
        return body
    rewritten = catalog_query(query, upstream, urllib.parse.unquote(route[1]))
    if rewritten == query:
        return body
    config["query"] = rewritten
    return json.dumps(document).encode()


def relabel(payload: bytes) -> bytes:
    """Rewrite a job's error reason, if it has the wrong one.

    Args:
        payload (bytes): the upstream response body.

    Returns:
        bytes: the body, with `jobInternalError` corrected wherever it
            appears in a job status. Anything that is not JSON, or has no
            such reason, is returned byte-identical.
    """
    if WRONG.encode() not in payload:
        return payload
    try:
        document = json.loads(payload)
    except ValueError:
        return payload

    changed = False

    def walk(node: object) -> None:
        """Correct every `reason` under a `status` block, in place."""
        nonlocal changed
        if isinstance(node, dict):
            if node.get("reason") == WRONG:
                node["reason"] = RIGHT
                changed = True
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(document)
    return json.dumps(document).encode() if changed else payload


def job_times(job: dict) -> None:
    """Give a job's times in milliseconds, as BigQuery does, in place.

    Args:
        job (dict): one job resource.
    """
    statistics = job.get("statistics")
    if not isinstance(statistics, dict):
        return
    for key in JOB_TIMES:
        value = statistics.get(key)
        if isinstance(value, str) and SECONDS.fullmatch(value):
            statistics[key] = str(int(value) * 1000)


def query_bytes(job: dict) -> None:
    """Give a query job the byte counts its zeros lost, in place.

    Args:
        job (dict): one job resource.
    """
    statistics = job.get("statistics")
    if not isinstance(statistics, dict) or not isinstance(
            statistics.get("query"), dict):
        return
    statistics.setdefault(QUERY_BYTES[0], "0")
    for key in QUERY_BYTES:
        statistics["query"].setdefault(key, "0")


def configure_listing(document: dict, upstream: str, project: str) -> None:
    """Give each listed job its configuration, in place.

    `jobs.list` with `projection=full`, which is what the client asks for,
    includes each job's configuration on BigQuery. The emulator leaves it
    out, so the client cannot tell a query job from any other and builds
    an `UnknownJob`, which keeps the times as strings. `jobs.get` has it.

    Args:
        document (dict): the `jobs.list` answer.
        upstream (str): the emulator's base URL.
        project (str): the project the jobs are listed in.
    """
    for job in document.get("jobs") or []:
        if job.get("configuration"):
            continue
        job_id = (job.get("jobReference") or {}).get("jobId")
        if not job_id:
            continue
        # One job the emulator cannot describe leaves that entry as the
        # emulator gave it, not the whole listing failed. `OSError` covers
        # a refused connection and a reply that timed out mid-read, which
        # is a `TimeoutError` and not a `URLError`.
        try:
            found = json.loads(
                fetch(f"{upstream}/bigquery/v2/projects/"
                      f"{urllib.parse.quote(project, safe='')}/jobs/"
                      f"{urllib.parse.quote(job_id, safe='')}"))
        except (OSError, ValueError):
            continue
        if isinstance(found, dict) and found.get("configuration"):
            job["configuration"] = found["configuration"]


class DatasetRecords:
    """What each dataset's insert said, kept for `datasets.get`.

    BigQuery answers `datasets.get` with the fields the insert set, the
    dataset's id and its creation and modification times. The emulator
    keeps only the reference, so upstream's own preprocess sets a
    description and a location that no reader sees. The proxy relays every
    insert, so it keeps them here.
    """

    def __init__(self) -> None:
        self.kept: dict[tuple[str, str], dict] = {}
        self.lock = threading.Lock()

    def inserted(self, method: str, project: str, body: bytes | None,
                 dataset: str | None) -> None:
        """Record an insert or an update the emulator accepted.

        `datasets.update` (PUT) replaces the resource, so a field it leaves
        out is gone; `datasets.patch` merges, and a field it sends as null
        is cleared -- a label too, which is how the client removes one.

        Args:
            method (str): POST, PUT or PATCH.
            project (str): the project in the path.
            body (bytes | None): the request body.
            dataset (str | None): the dataset in the path; None for an
                insert, whose body names it.
        """
        try:
            sent = json.loads(body or b"{}")
        except ValueError:
            return
        dataset = dataset or (sent.get("datasetReference")
                              or {}).get("datasetId")
        if not dataset:
            return
        now = str(int(time.time() * 1000))
        with self.lock:
            record = self.kept.setdefault((project, dataset),
                                          {"creationTime": now})
            if method != "PATCH":
                for key in DATASET_FIELDS:
                    record.pop(key, None)
            for key in DATASET_FIELDS:
                if key not in sent:
                    continue
                value = sent[key]
                if key == "labels" and isinstance(value, dict):
                    value = {
                        name: label
                        for name, label in {
                            **(record.get(key) or {}),
                            **value
                        }.items() if label is not None
                    }
                if value is None:
                    record.pop(key, None)
                else:
                    record[key] = value
            record["lastModifiedTime"] = now

    def deleted(self, project: str, dataset: str) -> None:
        """Forget a dataset the emulator deleted.

        Args:
            project (str): the project in the path.
            dataset (str): the dataset in the path.
        """
        with self.lock:
            self.kept.pop((project, dataset), None)

    def complete(self, document: dict, project: str, dataset: str) -> None:
        """Add what BigQuery would have said about the dataset, in place.

        Args:
            document (dict): the emulator's dataset resource.
            project (str): the project in the path.
            dataset (str): the dataset in the path.
        """
        document.setdefault("kind", "bigquery#dataset")
        document.setdefault("id", f"{project}:{dataset}")
        with self.lock:
            for key, value in self.kept.get((project, dataset), {}).items():
                document.setdefault(key, value)


def completed(payload: bytes, method: str, path: str, body: bytes | None,
              upstream: str, datasets: DatasetRecords) -> bytes:
    """A successful answer with what the emulator leaves out put back.

    Args:
        payload (bytes): the emulator's answer.
        method (str): the request's method.
        path (str): the request's path, query string included.
        body (bytes | None): the request's body.
        upstream (str): the emulator's base URL.
        datasets (DatasetRecords): the datasets' inserts.

    Returns:
        bytes: the answer, byte-identical when nothing was added.
    """
    jobs, sets = JOBS.search(path), DATASETS.search(path)
    if not (jobs or sets):
        return payload
    if sets and method == "DELETE" and sets["dataset"]:
        datasets.deleted(sets["project"], sets["dataset"])
        return payload
    try:
        document = json.loads(payload)
    except ValueError:
        return payload
    if not isinstance(document, dict):
        return payload
    if jobs:
        listed = document.get("jobs")
        if (method == "GET" and not jobs["job"]
                and "projection=full" in path.partition("?")[2]):
            configure_listing(document, upstream, jobs["project"])
        for job in listed if isinstance(listed, list) else [document]:
            job_times(job)
            query_bytes(job)
        return json.dumps(document).encode()
    if method in ("POST", "PATCH", "PUT"):
        datasets.inserted(method, sets["project"], body, sets["dataset"])
    dataset = sets["dataset"] or (document.get("datasetReference")
                                  or {}).get("datasetId")
    if method != "GET" or sets["dataset"]:
        if dataset:
            datasets.complete(document, sets["project"], dataset)
    return json.dumps(document).encode()


def fetch(url: str,
          method: str = "GET",
          body: bytes | None = None,
          content_type: str = "application/json") -> bytes:
    """One request the proxy makes on its own behalf.

    Args:
        url (str): the absolute URL.
        method (str): the HTTP method.
        body (bytes | None): the request body, if any.
        content_type (str): its media type.

    Returns:
        bytes: the response body.

    Raises:
        urllib.error.URLError: the call failed; callers decide what that
            means, because a header that cannot be restored must not take
            the export down with it.
    """
    request = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", content_type)
    with urllib.request.urlopen(request, timeout=60) as reply:
        return reply.read()


def runs_query(command: str, path: str, body: bytes | None) -> bool:
    """Whether a request runs SQL: `jobs.query`, or a query job's insert.

    Loads and extracts are left unbounded: seeding loads through here too,
    and nothing queues behind them the way it does behind a query.
    """
    if command != "POST":
        return False
    path = path.split("?", 1)[0]
    if path.endswith("/queries"):
        return True
    if not path.endswith("/jobs"):
        return False
    try:
        return "query" in json.loads(body or b"{}").get("configuration", {})
    except ValueError:
        return False


def header_line(upstream: str, table: dict, delimiter: str) -> str:
    """The column names of one table, as an extract's first line.

    Args:
        upstream (str): the emulator's base URL.
        table (dict): the job's `sourceTable` reference.
        delimiter (str): the extract's field delimiter.

    Returns:
        str: the header, with no trailing newline.
    """
    quoted = [
        urllib.parse.quote(table[key], safe="")
        for key in ("projectId", "datasetId", "tableId")
    ]
    described = json.loads(
        fetch(f"{upstream}/bigquery/v2/projects/{quoted[0]}"
              f"/datasets/{quoted[1]}/tables/{quoted[2]}"))
    return delimiter.join(field["name"]
                          for field in described["schema"]["fields"])


def objects_for(storage: str, uri: str) -> list[tuple[str, str]]:
    """The stored objects one destination URI names.

    A `gs://bucket/prefix-*.csv` writes one object per shard, so the
    wildcard is resolved against what is actually in the bucket rather than
    guessed at.

    Args:
        storage (str): the Cloud Storage fake's base URL.
        uri (str): a `gs://` destination URI.

    Returns:
        list[tuple[str, str]]: `(bucket, object name)` pairs.
    """
    bucket, _, name = uri[len("gs://"):].partition("/")
    if "*" not in name:
        return [(bucket, name)]
    prefix = name.split("*", 1)[0]
    query = urllib.parse.urlencode({"prefix": prefix})
    listing = json.loads(
        fetch(f"{storage}/storage/v1/b/{urllib.parse.quote(bucket)}"
              f"/o?{query}"))
    return [(bucket, item["name"]) for item in listing.get("items", [])]


def prepend(storage: str, bucket: str, name: str, line: str) -> None:
    """Put a header line at the front of one stored object.

    Args:
        storage (str): the Cloud Storage fake's base URL.
        bucket (str): the bucket.
        name (str): the object.
        line (str): the header, with no trailing newline.
    """
    quoted = urllib.parse.quote(bucket), urllib.parse.quote(name, safe="")
    body = fetch(f"{storage}/storage/v1/b/{quoted[0]}/o/{quoted[1]}"
                 f"?alt=media")
    if body.startswith(line.encode() + b"\n"):
        return
    query = urllib.parse.urlencode({"uploadType": "media", "name": name})
    fetch(f"{storage}/upload/storage/v1/b/{quoted[0]}/o?{query}",
          method="POST",
          body=line.encode() + b"\n" + body,
          content_type="application/octet-stream")


class Proxy(BaseHTTPRequestHandler):
    """Forwards everything; puts back on the way what BigQuery would say."""

    protocol_version = "HTTP/1.1"
    upstream = "http://127.0.0.1:9050"
    storage = "http://127.0.0.1:9070"
    datasets = DatasetRecords()

    def restore_header(self, body: bytes | None) -> None:
        """Put back the header line an extract job should have written.

        Called after the job has been forwarded and has come back without
        an error, at which point the emulator has already uploaded. Any
        failure here is reported and swallowed: the export itself
        succeeded, and taking it down because the header could not be
        restored would trade a gradeable artefact for none at all.

        Args:
            body (bytes | None): the request body the client posted.
        """
        try:
            config = json.loads(body or b"{}").get("configuration", {})
            extract = config.get("extract")
            if not extract:
                return
            if extract.get("destinationFormat", "CSV") != "CSV":
                return
            if extract.get("printHeader") is False:
                return
            if extract.get("compression", "NONE") not in ("NONE", ""):
                return
            delimiter = extract.get("fieldDelimiter") or ","
            line = header_line(self.upstream, extract["sourceTable"],
                               delimiter)
            uris = extract.get("destinationUris") or []
            if extract.get("destinationUri"):
                uris = [*uris, extract["destinationUri"]]
            for uri in uris:
                for bucket, name in objects_for(self.storage, uri):
                    prepend(self.storage, bucket, name, line)
        except Exception as failure:  # noqa: BLE001 - see the docstring
            print(
                f"bq_proxy: could not restore the extract header: "
                f"{failure}",
                file=sys.stderr,
                flush=True)

    def relay(self) -> None:
        """Pass one request upstream and return its answer."""
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        try:
            if self.command == "POST":
                body = catalog_body(body, self.path, self.upstream)
        except urllib.error.HTTPError as failure:
            payload = failure.read()
            self.send_response(failure.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        except urllib.error.URLError as failure:
            self.send_error(502, f"upstream unreachable: {failure.reason}")
            return
        headers = {
            k: v
            for k, v in self.headers.items() if k.lower() not in DROP
        }
        request = urllib.request.Request(f"{self.upstream}{self.path}",
                                         data=body,
                                         headers=headers,
                                         method=self.command)
        deadline = (DEADLINE
                    if runs_query(self.command, self.path, body) else None)
        try:
            with urllib.request.urlopen(request, timeout=deadline) as response:
                status, payload = response.status, response.read()
                out = dict(response.headers)
        except TimeoutError:
            # Closing the connection is what makes the emulator interrupt
            # the query; `timeout` is BigQuery's reason for a job that ran
            # out of time, and its client does not retry it.
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(TIMED_OUT)))
            self.end_headers()
            self.wfile.write(TIMED_OUT)
            return
        except urllib.error.HTTPError as failure:
            status, payload = failure.code, failure.read()
            out = dict(failure.headers)
        except urllib.error.URLError as failure:
            self.send_error(502, f"upstream unreachable: {failure.reason}")
            return

        payload = relabel(payload)
        if status < 400:
            payload = completed(payload, self.command, self.path, body,
                                self.upstream, self.datasets)
        # The path carries `?prettyPrint=false`, so the query string comes
        # off before the comparison.
        if (self.command == "POST" and status < 400
                and self.path.split("?", 1)[0].endswith("/jobs")):
            self.restore_header(body)
        self.send_response(status)
        for key, value in out.items():
            if key.lower() not in DROP:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = relay

    def log_message(self, *_args) -> None:
        """Stay quiet; the harness prints its own progress."""


def main() -> int:
    """Entry point.

    Returns:
        int: process exit status.
    """
    parser = argparse.ArgumentParser(
        description='Make the BigQuery emulator fail the way BigQuery fails.')
    parser.add_argument("--listen", type=int, default=9051)
    parser.add_argument("--upstream",
                        default="9050",
                        help="the emulator: a port when it shares this "
                        "host, a base URL when it does not")
    parser.add_argument("--storage",
                        default="http://127.0.0.1:9070",
                        help="the Cloud Storage fake an extract job writes "
                        "to, whose objects need their header put back")
    parser.add_argument("--bind",
                        default="127.0.0.1",
                        help="0.0.0.0 in a container, where binding the "
                        "loopback would publish a port nothing answers on")
    args = parser.parse_args()

    # A bare port still means loopback, which is every host invocation; a
    # URL is what compose needs, where the emulator is a separate container
    # reached by service name.
    Proxy.upstream = (args.upstream.rstrip("/") if "://" in args.upstream else
                      f"http://127.0.0.1:{args.upstream}")
    Proxy.storage = args.storage.rstrip("/")
    # Threaded: the MCP server and an evaluator can be in flight together,
    # and a single-threaded proxy would serialise them into a timeout.
    server = ThreadingHTTPServer((args.bind, args.listen), Proxy)
    print(f"BIGQUERY_EMULATOR_HOST=http://127.0.0.1:{args.listen}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
