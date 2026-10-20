import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = TASK_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "agent"))

# Where the answer sheet goes, defined once in agent/services.py.
from services import ground_truth  # noqa: E402

# The Postgres behind the fake warehouse, called directly: this seeder
# is ours, so it has no reason to go through `redirect/snowflake`.
from server.clients import snowflake as snowflake_pg  # noqa: E402

DATABASE = "SLA_MONITOR"
GROUNDTRUTH = ground_truth(TASK_DIR.name) / "sla_monitoring.jsonl"

# First reply time in minutes, from the handbook's section 6.1. Only
# `response_time_minutes` decides an overdue ticket; the other two are
# upstream's and are kept so the table reads the same.
SLA_CONFIGS = {
    "max": {
        "response_time_minutes": 1440,
        "followup_time_minutes": 1080,
        "priority": 3
    },
    "pro": {
        "response_time_minutes": 2160,
        "followup_time_minutes": 2160,
        "priority": 2
    },
    "basic": {
        "response_time_minutes": 4320,
        "followup_time_minutes": 4320,
        "priority": 1
    },
}

SAMPLE_USERS = [
    ("Raymond Miller", "raymondm@mcp.com", "basic", "dhall@mcp.com"),
    ("Donald Castillo", "donald_castillo@mcp.com", "max", "dhall@mcp.com"),
    ("Brian Ramos", "ramosb@mcp.com", "pro", "andersonp@mcp.com"),
    ("Ashley Ortiz", "ortiza2@mcp.com", "basic", "andersonp@mcp.com"),
    ("Tracy Clark", "clarkt12@mcp.com", "pro", "andersonp@mcp.com"),
    ("Ruth Scott", "rscott53@mcp.com", "basic", "dhall@mcp.com"),
    ("Andrew Wilson", "awilson@mcp.com", "pro", "andersonp@mcp.com"),
    ("Janet Lopez", "janetl@mcp.com", "max", "dhall@mcp.com"),
    ("Jason Hernandez", "hernandezj@mcp.com", "basic", "andersonp@mcp.com"),
    ("Anthony White", "anthonyw@mcp.com", "basic", "andersonp@mcp.com"),
    ("Richard Bennett", "rbennett78@mcp.com", "pro", "dhall@mcp.com"),
    ("Raymond Morgan", "raymondm713@mcp.com", "max", "dhall@mcp.com"),
    ("Rebecca Hall", "rebeccah@mcp.com", "max", "andersonp@mcp.com"),
    ("Anna Wright", "anna.wright@mcp.com", "pro", "andersonp@mcp.com"),
    ("Debra Sanders", "dsanders@mcp.com", "basic", "dhall@mcp.com"),
]

TICKET_TYPES = {
    "bug_report": [
        "Application crashes when uploading large files",
        "Login page returns 500 error intermittently",
        "Export feature not working for CSV format",
        "Dashboard charts not loading properly",
        "Email notifications not being sent",
    ],
    "feature_request": [
        "Need ability to bulk edit user permissions",
        "Request for dark mode theme option",
        "Add integration with third-party calendar",
        "Need advanced filtering options in reports",
        "Request for mobile app version",
    ],
    "account_issue": [
        "Unable to reset password using email link",
        "Account suspended without notification",
        "Billing discrepancy on latest invoice",
        "Need to transfer account to different email",
        "Subscription not reflecting recent upgrade",
    ],
    "general_inquiry": [
        "How to set up SSO for our organization",
        "Questions about data retention policies",
        "Need training materials for new team members",
        "Clarification on API rate limits",
        "Documentation for webhook setup",
    ],
}

# How far back an overdue ticket is placed, per service level, and the
# priority it is filed under. Every band clears its SLA by at least three
# hours, so a ticket that is overdue at seed time is still overdue when the
# grader looks.
OVERDUE_BANDS = {
    "pro": ((40, 50), "high"),
    "max": ((28, 35), "critical"),
    "basic": ((78, 90), "normal"),
}
# And how far back a healthy one is placed. Each band leaves enough room
# that a ticket cannot cross its SLA while the run is in progress: nine
# hours of slack for max, sixteen for pro, thirty-two for basic.
HEALTHY_BANDS = {"pro": (1, 20), "max": (1, 15), "basic": (1, 40)}

