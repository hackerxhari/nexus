"""
reset_data.py

This module contains core functionality for the Nexus application.
"""

import os
import shutil
import sys
from pathlib import Path

# Add project root to python path so we can import from core/db
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from core.config import get_settings
from db.base import engine, Base
import db.models  # Crucial: Import models so SQLAlchemy knows what to drop/create
from cache.redis_client import get_redis
from retrieval.vector_store import vector_store

def reset_all():
    settings = get_settings()
    
    print("=========================================================================")
    print("WARNING: This will permanently delete ALL data from the system including:")
    print("  - All Users (including admins)")
    print("  - All Departments")
    print("  - All Documents (metadata and actual files)")
    print("  - All Audit Logs")
    print("  - All Chat History & Custom Q&A")
    print("This action CANNOT be undone.")
    print("=========================================================================\n")
    
    confirm = input("Are you absolutely sure you want to proceed? Type 'yes' to confirm: ")
    if confirm.lower() != 'yes':
        print("Reset aborted. No changes were made.")
        return

    print("\nStarting reset process...")

    # 1. Reset Database
    print("- Dropping all database tables...")
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("  Database tables reset successfully.")
    except Exception as e:
        print(f"  Error resetting database: {e}")

    # 2. Reset Redis Cache
    print("- Clearing Redis cache...")
    try:
        get_redis().flushdb()
        print("  Redis cache cleared.")
    except Exception as e:
        print(f"  Error clearing Redis: {e}")

    # 3. Reset Qdrant Vectors
    print("- Clearing Qdrant vectors...")
    try:
        vector_store.client.delete_collection(settings.QDRANT_COLLECTION_NAME)
        vector_store._ensure_collection()
        print("  Qdrant collection cleared and recreated.")
    except Exception as e:
        print(f"  Error clearing Qdrant (it might not have existed): {e}")

    # 4. Clear Uploads directory
    print("- Clearing uploaded files...")
    upload_dir = Path(root_dir) / settings.UPLOAD_DIR
    try:
        if upload_dir.exists():
            for item in upload_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        else:
            upload_dir.mkdir(parents=True, exist_ok=True)
        print("  Uploads directory cleared.")
    except Exception as e:
        print(f"  Error clearing uploads directory: {e}")

    print("\n=== Reset Complete ===")
    print("System has been returned to a completely fresh, empty state.")
    print("Next step: Run the following command to recreate your admin user:")
    print("    python -m scripts.create_admin")

if __name__ == "__main__":
    reset_all()
