import argparse
import base64
import imaplib
import json
import sys
import time
import urllib.request
from email.message import EmailMessage
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STANDARD_FOLDERS = ("Sent", "Drafts", "Trash", "Junk")
TRANSIENT_IMAP_ERRORS = (OSError, imaplib.IMAP4.abort)


def reset(api: str) -> None:
    """Purge every GreenMail mailbox.

    Args:
        api (str): base URL of GreenMail's API port.
    """
    req = urllib.request.Request(f"{api}/api/service/reset", method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def connect(account: dict) -> imaplib.IMAP4:
    """Log in and make sure the standard folders exist.

    Args:
        account (dict): mailbox config, Toolathlon's spelling.

    Returns:
        imaplib.IMAP4: a logged-in connection.
    """
    imap = imaplib.IMAP4(account["imap_server"],
                         account["imap_port"],
                         timeout=10)
    imap.login(account["email"], account["password"])
    for folder in STANDARD_FOLDERS:
        imap.create(folder)
    return imap


def build(entry: dict, mailbox: str) -> tuple[EmailMessage, str]:
    """Turn one fixture entry into a message.

    Args:
        entry (dict): a fixture record in either supported shape.
        mailbox (str): the account address, used when the record has no
            explicit recipient.

    Returns:
        tuple[EmailMessage, str]: the message and its target folder.
    """
    msg = EmailMessage()
    msg["Subject"] = entry.get("subject", "(no subject)")
    sender = entry.get("from_addr") or entry.get("sender_name", "sender")
    msg["From"] = sender if "@" in sender else (
        f"{sender.replace(' ', '.').lower()}@mcp.com")
    msg["To"] = entry.get("to_addr") or mailbox
    for header in ("cc_addr", "bcc_addr"):
        if entry.get(header):
            msg[header[:2].upper()] = entry[header]
    if entry.get("date"):
        try:
            msg["Date"] = format_datetime(parsedate_to_datetime(entry["date"]))
        except (TypeError, ValueError):
            pass

    html = entry.get("body_html")
    text = entry.get("body_text")
    if entry.get("content_type") == "html":
        html = entry.get("content")
    elif entry.get("content") is not None:
        text = entry.get("content")

    msg.set_content(text or "")
    if html:
        msg.add_alternative(html, subtype="html")

    for att in entry.get("attachments") or []:
        raw = att.get("content") or att.get("data") or ""
        try:
            payload = base64.b64decode(raw)
        except (ValueError, TypeError):
            payload = str(raw).encode()
        ctype = att.get("content_type", "application/octet-stream")
        maintype, _, subtype = ctype.partition("/")
        msg.add_attachment(payload,
                           maintype=maintype or "application",
                           subtype=subtype or "octet-stream",
                           filename=att.get("filename", "attachment"))

    return msg, entry.get("folder") or "INBOX"


def entries_of(fixture: Path) -> list[dict]:
    """Read either fixture shape into a list of records.

    Args:
        fixture (Path): a .json or .jsonl fixture from upstream `files/`.

    Returns:
        list[dict]: the records, in file order.
    """
    if (fixture.name == "emails.jsonl"
            and fixture.parent.parent.name == "course-assistant"):
        return course_emails(fixture)
    if fixture.suffix == ".jsonl":
        return [
            json.loads(line) for line in fixture.read_text().splitlines()
            if line.strip()
        ]
    raw = json.loads(fixture.read_text())
    return raw["emails"] if isinstance(raw, dict) else raw


def course_emails(fixture: Path) -> list[dict]:
    """Reproduce the course preprocessor's account matching and formatting."""
    import importlib.util
    import re
    from email.utils import formataddr
    root = fixture.parent.parent
    path = root / "preprocess/send_email.py"
    spec = importlib.util.spec_from_file_location("course_send_email", path)
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    entries = upstream.load_emails_from_jsonl(fixture,
                                              fixture.parent /
                                              "placeholder_values.json",
                                              verbose=False)
    accounts = json.loads((root / "emails_all_config.json").read_text())
    recipient = json.loads((root / "emails_config.json").read_text())["email"]

    # Copied from preprocess/main.py; upstream defines this inside __main__.
    def normalize(name):
        n = name or ""
        n = re.sub(r"[._-]+", " ", n)
        n = re.sub(r"\d+", "", n)
        n = re.sub(r"[^A-Za-z\s]", "", n)
        return re.sub(r"\s+", " ", n).strip().lower()

    messages = []
    for account in accounts:
        address = account["email"]
        if address == recipient:
            continue
        candidates = {
            normalize(account.get("name", address)),
            normalize(address.split("@", 1)[0])
        }
        entry = next((item for item in entries
                      if normalize(item.get("sender_name")) in candidates),
                     None)
        if entry is not None:
            messages.append({
                **entry, "from_addr":
                formataddr((entry["sender_name"], address)),
                "to_addr":
                recipient
            })
    return messages


def fill(config: Path,
         fixture: Path | None = None,
         also: list[Path] | None = None,
         api: str = "http://localhost:8081",
         do_reset: bool = True) -> int:
    """Append a fixture inbox to a mailbox over IMAP.

    Args:
        config (Path): the mailbox to fill.
        fixture (Path | None): an `emails_backup.json` or `emails.jsonl`;
            without one the mailbox is only opened, which is how an empty
            mailbox gets created for a reply to land in.
        also (list[Path] | None): other mailboxes to create folders in.
        api (str): GreenMail's management API.
        do_reset (bool): empty GreenMail first. False when the caller has
            already reset it and is filling a second mailbox.

    Returns:
        int: how many messages were appended.
    """
    account = json.loads(config.read_text())
    if do_reset:
        reset(api)

    for extra in also or []:
        connect(json.loads(extra.read_text())).logout()

    imap = connect(account)
    count = 0
    if fixture:
        for entry in entries_of(fixture):
            msg, folder = build(entry, account["email"])
            if folder not in ("INBOX", *STANDARD_FOLDERS):
                imap.create(folder)
            imap.append(folder, None, imaplib.Time2Internaldate(time.time()),
                        msg.as_bytes())
            count += 1
    imap.logout()
    print(f"{account['email']}: {count} message(s) appended")
    return count


def main() -> int:
    """Reset GreenMail and append the fixture, from the command line.

    Returns:
        int: process exit status.
    """
    parser = argparse.ArgumentParser(
        description="Load a task's fixture inbox into GreenMail over IMAP.")
    parser.add_argument("--config", required=True, help="mailbox to fill")
    parser.add_argument("--fixture", help="emails_backup.json or emails.jsonl")
    parser.add_argument("--also",
                        action="append",
                        default=[],
                        help="another mailbox to create folders in")
    parser.add_argument("--api", default="http://localhost:8081")
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()
    fill(Path(args.config),
         Path(args.fixture) if args.fixture else None,
         [Path(p) for p in args.also],
         args.api,
         do_reset=not args.no_reset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
