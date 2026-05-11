"""
create_admin.py

This module contains core functionality for the Nexus application.
"""

from db.base import get_db_session
from db.repositories.user_repo import UserRepository

EMAIL = "admin@nexus.com"
PASSWORD = "admin@1234"
FULL_NAME = "Admin User"
ROLES = ["admin"]
DEPARTMENT = None


def main() -> None:
    with get_db_session() as db:
        repo = UserRepository(db)
        existing_user = repo.get_by_email(EMAIL)
        
        if existing_user:
            existing_user.roles = ROLES
            existing_user.hierarchy = 4
            existing_user.department = DEPARTMENT
            db.commit()
            print("Admin user already existed and has been updated.")
        else:
            repo.create(
                email=EMAIL,
                full_name=FULL_NAME,
                plain_password=PASSWORD,
                roles=ROLES,
                department=DEPARTMENT,
                hierarchy=4
            )
            db.commit()
            print("Admin user created.")

if __name__ == "__main__":
    main()
