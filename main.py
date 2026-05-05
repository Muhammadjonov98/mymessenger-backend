# ==========================================
# ГЛАВНЫЙ ФАЙЛ ПРИЛОЖЕНИЯ
# Создание FastAPI приложения, подключение middleware и роутеров
# ==========================================

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import Optional

from database import Base, engine
from routers import auth, messages, files, calls
from languages import t
from middleware import XavfsizlikMiddleware, limiter


# ==========================================
# СОЗДАНИЕ ПРИЛОЖЕНИЯ
# Основной объект FastAPI с метаданными для документации
# ==========================================

# Создаём главный объект приложения с описанием для Swagger UI
app = FastAPI(
    title="MyMessenger API",
    description="UZ | RU | EN - Xavfsiz Ko'p tilli messenger",
    version="2.0.0"
)


# ==========================================
# ПОДКЛЮЧЕНИЕ RATE LIMITER
# Ограничивает количество запросов с одного IP
# ==========================================

# Прикрепляем лимитер к состоянию приложения — так его видят все эндпоинты
app.state.limiter = limiter

# Регистрируем красивый обработчик ошибки превышения лимита
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ==========================================
# MIDDLEWARE ДЛЯ WEBSOCKET
# Пропускает WebSocket соединения без проверки HTTP заголовков
# BaseHTTPMiddleware блокирует WebSocket — этот класс исправляет это
# ==========================================

class WebSocketSafeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Проверяем тип соединения — WebSocket пропускаем напрямую
        # BaseHTTPMiddleware не совместим с WebSocket протоколом
        if request.scope["type"] == "websocket":
            return await call_next(request)

        # Для обычных HTTP запросов применяем проверку безопасности
        return await XavfsizlikMiddleware.sorovni_tekshirish(request, call_next)


# ==========================================
# ПОДКЛЮЧЕНИЕ MIDDLEWARE — ПОРЯДОК ВАЖЕН!
# FastAPI применяет middleware в обратном порядке добавления
# ==========================================

# 1. CORS — разрешаем запросы с фронтенда (localhost:3000)
# allow_origins=["*"] — разрешаем все домены (изменить при деплое)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Middleware безопасности — проверяет IP, добавляет заголовки защиты
# WebSocket соединения пропускаются автоматически через WebSocketSafeMiddleware
app.add_middleware(WebSocketSafeMiddleware)


# ==========================================
# СОЗДАНИЕ ТАБЛИЦ БАЗЫ ДАННЫХ
# Создаёт все таблицы если они ещё не существуют
# ==========================================

# Создаём все таблицы из моделей SQLAlchemy при старте приложения
Base.metadata.create_all(bind=engine)


# ==========================================
# ПОДКЛЮЧЕНИЕ РОУТЕРОВ
# Каждый роутер отвечает за свою группу эндпоинтов
# ==========================================

# Роутер аутентификации — /auth/login, /auth/register, /auth/me
app.include_router(auth.router)

# Роутер сообщений — /messages, /ws/{user_id}, /users
app.include_router(messages.router)

# Роутер файлов — /files/upload, /files/download
app.include_router(files.router)

# Роутер звонков — /calls, WebRTC сигналинг
app.include_router(calls.router)


# ==========================================
# ГЛАВНАЯ СТРАНИЦА
# Проверка работоспособности сервера
# ==========================================

@app.get("/", summary="Server holati")
def root(accept_language: Optional[str] = Header(default="uz")):
    # Определяем язык из заголовка Accept-Language (первые 2 символа)
    til = accept_language.strip().lower()[:2] if accept_language else "uz"

    # Возвращаем статус сервера на нужном языке
    return {
        "holat": t("server_ishlayapti", til),
        "versiya": "2.0.0",
        "xavfsizlik": "E2EE + Rate Limiting + Brute Force himoya ✅"
    }