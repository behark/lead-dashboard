#!/usr/bin/env python3
"""
Migration: Add is_hidden column to leads table
Allows hiding contacted leads from the dashboard list.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from models import db


def migrate():
    app = create_app()

    with app.app_context():
        print("Running migration: add is_hidden to leads...")

        try:
            db.engine.execute(
                "ALTER TABLE leads ADD COLUMN is_hidden BOOLEAN DEFAULT 0"
            )
            print("is_hidden column added successfully!")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("is_hidden column already exists, skipping.")
            else:
                print(f"Migration failed: {e}")
                return False

    return True


if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
