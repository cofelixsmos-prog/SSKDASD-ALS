from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from database import get_db
from dependencies import require_role
from models.user import User
from models.batch import Batch, batch_teachers
from schemas.user import UserCreate, UserUpdate, UserOut, PasswordReset
from services.auth_service import hash_password
from pydantic import BaseModel
from typing import Optional, List
import uuid

router = APIRouter(prefix="/api/admin", tags=["admin"])
AdminOnly = Depends(require_role("admin"))


# ── USER ENDPOINTS ───────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserOut])
async def list_users(
    role: Optional[str] = None,
    batch_id: Optional[str] = None,
    section: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=AdminOnly,
):
    q = select(User)
    if role:
        q = q.where(User.role == role)
    if batch_id:
        q = q.where(User.batch_id == batch_id)
    if section:
        q = q.where(User.section == section)
    if search:
        q = q.where(User.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%"))
    result = await db.execute(q.order_by(User.created_at.desc()))
    return result.scalars().all()


@router.post("/users", response_model=UserOut)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db), _=AdminOnly):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        batch_id=body.batch_id,
        section=body.section,
        linked_student_id=body.linked_student_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    # For teachers, assign batches via join table
    if body.role == "teacher" and body.batch_ids:
        for bid in body.batch_ids:
            await db.execute(
                batch_teachers.insert().values(batch_id=bid, teacher_id=user.id)
            )
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: str, body: UserUpdate, db: AsyncSession = Depends(get_db), _=AdminOnly):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_none=True)
    batch_ids = data.pop("batch_ids", None)
    for field, val in data.items():
        setattr(user, field, val)
    # Re-sync teacher batch assignments
    if batch_ids is not None and user.role == "teacher":
        await db.execute(delete(batch_teachers).where(batch_teachers.c.teacher_id == user_id))
        for bid in batch_ids:
            await db.execute(batch_teachers.insert().values(batch_id=bid, teacher_id=user_id))
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: str, body: PasswordReset, db: AsyncSession = Depends(get_db), _=AdminOnly):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db), _=AdminOnly):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    await db.delete(user)
    await db.commit()
    return {"ok": True}


# Get teacher's assigned batches
@router.get("/users/{user_id}/batches")
async def get_teacher_batches(user_id: str, db: AsyncSession = Depends(get_db), _=AdminOnly):
    result = await db.execute(
        select(batch_teachers.c.batch_id).where(batch_teachers.c.teacher_id == user_id)
    )
    return [row[0] for row in result.fetchall()]


# ── BATCH ENDPOINTS ──────────────────────────────────────────────────────────

class BatchCreate(BaseModel):
    name: str

class BatchUpdate(BaseModel):
    name: Optional[str] = None


@router.get("/batches")
async def list_batches(db: AsyncSession = Depends(get_db), _=AdminOnly):
    result = await db.execute(
        select(Batch).options(selectinload(Batch.students), selectinload(Batch.teachers)).order_by(Batch.name)
    )
    batches = result.scalars().all()
    out = []
    for b in batches:
        out.append({
            "id": b.id,
            "name": b.name,
            "created_at": b.created_at.isoformat(),
            "student_count": len(b.students),
            "teachers": [{"id": t.id, "name": t.name} for t in b.teachers],
            "sections": {
                "A": len([s for s in b.students if s.section == "A"]),
                "B": len([s for s in b.students if s.section == "B"]),
                "C": len([s for s in b.students if s.section == "C"]),
            }
        })
    return out


@router.post("/batches")
async def create_batch(body: BatchCreate, db: AsyncSession = Depends(get_db), _=AdminOnly):
    existing = await db.execute(select(Batch).where(Batch.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Batch name already exists")
    b = Batch(id=str(uuid.uuid4()), name=body.name)
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return {"id": b.id, "name": b.name, "student_count": 0, "teachers": [], "sections": {"A": 0, "B": 0, "C": 0}}


@router.patch("/batches/{batch_id}")
async def update_batch(batch_id: str, body: BatchUpdate, db: AsyncSession = Depends(get_db), _=AdminOnly):
    result = await db.execute(select(Batch).where(Batch.id == batch_id))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(404, "Batch not found")
    if body.name:
        b.name = body.name
    await db.commit()
    return {"ok": True}


@router.delete("/batches/{batch_id}")
async def delete_batch(batch_id: str, db: AsyncSession = Depends(get_db), _=AdminOnly):
    result = await db.execute(select(Batch).where(Batch.id == batch_id))
    b = result.scalar_one_or_none()
    if not b:
        raise HTTPException(404, "Batch not found")
    await db.delete(b)
    await db.commit()
    return {"ok": True}


@router.post("/batches/{batch_id}/teachers/{teacher_id}")
async def assign_teacher(batch_id: str, teacher_id: str, db: AsyncSession = Depends(get_db), _=AdminOnly):
    await db.execute(
        batch_teachers.insert().prefix_with("OR IGNORE").values(batch_id=batch_id, teacher_id=teacher_id)
    )
    await db.commit()
    return {"ok": True}


@router.delete("/batches/{batch_id}/teachers/{teacher_id}")
async def remove_teacher(batch_id: str, teacher_id: str, db: AsyncSession = Depends(get_db), _=AdminOnly):
    await db.execute(
        delete(batch_teachers).where(
            batch_teachers.c.batch_id == batch_id,
            batch_teachers.c.teacher_id == teacher_id,
        )
    )
    await db.commit()
    return {"ok": True}


@router.get("/batches/{batch_id}/students")
async def get_batch_students(batch_id: str, section: Optional[str] = None, db: AsyncSession = Depends(get_db), _=AdminOnly):
    q = select(User).where(User.batch_id == batch_id, User.role == "student")
    if section:
        q = q.where(User.section == section)
    result = await db.execute(q.order_by(User.name))
    students = result.scalars().all()
    return [{"id": s.id, "name": s.name, "section": s.section, "email": s.email, "is_active": s.is_active} for s in students]
