# Mini Telegram — FastAPI + PostgreSQL + RabbitMQ + Redis

Telegram uslubidagi real-time chat ilovasi. To'liq microservice-uslub arxitektura,
doimiy ma'lumotlar bazasi va real-time yetkazish. **Hammasi lokal ishlaydi.**

## Imkoniyatlar

| Funksiya | Tavsif |
|----------|--------|
| 🔐 Auth | Ro'yxatdan o'tish / kirish, parol **bcrypt** hash, **JWT** token |
| 👤 Profil | Ism, bio, avatar; foydalanuvchi qidirish |
| 💬 Shaxsiy suhbat (1:1) | Ikki foydalanuvchi o'rtasida DM |
| 👥 Guruhlar | Ko'p a'zoli suhbat, a'zo qo'shish/chiqarish, rollar (owner/admin/member) |
| 🖼 Media / fayl | Rasm va fayl yuborish (lokal `uploads/` ga saqlanadi) |
| ✓✓ Read receipts | Kim qayergacha o'qigani |
| ✍️ Typing indicator | "... yozmoqda" |
| 🟢 Presence | Onlayn / oxirgi tashrif (last seen) |
| 🔔 Realtime | WebSocket + Redis pub/sub orqali barcha qurilmalarga bir zumda |
| 📜 Tarix | PostgreSQL'da doimiy saqlanadi, sahifalab yuklash |

## Arxitektura

```
                         ┌───────────────────────────────────────┐
  Browser  ◄──WebSocket──►         FastAPI (app/)                 │
  (SPA)         REST      │  • REST: auth, users, chats, upload   │
    ▲                     │  • WS /ws  (JWT auth)                  │
    │                     └───┬──────────────┬───────────────┬────┘
    │                         │ publish      │ read/write    │ subscribe
    │                         ▼              ▼               ▼
    │                 ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │                 │   RabbitMQ   │ │  PostgreSQL  │ │    Redis     │
    │                 │ chat.persist │ │ users/chats/ │ │ presence/    │
    │                 │  (durable)   │ │ messages/... │ │ typing/pubsub│
    │                 └──────┬───────┘ └──────────────┘ └──────┬───────┘
    │                        │ consume  ► DB'ga saqlaydi        │ fan-out
    └────────broadcast───────┴─────────────────────────────────┘
```

**Xabar oqimi:**
1. Klient WebSocket orqali xabar yuboradi (`{type:"message", chat_id, content}`).
2. Server xabarni **RabbitMQ** `chat.persist` queue'siga qo'yadi.
3. Consumer queue'dan oladi → **PostgreSQL**'ga saqlaydi → **Redis** pub/sub kanaliga chiqaradi.
4. Har bir server instance Redis kanalini tinglaydi → suhbat a'zolarining WebSocket'lariga yetkazadi.

