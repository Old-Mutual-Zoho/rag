#!/usr/bin/env python3
"""
Create app tables (users, conversations, messages, quotes) in Postgres.
Uses DATABASE_URL. Run when USE_POSTGRES_CONVERSATIONS is enabled.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.database.models import Base
from sqlalchemy import create_engine


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 1
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    print("App tables created (users, conversations, messages, quotes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
