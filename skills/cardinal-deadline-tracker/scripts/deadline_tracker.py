"""Original credential-free helper. Initial draft: Codex/GPT-6; no copied student code."""

import argparse
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def aware(text):
    d = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("deadline requires an explicit timezone offset")
    return d.astimezone(timezone.utc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["create", "update", "list", "due-soon"])
    parser.add_argument("--title")
    parser.add_argument("--due")
    parser.add_argument("--id")
    parser.add_argument(
        "--status", choices=["open", "done", "cancelled"], default="open"
    )
    parser.add_argument("--hours", type=float, default=72)
    args = parser.parse_args()
    state = Path(
        os.environ.get("CARDINAL_STATE_DIR")
        or (
            Path(
                os.environ.get("LOCALAPPDATA")
                or os.environ.get("XDG_STATE_HOME")
                or Path.home() / ".local/state"
            )
            / "cardinal-deadlines"
        )
    )
    state.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(state / "deadlines.sqlite")
    try:
        with db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,title TEXT NOT NULL,due TEXT NOT NULL,status TEXT NOT NULL)"
            )
            if args.operation in ("create", "update"):
                if not args.title or len(args.title) > 300 or not args.due:
                    raise ValueError("title and due are required")
                due = aware(args.due).isoformat()
                if args.operation == "create":
                    db.execute(
                        "INSERT INTO tasks VALUES(?,?,?,?)",
                        (uuid.uuid4().hex, args.title, due, args.status),
                    )
                else:
                    if (
                        not args.id
                        or db.execute(
                            "UPDATE tasks SET title=?,due=?,status=? WHERE id=?",
                            (args.title, due, args.status, args.id),
                        ).rowcount
                        != 1
                    ):
                        raise ValueError("unknown update id")
            rows = [
                dict(zip(("id", "title", "due", "status"), row))
                for row in db.execute("SELECT * FROM tasks ORDER BY due")
            ]
            if args.operation == "due-soon":
                if not 0 < args.hours <= 24 * 366:
                    raise ValueError("hours out of range")
                now = datetime.now(timezone.utc)
                rows = [
                    r
                    for r in rows
                    if r["status"] == "open"
                    and now <= aware(r["due"]) <= now + timedelta(hours=args.hours)
                ]
        print(json.dumps({"tasks": rows}, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, sqlite3.Error) as error:
        raise SystemExit(str(error)) from None