RabbitMQ — ishonchli saqlash quvuri (yozish yo'lini ajratadi). Redis — presence, typing va
instance'lararo real-time tarqatish (fan-out).

## Loyiha strukturasi

```
mini-chat-project/
├── app/
│   ├── main.py             # FastAPI app, lifecycle, routerlar
│   ├── config.py           # Sozlamalar (.env / env)
│   ├── database.py         # SQLAlchemy async engine + session
│   ├── models.py           # ORM: User, Chat, ChatMember, Message
│   ├── schemas.py          # Pydantic sxemalar
│   ├── security.py         # bcrypt + JWT
│   ├── deps.py             # DB session, joriy foydalanuvchi
│   ├── chat_service.py     # Suhbat DB yordamchilari
│   ├── redis_service.py    # presence / typing / pub-sub
│   ├── rabbit_service.py   # RabbitMQ publisher + consumer
│   ├── connection_manager.py # WebSocket ulanishlar (user -> sockets)
│   ├── realtime.py         # Fan-out yadrosi (persist+broadcast, subscriber)
│   ├── ws.py               # WebSocket endpoint
│   └── routers/            # auth, users, chats, messages, upload
├── static/                 # Frontend SPA (index.html, app.js, style.css)
├── uploads/                # Yuklangan media (gitignored)
├── docker-compose.yml      # Postgres + Redis + RabbitMQ
├── requirements.txt
├── .env.example
└── run.bat                 # Windows uchun bir tugmali ishga tushirish
```

## Ishga tushirish

### Talablar
- Python 3.11+
- Docker Desktop (Postgres, Redis, RabbitMQ uchun — eng oson yo'l)

### 1. Infratuzilmani ko'tarish (Docker)

```bash
docker compose up -d
```

Bu uchta konteynerni ishga tushiradi:
- PostgreSQL — `localhost:5432` (chat / chat / chat)
- Redis — `localhost:6379`
- RabbitMQ — `localhost:5672`, Management UI: http://localhost:15672 (guest / guest)

### 2. Sozlamalar (ixtiyoriy)

```bash
cp .env.example .env
```
Standart qiymatlar Docker Compose bilan mos — o'zgartirmasangiz ham ishlaydi.

### 3. Kutubxonalar va server

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Jadval sxemasi birinchi ishga tushishda avtomatik yaratiladi.

### 4. Ochish

http://localhost:8000 — ro'yxatdan o'ting. Sinash uchun ikki xil browserda (yoki
oddiy + inkognito) ikkita hisob yarating va bir-biringizga yozing.

> **Windows:** `run.bat` faylini ikki marta bosing — u Docker'ni ko'taradi,
> kutubxonalarni o'rnatadi va serverni ishga tushiradi.

## API (qisqacha)

| Metod | Yo'l | Tavsif |
|-------|------|--------|
| POST | `/api/auth/register` | Ro'yxatdan o'tish → JWT |
| POST | `/api/auth/login` | Kirish → JWT |
| GET | `/api/users/me` | Profil |
| PUT | `/api/users/me` | Profilni yangilash |
| GET | `/api/users/search?q=` | Foydalanuvchi qidirish |
| GET | `/api/chats` | Mening suhbatlarim |
| POST | `/api/chats/private` | Shaxsiy suhbat ochish/topish |
| POST | `/api/chats/group` | Guruh yaratish |
| POST | `/api/chats/{id}/members` | Guruhga a'zo qo'shish |
| DELETE | `/api/chats/{id}/members/{uid}` | A'zoni chiqarish / chiqish |
| GET | `/api/chats/{id}/messages?before_id=` | Xabar tarixi (sahifalash) |
| POST | `/api/upload` | Media / fayl yuklash |
| WS | `/ws?token=<JWT>` | Real-time kanal |

To'liq interaktiv hujjat: http://localhost:8000/docs

### WebSocket protokoli

Klient → server:
```json
{"type": "message", "chat_id": 1, "content": "salom", "client_id": "c123"}
{"type": "typing",  "chat_id": 1}
{"type": "read",    "chat_id": 1, "message_id": 42}
{"type": "heartbeat"}
```

Server → klient: `message`, `typing`, `read`, `presence`, `chat_update`, `error`.

## Ma'lumotlar bazasi (PostgreSQL)

| Jadval | Maqsad |
|--------|--------|
| `users` | Foydalanuvchilar (username, parol hash, profil, last_seen) |
| `chats` | Suhbatlar (private / group) |
| `chat_members` | A'zolik (rol, oxirgi o'qilgan xabar) |
| `messages` | Xabarlar (matn, media, reply, vaqt) |

## Redis kalitlari

| Kalit | Maqsad |
|-------|--------|
| `presence:{user_id}` | Onlayn belgisi (TTL heartbeat) |
| `conn:{user_id}` | Ochiq ulanishlar soni |
| `typing:{chat_id}:{user_id}` | Typing indicator (TTL) |
| `rt:events` (kanal) | Real-time fan-out pub/sub |

## Ishlab chiqarish uchun eslatma

- `JWT_SECRET` ni albatta kuchli qiymatga o'zgartiring (`.env`).
- Media saqlash: hozir lokal disk (`uploads/`). Prod uchun S3/MinIO tavsiya etiladi.
- Jadval migratsiyalari: hozir `create_all` (sodda). Prod uchun **Alembic** qo'shish mumkin.