CREATE_USERS = """
CREATE TABLE SLA_MONITOR.PUBLIC.USERS (
    ID INTEGER PRIMARY KEY,
    NAME VARCHAR(255) NOT NULL,
    EMAIL VARCHAR(255) NOT NULL UNIQUE,
    SERVICE_LEVEL VARCHAR(50) NOT NULL,
    CUSTOMER_MANAGER VARCHAR(255) NOT NULL,
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)"""

CREATE_TICKETS = """
CREATE TABLE SLA_MONITOR.PUBLIC.SUPPORT_TICKETS (
    ID INTEGER AUTOINCREMENT PRIMARY KEY,
    TICKET_NUMBER VARCHAR(50) NOT NULL UNIQUE,
    USER_ID INTEGER NOT NULL,
    SUBJECT VARCHAR(500) NOT NULL,
    DESCRIPTION TEXT,
    STATUS VARCHAR(50) NOT NULL DEFAULT 'open',
    PRIORITY VARCHAR(20) DEFAULT 'normal',
    TICKET_TYPE VARCHAR(50),
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FIRST_RESPONSE_AT TIMESTAMP,
    RESOLVED_AT TIMESTAMP,
    UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    FOREIGN KEY (USER_ID) REFERENCES SLA_MONITOR.PUBLIC.USERS(ID)
)"""


def clock() -> datetime:
    """The warehouse's own idea of now, to second precision.

    Not the host's. Upstream asks the warehouse -- it runs
    `SELECT CURRENT_TIMESTAMP()` and places every ticket relative to the
    answer -- and it has to, because "this ticket is 40 hours old" is only
    true against the clock whoever reads it will compare against. Here the
    two differ: the fixture container runs `Etc/UTC` and a developer's
    laptop generally does not, so seeding from `datetime.now()` puts every
    ticket hours away from where the database says it is, and an agent that
    asks the database for the time gets a different overdue set than the
    one the ground truth records.

    Returns:
        datetime: naive, in the database's timezone.
    """
    now = snowflake_pg.execute("SELECT CURRENT_TIMESTAMP AS NOW")[0]["NOW"]
    return now.replace(tzinfo=None, microsecond=0)


def stamp(moment: datetime) -> str:
    """Render a timestamp the way the fixture stores them.

    Second precision, because upstream reads its clock back out of a
    `CURRENT_TIMESTAMP()` result with a `\\d{4}-..` regex and gets nothing
    finer.

    Args:
        moment (datetime): the time.
    """
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def generate(now: datetime) -> list[dict]:
    """Generate one ticket per user, upstream's sequence exactly.

    The `random` calls here are load-bearing: seeded at 42, their order is
    what fixes which of the fifteen tickets are overdue. Adding, removing
    or reordering a call silently produces a different fixture.

    Args:
        now (datetime): the clock the tickets are placed relative to.

    Returns:
        list[dict]: the tickets, in user order, numbered from TK-1000.
    """
    random.seed(42)
    tickets = []
    taken: set[datetime] = set()

    for offset, (name, email, level, manager) in enumerate(SAMPLE_USERS):
        ticket_type = random.choice(list(TICKET_TYPES.keys()))
        subject = random.choice(TICKET_TYPES[ticket_type])
        overdue = random.choice([True, False])

        if overdue:
            band, priority = OVERDUE_BANDS[level]
            created = now - timedelta(hours=random.randint(*band))
            status, first_response = "open", None
        else:
            hours = random.randint(*HEALTHY_BANDS[level])
            created = now - timedelta(hours=hours)

        # Upstream spaces colliding tickets ten minutes apart. It does this
        # before drawing the reply for a healthy ticket and after settling
        # an overdue one, but the loop consumes no randomness either way,
        # so one placement here matches both.
        while created in taken:
            created -= timedelta(minutes=10)
        taken.add(created)

        if not overdue:
            priority = "normal"
            answered = random.choice([True, False])
            first_response = None
            if answered:
                delay = random.randint(1, hours - 1) if hours > 1 else 1
                first_response = created + timedelta(hours=delay)
            status = ("resolved"
                      if answered else random.choice(["open", "in_progress"]))

        tickets.append({
            "ticket_number":
            f"TK-{1000 + offset}",
            "user_id":
            1001 + offset,
            "user_email":
            email,
            "manager_email":
            manager,
            "service_level":
            level,
            "subject":
            subject,
            "description":
            (f"Detailed description: {subject}. Customer {name} reported "
             f"related issues requiring assistance from the technical "
             f"support team."),
            "status":
            status,
            "priority":
            priority,
            "ticket_type":
            ticket_type,
            "created_at":
            stamp(created),
            "first_response_at":
            stamp(first_response) if first_response else None,
        })
    return tickets


