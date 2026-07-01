"""Foydalanuvchi profili va qidiruv."""
from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from app.deps import CurrentUser, DbSession
from app.models import User
from app.redis_service import redis_service
from app.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.put("/me", response_model=UserOut)
async def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> UserOut:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/search", response_model=list[UserOut])
async def search_users(
    user: CurrentUser,
    db: DbSession,
    q: str = Query(min_length=1, max_length=64),
) -> list[UserOut]:
    """Username yoki ism bo'yicha foydalanuvchi qidirish (o'zidan tashqari)."""
    like = f"%{q}%"
    rows = await db.scalars(
        select(User)
        .where(User.id != user.id)
        .where(or_(User.username.ilike(like), User.display_name.ilike(like)))
        .order_by(User.username)
        .limit(20)
    )
    return [UserOut.model_validate(u) for u in rows]


@router.get("/{user_id}/presence")
async def get_presence(user_id: int, _: CurrentUser) -> dict:
    """Foydalanuvchi online holati (Redis)."""
    online = await redis_service.is_online(user_id)
    return {"user_id": user_id, "online": online}
