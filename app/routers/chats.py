"""Suhbatlar — private, guruh, a'zolar."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.chat_service import (
    build_chat_out,
    find_private_chat,
    get_member,
    is_member,
    list_user_chats,
    member_user_ids,
)
from app.deps import CurrentUser, DbSession
from app.models import Chat, ChatMember, ChatType, MemberRole, User
from app.realtime import notify_chat_update
from app.schemas import (
    AddMemberRequest,
    ChatOut,
    CreateGroupRequest,
    CreatePrivateRequest,
)

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("", response_model=list[ChatOut])
async def my_chats(user: CurrentUser, db: DbSession) -> list[ChatOut]:
    return await list_user_chats(db, user.id)


@router.post("/private", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_private(
    payload: CreatePrivateRequest, user: CurrentUser, db: DbSession
) -> ChatOut:
    if payload.user_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "O'zingiz bilan suhbat ochib bo'lmaydi")

    other = await db.get(User, payload.user_id)
    if other is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foydalanuvchi topilmadi")

    # allaqachon mavjud bo'lsa — o'shani qaytaramiz
    existing = await find_private_chat(db, user.id, other.id)
    if existing is not None:
        return await build_chat_out(db, existing, user.id)

    chat = Chat(type=ChatType.private, created_by=user.id)
    db.add(chat)
    await db.flush()
    db.add_all(
        [
            ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.member),
            ChatMember(chat_id=chat.id, user_id=other.id, role=MemberRole.member),
        ]
    )
    await db.commit()

    out = await build_chat_out(db, chat, user.id)
    # ikkala a'zoga yangi suhbat haqida xabar beramiz
    await notify_chat_update(chat.id, [user.id, other.id])
    return out


@router.post("/group", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: CreateGroupRequest, user: CurrentUser, db: DbSession
) -> ChatOut:
    chat = Chat(type=ChatType.group, title=payload.title, created_by=user.id)
    db.add(chat)
    await db.flush()

    # yaratuvchi — owner
    members = [ChatMember(chat_id=chat.id, user_id=user.id, role=MemberRole.owner)]
    # boshqa a'zolar (o'zini ikki marta qo'shmaymiz)
    unique_ids = {uid for uid in payload.member_ids if uid != user.id}
    for uid in unique_ids:
        exists = await db.scalar(select(User.id).where(User.id == uid))
        if exists:
            members.append(
                ChatMember(chat_id=chat.id, user_id=uid, role=MemberRole.member)
            )
    db.add_all(members)
    await db.commit()

    out = await build_chat_out(db, chat, user.id)
    await notify_chat_update(chat.id, [m.user_id for m in members])
    return out


@router.get("/{chat_id}", response_model=ChatOut)
async def get_chat(chat_id: int, user: CurrentUser, db: DbSession) -> ChatOut:
    chat = await db.get(Chat, chat_id)
    if chat is None or not await is_member(db, chat_id, user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suhbat topilmadi")
    return await build_chat_out(db, chat, user.id)


@router.post("/{chat_id}/members", response_model=ChatOut)
async def add_member(
    chat_id: int, payload: AddMemberRequest, user: CurrentUser, db: DbSession
) -> ChatOut:
    chat = await db.get(Chat, chat_id)
    if chat is None or chat.type != ChatType.group:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Guruh topilmadi")

    me = await get_member(db, chat_id, user.id)
    if me is None or me.role not in (MemberRole.owner, MemberRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A'zo qo'shishga ruxsat yo'q")

    if await is_member(db, chat_id, payload.user_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu foydalanuvchi allaqachon a'zo")

    target = await db.get(User, payload.user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foydalanuvchi topilmadi")

    db.add(ChatMember(chat_id=chat_id, user_id=target.id, role=MemberRole.member))
    await db.commit()

    out = await build_chat_out(db, chat, user.id)
    await notify_chat_update(chat_id, await member_user_ids(db, chat_id))
    return out


@router.delete("/{chat_id}/members/{member_id}", response_model=ChatOut)
async def remove_member(
    chat_id: int, member_id: int, user: CurrentUser, db: DbSession
) -> ChatOut:
    chat = await db.get(Chat, chat_id)
    if chat is None or chat.type != ChatType.group:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Guruh topilmadi")

    me = await get_member(db, chat_id, user.id)
    # o'zini chiqarish (leave) mumkin; boshqani faqat owner/admin
    if member_id != user.id and (
        me is None or me.role not in (MemberRole.owner, MemberRole.admin)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A'zoni chiqarishga ruxsat yo'q")

    target = await get_member(db, chat_id, member_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A'zo topilmadi")
    if target.role == MemberRole.owner:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Guruh egasini chiqarib bo'lmaydi")

    all_ids = await member_user_ids(db, chat_id)  # o'chirishdan oldin id'lar
    await db.delete(target)
    await db.commit()

    out = await build_chat_out(db, chat, user.id)
    await notify_chat_update(chat_id, all_ids)
    return out
