---
name: workspace-commands
description: The shell commands, task tools, and python3 interpreter available in this workspace.
---

# Available commands

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip  curl

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## pdf-tools

Use `pdf-tools <command> '<JSON arguments>'`. Run
`pdf-tools <command> --help` to get more information.

| Command | Arguments | Description |
|---|---|---|
| `pdf-tools read-pdf-pages` | `{pdf_file_path: str, start_page?: int = 1, end_page?: int = 1}` | Read content from PDF file for specified page range. Supports both local file paths and URLs. For URLs, the PDF will be downloaded to a temporary directory and cached for future use. Note: Avoid reading too many pages at once (recommended: <50 pages) to prevent errors. Args: pdf_file_path: Path to the PDF file or URL to PDF start_page: Starting page number (default: 1) end_page: Ending page number (default: 1) Returns: Extracted text content from the specified pages |
| `pdf-tools get-pdf-info` | `{pdf_file_path: str}` | Get basic information about a PDF file including page count. Supports both local file paths and URLs. For URLs, the PDF will be downloaded to a temporary directory and cached for future use. Args: pdf_file_path: Path to the PDF file or URL to PDF Returns: Basic information about the PDF file |
| `pdf-tools merge-pdfs` | `{pdf_paths: list[str], output_path: str}` | Merge multiple PDF files into one. Supports both local file paths and URLs. URLs will be downloaded to temporary files before merging. Mixed local and URL paths are supported. Args: pdf_paths: List of paths to PDF files to merge (in order) - can include URLs output_path: Path where the merged PDF will be saved (must be local path) Returns: Success message with merge details or error message |
| `pdf-tools extract-pdf-pages` | `{source_path: str, page_numbers: list[int], output_path: str}` | Extract specific pages from a PDF and create a new PDF. Supports URLs for source PDF. The source PDF will be downloaded to a temporary directory if it's a URL. Output path must be a local file path. Args: source_path: Path to the source PDF file or URL to PDF page_numbers: List of page numbers to extract (1-indexed) output_path: Path where the new PDF will be saved (must be local path) Returns: Success message with extraction details or error message |
| `pdf-tools search-pdf-content` | `{pdf_file_path: str, pattern: str, page_size?: int = 10}` | Search for regex pattern in PDF content and return paginated results. Supports both local file paths and URLs. For URLs, the PDF will be downloaded to a temporary directory and cached for future use. Args: pdf_file_path: Path to the PDF file or URL to PDF pattern: Regular expression pattern to search for page_size: Number of results per page (10-50, default: 10) Returns: Search results with UUID for pagination, or error message |
| `pdf-tools search-pdf-next-page` | `{search_id: str}` | Get next page of search results. Args: search_id: Search session ID from previous search Returns: Next page of search results or error message |
| `pdf-tools search-pdf-prev-page` | `{search_id: str}` | Get previous page of search results. Args: search_id: Search session ID from previous search Returns: Previous page of search results or error message |
| `pdf-tools search-pdf-go-page` | `{search_id: str, page_number: int}` | Go to specific page of search results. Args: search_id: Search session ID from previous search page_number: Page number to go to (1-indexed) Returns: Specified page of search results or error message |
| `pdf-tools search-pdf-info` | `{search_id: str}` | Get information about a search session. Args: search_id: Search session ID from previous search Returns: Information about the search session |

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

## git

Use `git --help` for Git operations on workspace repositories.

## python3

Execute Python code directly under the agent workspace and return stdout
and stderr. Code can be pasted into a `.py` file and run with `python3`.

Python cannot launch subprocesses or make direct network requests. Run the
documented service commands directly in the shell. Use Python for local
file processing and generating JSON arguments.
