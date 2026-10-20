# Machine operating

An hour of IoT sensor readings sits in BigQuery and the normal range for
every machine's every sensor sits in an xlsx. Find the readings outside
their range, write them to `anomaly_report.csv`, and upload that to the
existing Cloud Storage bucket whose name starts `iot_anomaly_reports`.

## The first task to use two thirds of `google-cloud`

`flagged-transactions` and `game-statistics` reach only BigQuery — their own
`token_key_session.py` sets `google_cloud_allowed_buckets` to `"null"`, so
upstream launches the server with the storage tools switched off. This one
sets it to a real bucket, and so it is the first task where the mirage arm
needs the storage tools as well.

    google-cloud storage-list-buckets
    google-cloud storage-create-bucket '{"bucket_name":"B"}'
    google-cloud storage-list-objects '{"bucket_name":"B","prefix":"P"}'
    google-cloud storage-upload-file '{"bucket_name":"B","source_file_path":"/work/N","destination_blob_name":"N"}'
    google-cloud storage-download-file '{"bucket_name":"B","source_blob_name":"N","destination_file_path":"/work/N"}'

Buckets and blobs *are* path-shaped, and by the argument
`task/toolathlon/flagged-transactions/README.md` makes about warehouses they should
have been a mount rather than a verb tree. They are not, for a reason that
belongs to the fake rather than to the design:
[`fsouza/fake-gcs-server`](https://github.com/fsouza/fake-gcs-server) serves
the GCS JSON API and only a **read** slice of the S3-compatible XML API —
probed directly, listing and GET answer and PUT returns 400 — and mirage's
`gcs` VFS is `S3VFS` underneath. A mount would have given the
agent a bucket it could read and not write, which is worse than no mount.
The mount goes in the day the fake grows an S3 writer.

Bodies travel on stdin and stdout rather than as path operands, which is
what keeps the CLI out of the filesystem entirely. A path would have to be
translated from the agent's virtual path to whatever the host calls it, and
then the two arms would disagree about which files are reachable. A pipe is
the shell's own answer and needs no mapping:

    cat /work/anomaly_report.csv | gcs upload --bucket b --name anomaly_report.csv

## The fixture pointed at the wrong CSV

Upstream ships two sensor files, and only one of them is the fixture:

| file | rows | what it is |
|---|---:|---|
| `preprocess/live_sensor_data.csv` | 1,500 | what `preprocess/main.py` loads into BigQuery |
| `preprocess/machine_operating/live_sensor.csv` | 311,400 | a different, larger generation run |

`shared/bigquery.json` named the second. The rows look identical in shape
and the task runs fine against either — which is exactly what made it worth
catching, because the answers are not the same. The committed ground truth's
first anomaly is at `11:33:59.878906` and the 311k file's first in-window
reading is at `11:32:08.269059`, 111 seconds away from it; the evaluator
matches within 60. Every row would have missed, on a fixture that loaded
cleanly and queried cleanly.

With the right CSV the port reproduces upstream's ground truth **exactly**:
720 readings in the 11:30–12:30 window, 337 of them outside their range, the
same 337 rows the committed `anomaly_report.csv` holds.
A golden solver derived that through the
mirage surface — `bq query
--format=csv` into a file, openpyxl over the workbook inside pyodide, `gcs
upload` from a pipe — and then reads the object back through the CLI rather
than off disk, because what the evaluator grades is the object and an upload
that reported success and stored nothing would pass every other check.

`timestamp` stays a STRING, as it is in `flagged-transactions`. Nothing
upstream pins the type here, so the rule in `server/seed/seed_bigquery.py` decides
it, and the sibling task is the evidence for that rule: its `txn_time` is
equally timestamp-shaped and BigQuery's `autodetect=True` left it a string —
upstream's own preprocess proves it by reading the column back with
`PARSE_DATETIME`, a type error against a TIMESTAMP.

## Two more emulator defects, both on the MCP arm only

`flagged-transactions` found the emulator mislabelling a user SQL error as a
transient internal one, and wrote down why it had to be fixed rather than
noted: it was invisible to the arm whose CLI posts to `/queries` and fatal
to the arm that uses the job API. This task found two more of the same
shape, and the second is the more interesting one.

**The emulator uploads an extract to the real Cloud Storage.**
`bigquery_export_table` is one of the 39 tools the MCP arm is given. It runs
an extract job, which `goccy/bigquery-emulator` implements by being a GCS
client itself — and with no `STORAGE_EMULATOR_HOST` of its own it posted to
`https://storage.googleapis.com/upload/...` and came back with `tls: failed
to verify certificate: x509: certificate signed by unknown authority`. The
mirage arm now runs the same server and would hit the same wall without
the fix below.

The fix is one environment variable on the emulator's container, resolved
inside it — `host.docker.internal` rather than `127.0.0.1` — and the Go
storage client honours it the way the Python one does.

**And then it ignores `printHeader`.** The client sets `printHeader: true` by
default and BigQuery honours it; the emulator writes the rows and no header line. Verified in
both directions against a two-column probe table.

That is the worse of the two failure modes, and worth stating plainly: **a
fake that fails loudly costs an arm turns, and a fake that succeeds wrongly
costs it the grade.** Wiring up the upload without noticing the header would
have converted a visible failure into an invisible one — a plausible
artefact, graded wrong, with nothing in the transcript to suggest the
environment was at fault.

`server/bq/proxy.py` puts the header back, from the source table's own
schema read out of the emulator, and respects `printHeader: false`. The
emulator still does the export — values, escaping, sharding are all its own.

## One emulator, two arms, one dataset

Both arms run against the same emulator process, seeded once when it
started, so tables an agent creates outlive the arm that created them. This
arm's MCP run leaves a staging table and an `anomaly_report_...`; nothing
puts them back.

`server/seed/reset_bigquery.py` now sweeps each dataset back to the tables its
manifest names, before every arm, the way `server/seed/seed_gcs.py` recreates the
bucket. That guard was missing for as long as BigQuery has been in this
repo, and the task it mattered most for is `game-statistics`, which is
graded on a `leaderboard_<date>` table the agent is asked to create.
