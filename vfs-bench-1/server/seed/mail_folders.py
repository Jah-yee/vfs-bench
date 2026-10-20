#!/usr/bin/env python
import imaplib
import json
import sys
from pathlib import Path

# What poste.io gives an account, minus INBOX, which every server has.
FOLDERS = ("Sent", "Drafts", "Trash")


def accounts(listing: Path) -> list[dict]:
    """Read the addresses a task involves.

    Args:
        listing (Path): the task's `files/involved_emails.json`, which is
            `{role: {address: {password, imap_server, imap_port, ...}}}`.

    Returns:
        list[dict]: one connection config per address.
    """
    found = []
    for role in json.loads(listing.read_text()).values():
        for address, config in role.items():
            found.append({"email": address, **config})
    return found


def provision(config: dict) -> list[str]:
    """Create the missing folders on one account.

    Args:
        config (dict): address, password and IMAP host/port.

    Returns:
        list[str]: the folders this call created.
    """
    connect = imaplib.IMAP4_SSL if config.get("use_ssl") else imaplib.IMAP4
    imap = connect(config["imap_server"], config["imap_port"])
    made = []
    try:
        imap.login(config["email"], config["password"])
        for folder in FOLDERS:
            status, _ = imap.create(folder)
            if status == "OK":
                made.append(folder)
    finally:
        imap.logout()
    return made


def provision_all(listing: Path) -> int:
    """Give every account named in the listing its standard folders.

    Args:
        listing (Path): an `involved_emails.json`.

    Returns:
        int: how many folders were created.

    Raises:
        SystemExit: no such listing.
    """
    if not listing.is_file():
        raise SystemExit(f"no such account listing: {listing}")
    configs = accounts(listing)
    total = sum(len(provision(config)) for config in configs)
    print(f"mail folders: created {total} across {len(configs)} mailboxes")
    return total


def main(argv: list[str]) -> int:
    """Provision every account named in the listing, from the command line.

    Args:
        argv (list[str]): one path to an `involved_emails.json`.

    Returns:
        int: process exit status.
    """
    if len(argv) != 1:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} "
                         f"<involved_emails.json>")
    provision_all(Path(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
