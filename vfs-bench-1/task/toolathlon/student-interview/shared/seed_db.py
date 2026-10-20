import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = TASK_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT / "server" / "clients"))
sys.path.insert(0, str(REPO_ROOT / "agent"))

import gws  # noqa: E402
# Where the agent writes, defined once in agent/services.py.
from services import agent_workspace  # noqa: E402

TOOLATHLON = REPO_ROOT / "submodule" / "Toolathlon"
PACKAGE = f"tasks.finalpool.{TASK_DIR.name}"
CALENDAR = "primary"
# Hong Kong, because the task statement is: "within the two days of tomorrow
# and the day after tomorrow (Hong Kong Time)". The evaluator reads the
# working-hours window in the same frame.
OFFSET = "+08:00"
ZONE = "Asia/Hong_Kong"
# The two meetings the interviews have to be scheduled around, exactly as
# upstream's setup_calendar_events writes them: one on each of the two days,
# one of them inside working hours at each end of the range.
MEETINGS = (
    {
        "summary":
        "Academic Committee Meeting",
        "description":
        "Discuss curriculum arrangement and teaching plan for "
        "this semester\nLocation: Conference Room A\n"
        "Participants: Department heads",
        "location":
        "HKUST Conference Room A",
        "day":
        1,
        "from":
        "15:00:00",
        "to":
        "17:00:00",
    },
    {
        "summary":
        "PhD Dissertation Defense",
        "description":
        "Student: Li Minghua\nThesis: Research on Deep "
        "Learning-based Image Analysis Methods\nDefense "
        "committee members attendance required",
        "location":
        "HKUST Academic Auditorium",
        "day":
        2,
        "from":
        "09:00:00",
        "to":
        "11:00:00",
    },
)


def calendar(today: str) -> None:
    """Empty the mock calendar and put the two meetings back.

    Args:
        today (str): the day upstream just wrote into `today.txt`.
    """
    day = datetime.strptime(today, "%Y-%m-%d").date()
    gws.reset(epoch=f"{today}T09:00:00{OFFSET}",
              extras={"calendarTimeZone": ZONE})
    for meeting in MEETINGS:
        when = day + timedelta(days=meeting["day"])
        gws.create_event(
            CALENDAR, {
                "summary": meeting["summary"],
                "description": meeting["description"],
                "location": meeting["location"],
                "start": {
                    "dateTime": f"{when}T{meeting['from']}{OFFSET}",
                    "timeZone": ZONE,
                },
                "end": {
                    "dateTime": f"{when}T{meeting['to']}{OFFSET}",
                    "timeZone": ZONE,
                },
            })
    print(f"calendar: emptied, {len(MEETINGS)} meetings placed around "
          f"{day + timedelta(days=1)} and {day + timedelta(days=2)}")


def seed() -> int:
    """Run upstream's preprocess with the calendar half redirected."""
    sys.path.insert(0, str(TOOLATHLON))
    import asyncio
    import importlib

    entry = importlib.import_module(f"{PACKAGE}.preprocess.main")

    async def instead(_credentials: str) -> bool:
        """Stand in for `setup_calendar_events`, same events, mock server."""
        today = (TOOLATHLON / "tasks" / "finalpool" / TASK_DIR.name /
                 "groundtruth_workspace" / "today.txt").read_text().strip()
        calendar(today)
        return True

    entry.setup_calendar_events = instead
    sys.argv = ["main", "--agent_workspace", str(agent_workspace(TASK_DIR))]
    asyncio.run(entry.main())
    return 0


def relaunch() -> int:
    """Re-run this script inside Toolathlon's virtualenv.

    Its preprocess imports `utils.app_specific.poste`, `addict` and `rich`,
    none of which are this repo's dependencies.
    """
    if not TOOLATHLON.is_dir():
        raise FileNotFoundError(f"no Toolathlon checkout at {TOOLATHLON}")
    done = subprocess.run(
        ["uv", "run", "python",
         str(Path(__file__).resolve()), "--seed"],
        cwd=str(TOOLATHLON),
        env={**os.environ},
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        sys.stderr.write(done.stdout[-4000:] + done.stderr[-4000:])
        return done.returncode
    # Its own output is a line per injected message; the two that say what
    # the fixture is are enough for a batch log.
    for line in done.stdout.splitlines():
        if line.startswith("calendar:") or "Final mix:" in line:
            print(line.strip())
    return 0


if __name__ == "__main__":
    sys.exit(seed() if "--seed" in sys.argv else relaunch())
