import os

# The seed upstream already picked for the standard-library generator, so the
# two halves of their fixture are drawn the same way.
SEED = 42

# 500 is the per-request row limit `insert_rows_json` documents; the emulator
# does not enforce it, but batching keeps one request from carrying 1,314
# rows and makes a partial failure legible.
BATCH = 500


class _Job:
    """The bit of `LoadJob` that a caller of `load_table_from_json` reads.

    Attributes:
        job_id (str): a stand-in identifier, printed by preprocess.
        state (str): always DONE; the insert has already happened.
        output_rows (int): how many rows were written.
    """

    def __init__(self, rows: int) -> None:
        self.job_id = "shimmed-streaming-insert"
        self.state = "DONE"
        self.output_rows = rows
        self.output_bytes = None
        self.created = None
        self.ended = None
        self.errors = None

    def result(self) -> "_Job":
        """Wait for the load. It is already done.

        Returns:
            _Job: self, as `LoadJob.result()` returns the job.
        """
        return self


def _install() -> None:
    """Replace `Client.load_table_from_json` with a streaming equivalent."""
    from google.cloud import bigquery

    def load_table_from_json(self, json_rows, destination, **kwargs):
        """Write rows the way the emulator can accept them.

        Args:
            json_rows (list[dict]): the rows, as the caller built them.
            destination (str | Any): table reference or its string form.
            **kwargs: `job_config` and friends; only `write_disposition`
                changes what happens here.

        Returns:
            _Job: a completed stand-in for the load job.

        Raises:
            RuntimeError: a row was rejected, which a real load would have
                surfaced as a failed job rather than silently dropped.
        """
        table = self.get_table(destination)
        config = kwargs.get("job_config")
        if getattr(config, "write_disposition", None) == "WRITE_TRUNCATE":
            # TRUNCATE TABLE is DDL the emulator does not have; a DELETE with
            # a always-true predicate is the portable spelling.
            self.query(f"DELETE FROM `{table.dataset_id}.{table.table_id}` "
                       f"WHERE TRUE").result()
        for start in range(0, len(json_rows), BATCH):
            errors = self.insert_rows_json(table,
                                           json_rows[start:start + BATCH])
            if errors:
                raise RuntimeError(
                    f"streaming insert into {table.table_id} rejected rows: "
                    f"{errors[:3]}")
        return _Job(len(json_rows))

    bigquery.Client.load_table_from_json = load_table_from_json


def _seed() -> None:
    """Seed numpy to match the seed upstream sets for `random`."""
    try:
        import numpy
    except ImportError:
        return
    numpy.random.seed(SEED)


if os.environ.get("BIGQUERY_EMULATOR_HOST"):
    _install()
    _seed()
