from typing import Any

from server.clients import snowflake as snowflake_pg


def found(database: str, schema: str | None) -> bool:
    """Whether a database, and a schema in it, exist.

    Args:
        database (str): the database, as Snowflake resolves it.
        schema (str | None): the schema, or None to ask only about the
            database.

    Returns:
        bool: whether a `USE` of them would succeed.
    """
    try:
        snowflake_pg.use(database, schema)
    except LookupError:
        return False
    return True


class Row(dict):
    """A result row. Snowpark's rows are dict-like and answer `asDict`."""

    def asDict(self) -> dict[str, Any]:  # noqa: N802 - Snowpark's spelling
        """The row as a plain dictionary."""
        return dict(self)


class DataFrame:
    """A statement that has not run yet.

    Snowpark is lazy, and the server relies on that: it builds
    `session.sql("USE WAREHOUSE ...")` and never collects it, which has to
    stay a no-op rather than an error.
    """

    def __init__(self, query: str, session: "Session"):
        """
        Args:
            query (str): the SQL.
            session (Session): the session it runs in, whose database and
                schema are the default for unqualified queries.
        """
        self._query = query
        self._session = session

    def collect(self) -> list[Row]:
        """Run the statement and return its rows.

        Returns:
            list[Row]: the rows, empty for a statement that returns none.
        """
        # A `USE` changes the session's database or schema, as it does in
        # Snowpark, for every statement the session runs after it -- and
        # one that names something missing fails and changes neither.
        # `USE DATABASE` leaves the session in that database's PUBLIC, when
        # it has one.
        used = snowflake_pg.used(self._query)
        if used is not None:
            database = used[0] or self._session._database
            snowflake_pg.use(database, used[1])
            self._session._database = database
            self._session._schema = used[1] or ("PUBLIC" if found(
                database, "PUBLIC") else None)
            return []
        return [
            Row(row) for row in snowflake_pg.execute(
                self._query, self._session._database, self._session._schema)
        ]

    def to_pandas(self):
        """The other collector, for the upstream release that uses it.

        Returns:
            pandas.DataFrame: the rows.
        """
        import pandas
        return pandas.DataFrame(self.collect())


class Session:
    """A Snowpark session over the fixture Postgres."""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config (dict[str, Any]): the connection block the server built.
                Only `database` and `schema` are used; the rest describes
                a cloud tenancy that does not exist here.
        """
        # Logging in leaves a database or schema that is not there unset
        # rather than refusing it: the connector's
        # `validate_default_parameters` is off unless asked for, and
        # neither the fork nor Snowpark asks. Upstream's block names
        # SNOWFLAKE and PUBLIC, and SNOWFLAKE has no PUBLIC, so its session
        # has a database and no schema.
        database, schema = config.get("database"), config.get("schema")
        self._database = self._schema = None
        if database and found(database, None):
            self._database = database
            if schema and found(database, schema):
                self._schema = schema

    class _Builder:
        """`Session.builder.configs(...).create()`."""

        def __init__(self):
            self._config: dict[str, Any] = {}

        def configs(self, config: dict[str, Any]) -> "Session._Builder":
            """Record the connection block.

            Args:
                config (dict[str, Any]): as the server assembled it.
            """
            self._config = config
            return self

        def create(self) -> "Session":
            """Open the session."""
            return Session(self._config)

    builder = _Builder()

    def sql(self, query: str) -> DataFrame:
        """Prepare a statement without running it.

        Args:
            query (str): the SQL.
        """
        return DataFrame(query, self)

    def close(self) -> None:
        """No-op: each statement opens its own connection."""


__all__ = ["Session", "DataFrame", "Row"]
