"""
Run once to create the admin account.
Usage: python seed.py
"""
import asyncio
import bcrypt
from sqlalchemy import select
from database import AsyncSessionLocal, engine, Base
import models
from models.user import User

ADMIN_EMAIL = "admin@scholarly.com"
ADMIN_PASSWORD = "Admin@1234"
ADMIN_NAME = "Platform Admin"


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Admin already exists: {ADMIN_EMAIL}")
            return

        pw_hash = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
        admin = User(
            name=ADMIN_NAME,
            email=ADMIN_EMAIL,
            password_hash=pw_hash,
            role="admin",
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        print(f"Admin created: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