def is_overdue(ticket: dict, now: datetime) -> bool:
    """Whether a ticket has blown its first reply time.

    Args:
        ticket (dict): one generated ticket.
        now (datetime): the same clock the tickets were placed against.
    """
    if ticket["status"] not in ("open", "in_progress"):
        return False
    if ticket["first_response_at"] is not None:
        return False
    created = datetime.strptime(ticket["created_at"], "%Y-%m-%d %H:%M:%S")
    waited = (now - created).total_seconds() / 60
    return waited > SLA_CONFIGS[
        ticket["service_level"]]["response_time_minutes"]


def quote(value: str) -> str:
    """Escape a value for a SQL literal, upstream's way.

    Args:
        value (str): the text.
    """
    return value.replace("'", "''")


def load(tickets: list[dict], now: datetime) -> None:
    """Drop, recreate and fill the warehouse.

    Args:
        tickets (list[dict]): what `generate` produced.
        now (datetime): the run's clock, used for the mutable columns.
    """
    snowflake_pg.execute(f"DROP DATABASE IF EXISTS {DATABASE}")
    snowflake_pg.execute(f"CREATE DATABASE {DATABASE}")
    snowflake_pg.execute(CREATE_USERS)
    snowflake_pg.execute(CREATE_TICKETS)

    registered = stamp(now - timedelta(days=7))
    for offset, (name, email, level, manager) in enumerate(SAMPLE_USERS):
        snowflake_pg.execute(
            f"INSERT INTO {DATABASE}.PUBLIC.USERS (ID, NAME, EMAIL, "
            f"SERVICE_LEVEL, CUSTOMER_MANAGER, CREATED_AT, UPDATED_AT) "
            f"VALUES ({1001 + offset}, '{quote(name)}', '{email}', "
            f"'{level}', '{manager}', '{registered}', '{registered}')")

    updated = stamp(now)
    for ticket in tickets:
        first = (f"'{ticket['first_response_at']}'"
                 if ticket["first_response_at"] else "NULL")
        snowflake_pg.execute(
            f"INSERT INTO {DATABASE}.PUBLIC.SUPPORT_TICKETS (TICKET_NUMBER, "
            f"USER_ID, SUBJECT, DESCRIPTION, STATUS, PRIORITY, TICKET_TYPE, "
            f"CREATED_AT, FIRST_RESPONSE_AT, UPDATED_AT) VALUES "
            f"('{ticket['ticket_number']}', {ticket['user_id']}, "
            f"'{quote(ticket['subject'])}', "
            f"'{quote(ticket['description'])}', '{ticket['status']}', "
            f"'{ticket['priority']}', '{ticket['ticket_type']}', "
            f"'{ticket['created_at']}', {first}, '{updated}')")


def main() -> int:
    """Seed the warehouse and write the ground truth beside the task."""
    now = clock()
    tickets = generate(now)
    load(tickets, now)

    GROUNDTRUTH.parent.mkdir(parents=True, exist_ok=True)
    overdue = 0
    with GROUNDTRUTH.open("w", encoding="utf-8") as out:
        for ticket in tickets:
            flag = is_overdue(ticket, now)
            overdue += flag
            out.write(
                json.dumps(
                    {
                        "ticket_number": ticket["ticket_number"],
                        "manager_email": ticket["manager_email"],
                        "user_email": ticket["user_email"],
                        "service_level": ticket["service_level"],
                        "created_at": ticket["created_at"],
                        "is_overdue": flag,
                    },
                    ensure_ascii=False) + "\n")

    print(f"{DATABASE}: {len(SAMPLE_USERS)} users, {len(tickets)} tickets, "
          f"{overdue} overdue -> {GROUNDTRUTH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
