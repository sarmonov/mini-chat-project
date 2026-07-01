"""Ilova konfiguratsiyasi — barcha sozlamalar bir joyda."""
import os

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# RabbitMQ
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# Mavjud xonalar
ROOMS = ["general", "random", "tech"]

# Tarix uchun saqlanadigan xabarlar soni
HISTORY_LIMIT = 50

# Rate limiting: 1 sekundda nechta xabar yuborish mumkin
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 1  # sekund

# Typing indicator TTL (sekund)
TYPING_TTL = 3

# Online status heartbeat TTL (sekund)
STATUS_TTL = 30
