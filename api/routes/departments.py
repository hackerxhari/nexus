"""
departments.py

This module contains core functionality for the Project Nexus application.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from api.dependencies import get_request_id, CurrentUser, require_roles
from api.schemas.request import CreateDepartmentRequest
from api.schemas.response import APIResponse
from core.exceptions import GreenBaseException
from db.base import get_db
from db.repositories.dept_repo import DepartmentRepository

router = APIRouter(prefix="/departments", tags=["Departments"])

@router.post("", response_model=APIResponse)
async def create_department(
    body: CreateDepartmentRequest,
    current_user: CurrentUser = Depends(require_roles("admin", "ceo")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    try:
        repo = DepartmentRepository(db)
        dept = repo.create(name=body.name)

        return APIResponse.ok({
            "id": dept.id,
            "name": dept.name
        }, request_id)
    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)

@router.get("", response_model=APIResponse)
async def list_departments(
    current_user: CurrentUser = Depends(require_roles("admin", "hr", "manager", "employee", "ceo")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    repo = DepartmentRepository(db)
    depts = repo.get_all()
    return APIResponse.ok([{
        "id": d.id,
        "name": d.name
    } for d in depts], request_id)

@router.delete("/{dept_id}", response_model=APIResponse)
async def delete_department(
    dept_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "ceo")),
    request_id: str = Depends(get_request_id),
    db: Session = Depends(get_db)
):
    try:
        repo = DepartmentRepository(db)
        repo.delete(dept_id)
        return APIResponse.ok({"message": "Department deleted successfully"}, request_id)
    except GreenBaseException as e:
        return APIResponse.fail(e.error_code.value, e.message, request_id)
