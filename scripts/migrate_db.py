"""
migrate_db.py

This module contains core functionality for the Nexus application.
"""

import os
import sqlite3
import sys

# Add project root to sys.path so we can import from db
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from db.models import Base

db_path = "H:/nexus/nexus.db"

# 1. Add columns to existing tables
print(f"Connecting to sqlite database at {db_path}...")
conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("ALTER TABLE users ADD COLUMN hierarchy INTEGER NOT NULL DEFAULT 1;")
    print("Successfully added hierarchy to users.")
except Exception as e:
    print(f"Failed to add hierarchy to users: {e}")

try:
    c.execute("ALTER TABLE documents ADD COLUMN hierarchy INTEGER NOT NULL DEFAULT 1;")
    print("Successfully added hierarchy to documents.")
except Exception as e:
    print(f"Failed to add hierarchy to documents: {e}")

conn.commit()
conn.close()

# 2. Create any missing tables (like 'departments') via SQLAlchemy
print("Running Base.metadata.create_all to create missing tables...")
engine = create_engine(f"sqlite:///{db_path}")
Base.metadata.create_all(engine)
print("Database schema update complete.")
