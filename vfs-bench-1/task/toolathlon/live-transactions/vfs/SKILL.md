---
name: workspace-commands
description: The shell commands and task tools available in this workspace.
---

# Available commands

Python (`python` or `python3`), Perl, JavaScript/Node.js, and TypeScript
runtimes are unavailable. Use the shell commands and task CLIs documented
below; do not probe for or attempt to install other runtimes.

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## google-cloud

Use `google-cloud <command> '<JSON arguments>'`. Run
`google-cloud <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `google-cloud bigquery-run-query` | `{query: str, dry_run?: bool = false, max_results?: int = 1000}` | Execute a BigQuery SQL query Args: query: SQL query to execute dry_run: If True, only validate query without running it max_results: Maximum number of results to return (default: 1000) Returns: Query results or error message |
| `google-cloud bigquery-list-datasets` | `{}` | List all BigQuery datasets in the project Returns: List of datasets or error message |
| `google-cloud bigquery-create-dataset` | `{dataset_id: str, description?: str = "", location?: str = "US"}` | Create a new BigQuery dataset Args: dataset_id: ID for the new dataset description: Optional description for the dataset location: Dataset location (default: US) Returns: Success message or error |
| `google-cloud bigquery-get-dataset-info` | `{dataset_id: str}` | Get detailed information about a BigQuery dataset Args: dataset_id: ID of the dataset Returns: Dataset information or error message |
| `google-cloud bigquery-load-csv-data` | `{dataset_id: str, table_id: str, csv_file_path: str, skip_header?: bool = true, write_mode?: str = "WRITE_TRUNCATE"}` | Load data from CSV file to BigQuery table Args: dataset_id: Dataset ID table_id: Table ID csv_file_path: Path to CSV file skip_header: Whether to skip the first row (header) write_mode: Write mode (WRITE_TRUNCATE, WRITE_APPEND, WRITE_EMPTY) Returns: Success message or error |
| `google-cloud bigquery-export-table` | `{dataset_id: str, table_id: str, destination_bucket: str, destination_path: str, file_format?: str = "CSV"}` | Export BigQuery table to Cloud Storage Args: dataset_id: Dataset ID table_id: Table ID destination_bucket: Destination bucket name destination_path: Destination path in bucket file_format: Export format (CSV, JSON, AVRO) Returns: Success message or error |
| `google-cloud bigquery-list-jobs` | `{max_results?: int = 50, state_filter?: str = ""}` | List BigQuery jobs Args: max_results: Maximum number of jobs to return state_filter: Filter by job state (RUNNING, DONE, PENDING) Returns: List of jobs or error message |
| `google-cloud bigquery-cancel-job` | `{job_id: str}` | Cancel a BigQuery job Args: job_id: ID of the job to cancel Returns: Success message or error |
| `google-cloud storage-list-buckets` | `{}` | List all Cloud Storage buckets Returns: List of buckets or error message |
| `google-cloud storage-create-bucket` | `{bucket_name: str, location?: str = "US"}` | Create a new Cloud Storage bucket Args: bucket_name: Name for the new bucket location: Location for the bucket (default: US) Returns: Success message or error |
| `google-cloud storage-list-objects` | `{bucket_name: str, prefix?: str = ""}` | List objects in a Cloud Storage bucket Args: bucket_name: Name of the bucket prefix: Optional prefix to filter objects Returns: List of objects or error message |
| `google-cloud storage-upload-file` | `{bucket_name: str, source_file_path: str, destination_blob_name: str}` | Upload a file to Cloud Storage bucket Args: bucket_name: Name of the bucket source_file_path: Local path to the file to upload destination_blob_name: Name for the blob in the bucket Returns: Success message or error |
| `google-cloud storage-download-file` | `{bucket_name: str, source_blob_name: str, destination_file_path: str}` | Download a file from Cloud Storage bucket Args: bucket_name: Name of the bucket source_blob_name: Name of the blob in the bucket destination_file_path: Local path where to save the file Returns: Success message or error |
| `google-cloud storage-delete-object` | `{bucket_name: str, blob_name: str}` | Delete an object from Cloud Storage bucket Args: bucket_name: Name of the bucket blob_name: Name of the blob to delete Returns: Success message or error |
| `google-cloud storage-get-bucket-info` | `{bucket_name: str}` | Get detailed information about a Cloud Storage bucket Args: bucket_name: Name of the bucket Returns: Bucket information or error message |
| `google-cloud storage-generate-signed-url` | `{bucket_name: str, blob_name: str, expiration_minutes?: int = 60, method?: str = "GET"}` | Generate a signed URL for temporary access to a Cloud Storage object Args: bucket_name: Name of the bucket blob_name: Name of the blob expiration_minutes: URL expiration time in minutes (default: 60) method: HTTP method (GET, PUT, POST, DELETE) Returns: Signed URL or error message |
| `google-cloud storage-copy-object` | `{source_bucket: str, source_blob: str, dest_bucket: str, dest_blob: str}` | Copy an object between Cloud Storage buckets Args: source_bucket: Source bucket name source_blob: Source blob name dest_bucket: Destination bucket name dest_blob: Destination blob name Returns: Success message or error |
| `google-cloud storage-move-object` | `{source_bucket: str, source_blob: str, dest_bucket: str, dest_blob: str}` | Move an object between Cloud Storage buckets Args: source_bucket: Source bucket name source_blob: Source blob name dest_bucket: Destination bucket name dest_blob: Destination blob name Returns: Success message or error |
| `google-cloud storage-enable-versioning` | `{bucket_name: str, enabled?: bool = true}` | Enable or disable versioning for a Cloud Storage bucket Args: bucket_name: Name of the bucket enabled: Whether to enable (True) or disable (False) versioning Returns: Success message or error |
| `google-cloud storage-get-bucket-size` | `{bucket_name: str}` | Get size statistics for a Cloud Storage bucket Args: bucket_name: Name of the bucket Returns: Bucket size information or error message |
| `google-cloud storage-set-bucket-lifecycle` | `{bucket_name: str, age_days?: int = 30, action?: str = "Delete"}` | Set lifecycle rules for a Cloud Storage bucket Args: bucket_name: Name of the bucket age_days: Age in days after which to apply the action action: Action to take (Delete, SetStorageClass) Returns: Success message or error |
| `google-cloud logging-write-log` | `{log_name: str, message: str, severity?: str = "INFO"}` | Write a log entry to Cloud Logging Args: log_name: Name of the log message: Log message severity: Log severity (DEBUG, INFO, WARNING, ERROR, CRITICAL) Returns: Success message or error |
| `google-cloud logging-read-logs` | `{log_filter?: str = "", max_entries?: int = 50}` | Read recent log entries from Cloud Logging Args: log_filter: Optional filter for log entries max_entries: Maximum number of entries to return (default: 50) Returns: Log entries or error message |
| `google-cloud logging-list-logs` | `{}` | List all log names in the project Returns: List of log names or error message |
| `google-cloud logging-delete-log` | `{log_name: str}` | Delete a log Args: log_name: Name of the log to delete Returns: Success message or error |
| `google-cloud logging-create-log-sink` | `{sink_name: str, destination: str, log_filter?: str = ""}` | Create a log sink to export logs to another service Args: sink_name: Name for the sink destination: Destination (e.g., bigquery://project.dataset, storage://bucket-name) log_filter: Optional filter for which logs to export Returns: Success message or error |
| `google-cloud logging-list-log-sinks` | `{}` | List all log sinks in the project Returns: List of log sinks or error message |
| `google-cloud logging-delete-log-sink` | `{sink_name: str}` | Delete a log sink Args: sink_name: Name of the sink to delete Returns: Success message or error |
| `google-cloud logging-export-logs-to-bigquery` | `{dataset_id: str, table_id: str, log_filter?: str = "", days_back?: int = 1}` | Export logs to BigQuery Args: dataset_id: BigQuery dataset ID table_id: BigQuery table ID log_filter: Filter for which logs to export days_back: Number of days back to export (default: 1) Returns: Success message or error |
| `google-cloud logging-create-log-bucket` | `{bucket_id: str, location?: str = "global", retention_days?: int = 30}` | Create a log bucket for storing logs Args: bucket_id: ID for the log bucket location: Location for the bucket (default: global) retention_days: Log retention period in days (default: 30) Returns: Success message or error |
| `google-cloud compute-list-instances` | `{zone?: str = ""}` | List Compute Engine instances Args: zone: Optional zone filter, if empty lists from all zones Returns: List of instances or error message |
| `google-cloud compute-create-instance` | `{instance_name: str, zone: str, machine_type?: str = "e2-micro"}` | Create a new Compute Engine instance Args: instance_name: Name for the new instance zone: Zone where to create the instance machine_type: Machine type (default: e2-micro) Returns: Success message or error |
| `google-cloud compute-delete-instance` | `{instance_name: str, zone: str}` | Delete a Compute Engine instance Args: instance_name: Name of the instance to delete zone: Zone where the instance is located Returns: Success message or error |
| `google-cloud compute-start-instance` | `{instance_name: str, zone: str}` | Start a Compute Engine instance Args: instance_name: Name of the instance to start zone: Zone where the instance is located Returns: Success message or error |
| `google-cloud compute-stop-instance` | `{instance_name: str, zone: str}` | Stop a Compute Engine instance Args: instance_name: Name of the instance to stop zone: Zone where the instance is located Returns: Success message or error |
| `google-cloud compute-restart-instance` | `{instance_name: str, zone: str}` | Restart a Compute Engine instance Args: instance_name: Name of the instance to restart zone: Zone where the instance is located Returns: Success message or error |
| `google-cloud compute-get-instance` | `{instance_name: str, zone: str}` | Get detailed information about a Compute Engine instance Args: instance_name: Name of the instance zone: Zone where the instance is located Returns: Instance information or error message |
| `google-cloud compute-list-zones` | `{}` | List all available Compute Engine zones Returns: List of zones or error message |
| `google-cloud compute-wait-for-operation` | `{operation_name: str, zone: str, timeout_minutes?: int = 5}` | Wait for a Compute Engine operation to complete Args: operation_name: Name of the operation to wait for zone: Zone where the operation is running timeout_minutes: Maximum time to wait in minutes (default: 5) Returns: Operation status or timeout message |
