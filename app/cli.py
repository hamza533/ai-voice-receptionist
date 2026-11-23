"""Admin commands. `python -m app.cli create-admin --email you@example.com`

The password is read interactively (or from stdin when piped), never from .env.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import User
from app.security import hash_password


def create_user(email: str, password: str, role: str, name: str = "") -> str:
    if len(password) < 10:
        raise SystemExit("Password must be at least 10 characters")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        action = "updated"
        if user is None:
            user = User(email=email.lower(), name=name or email.split("@")[0])
            db.add(user)
            action = "created"
        user.password_hash = hash_password(password)
        user.role = role
        user.active = True
        db.commit()
    return action


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ("create-admin", "create-staff"):
        p = sub.add_parser(cmd)
        p.add_argument("--email", required=True)
        p.add_argument("--name", default="")
    args = parser.parse_args()
    if sys.stdin.isatty():
        password = getpass.getpass("Password: ")
        if getpass.getpass("Repeat: ") != password:
            raise SystemExit("Passwords do not match")
    else:
        password = sys.stdin.readline().rstrip("\n")
    role = "admin" if args.cmd == "create-admin" else "staff"
    action = create_user(args.email, password, role, args.name)
    print(f"{role} {args.email} {action}")


if __name__ == "__main__":
    main()
