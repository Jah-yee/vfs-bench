from typing import Any

from server.clients import snowflake as snowflake_pg


class DictCursor:
    """Marker for `conn.cursor(DictCursor)`, matching the real client.

    The connector uses the class itself as a selector rather than
    instantiating it, so an empty class is the whole contract.
    """


class Error(Exception):
    """What a failed statement raises, standing in for the real hierarchy."""


class Cursor:
    """One statement at a time, over `snowflake_pg`."""

    def __init__(self, database: str | None, as_dict: bool):
        """
        Args:
            database (str | None): default database for unqualified queries.
            as_dict (bool): whether rows come back as dictionaries.
        """
        self._database = database
        self._as_dict = as_dict
        self._rows: list[dict[str, Any]] = []
        self._at = 0
        self.rowcount = -1
        self.description: list[tuple] | None = None

    def execute(self, query: str, params: Any = None) -> "Cursor":
        """Run one statement.

        Args:
            query (str): the SQL.
            params (Any): bind parameters, passed through to psycopg2's
                own formatting when given.

        Returns:
            Cursor: self, as the DB-API allows.

        Raises:
            Error: the statement failed.
        """
        if params is not None:
            raise Error("the Postgres-backed shim takes SQL without binds")
        try:
            self._rows, self.rowcount = snowflake_pg.run(query, self._database)
        except Exception as failure:
            raise Error(str(failure)) from failure
        self._at = 0
        self.description = ([(name, ) + (None, ) * 6 for name in self._rows[0]]
                            if self._rows else None)
        return self

    def _shape(self, row: dict[str, Any]) -> Any:
        """Present one row the way this cursor was asked to.

        Args:
            row (dict[str, Any]): the row as the shim produced it.
        """
        return row if self._as_dict else tuple(row.values())

    def fetchall(self) -> list[Any]:
        """Every remaining row."""
        rest = [self._shape(r) for r in self._rows[self._at:]]
        self._at = len(self._rows)
        return rest

    def fetchone(self) -> Any:
        """The next row, or None."""
        if self._at >= len(self._rows):
            return None
        self._at += 1
        return self._shape(self._rows[self._at - 1])

    def close(self) -> None:
        """Release the cursor. Nothing is held open between statements."""
        self._rows = []


class Connection:
    """A connection in name only: each statement opens its own."""

    def __init__(self, database: str | None):
        """
        Args:
            database (str | None): default database for unqualified queries.
        """
        self.database = database

    def cursor(self, cursor_class: type | None = None) -> Cursor:
        """Open a cursor.

        Args:
            cursor_class (type | None): `DictCursor` for dictionaries,
                nothing for tuples.
        """
        return Cursor(self.database, cursor_class is DictCursor)

    def commit(self) -> None:
        """No-op: the shim runs every statement autocommitted."""

    def rollback(self) -> None:
        """No-op, and honest about it -- nothing here opens a transaction."""

    def close(self) -> None:
        """No-op: connections are per statement."""


def connect(**kwargs: Any) -> Connection:
    """Open a connection, ignoring everything that describes a cloud.

    Args:
        **kwargs (Any): the real connector's arguments; only `database`
            is used.

    Returns:
        Connection: a connection over the fixture Postgres.
    """
    return Connection(kwargs.get("database"))


class connection:  # noqa: N801 - the real package spells it this way
    """Stand-in for `snowflake.connector.connection`.

    The MCP server reads `DEFAULT_CONFIGURATION` from here to decide which
    `SNOWFLAKE_*` environment variables to pick up. Its keys are what
    matters, not its values.
    """

    DEFAULT_CONFIGURATION = {
        "account": (None, str),
        "user": (None, str),
        "password": (None, str),
        "database": (None, str),
        "schema": (None, str),
        "warehouse": (None, str),
        "role": (None, str),
    }


__all__ = [
    "connect", "connection", "Connection", "Cursor", "DictCursor", "Error"
]
