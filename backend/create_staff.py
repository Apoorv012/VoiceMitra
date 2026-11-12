"""Make a staff login and print its password (shown once; only a hash is stored).

    python -m backend.create_staff <username>           # a new staff login
    python -m backend.create_staff <username> --reset   # a new password for an existing one

Writes to the database in `.env` (MONGODB_URI / MONGODB_DB_NAME) -- on this PC that is the cloud (Atlas)
database, so a login made here works on the live website. Staff see and change everything.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys

from dotenv import load_dotenv

load_dotenv()

from backend import logins  # noqa: E402  (after load_dotenv, so the database settings are read)
from backend.db import get_db, logins_col  # noqa: E402
from backend.models import LoginRole, new_id  # noqa: E402


async def _run(username: str, reset: bool) -> int:
    await logins_col().create_index("username_key", unique=True)
    existing = await logins.find(username)
    if existing is not None and existing.role != LoginRole.staff:
        print(f"'{username}' is already a {existing.role.value} login; pick another username.", file=sys.stderr)
        return 1
    if existing is not None and not reset:
        print(f"Staff login '{existing.username}' already exists. Use --reset for a new password.", file=sys.stderr)
        return 1
    if existing is None and reset:
        print(f"No staff login '{username}' to reset.", file=sys.stderr)
        return 1
    password = secrets.token_urlsafe(18)  # 24 characters, ~144 bits
    login = await logins.set_login(LoginRole.staff, existing.id if existing else new_id(), username, password)
    print(f"Staff login {'reset' if existing else 'created'} in database '{get_db().name}'.")
    print(f"  username: {login.username}")
    print(f"  password: {password}")
    print("Save the password now: it is not stored and can't be shown again.")
    if existing:
        print("Signed out everywhere it was signed in.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a staff login (or reset its password).")
    parser.add_argument("username")
    parser.add_argument("--reset", action="store_true", help="give an existing staff login a new password")
    args = parser.parse_args()
    try:
        code = asyncio.run(_run(args.username, args.reset))
    except Exception as e:  # set_login's 400/409 arrive as HTTPException
        detail = getattr(e, "detail", None) or str(e)
        print(f"Couldn't create the login: {detail}", file=sys.stderr)
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
