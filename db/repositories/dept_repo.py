"""
Department repository for CRUD operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.exceptions import RecordNotFoundError, DuplicateRecordError, DatabaseError
from db.models import Department, User

class DepartmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, name: str) -> Department:
        try:
            dept = Department(name=name)
            self.db.add(dept)
            self.db.flush()
            return dept
        except IntegrityError:
            self.db.rollback()
            raise DuplicateRecordError("Department", "name", name)
        except Exception as e:
            self.db.rollback()
            raise DatabaseError(f"Failed to create department: {str(e)}")

    def get_all(self) -> List[Department]:
        return self.db.query(Department).all()

    def get_by_id(self, dept_id: str) -> Department:
        dept = self.db.query(Department).filter(Department.id == dept_id).first()
        if not dept:
            raise RecordNotFoundError("Department", dept_id)
        return dept

    def delete(self, dept_id: str) -> None:
        dept = self.get_by_id(dept_id)
        self.db.delete(dept)
        self.db.flush()
