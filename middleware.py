# ==========================================
# MIDDLEWARE — Безопасность и ограничение запросов
# Проверяет каждый запрос, добавляет заголовки безопасности
# ==========================================

from fastapi import Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
import time
import logging

# ==========================================
# LOGGING — Запись подозрительных действий
# Все предупреждения записываются в файл security.log
# ==========================================

# Настраиваем лог-файл — формат: дата - уровень - сообщение
logging.basicConfig(
    filename='security.log',
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Получаем объект логгера для этого модуля
logger = logging.getLogger(__name__)


# ==========================================
# RATE LIMITER — Ограничение запросов по IP
# Используется декоратором @limiter.limit("5/minute") на эндпоинтах
# ==========================================

# Создаём объект лимитера — ключ определяется по IP адресу
limiter = Limiter(key_func=get_remote_address)


# ==========================================
# MIDDLEWARE БЕЗОПАСНОСТИ
# Проверяет каждый HTTP запрос
# WebSocket запросы пропускаются без проверки (для них заголовки не нужны)
# ==========================================

class XavfsizlikMiddleware:
    """
    Для всех запросов:
    1. Проверяет заблокированные IP
    2. Добавляет заголовки безопасности
    3. Записывает медленные запросы в лог
    WebSocket соединения (ws://) пропускаются напрямую
    """

    # Множество заблокированных IP адресов — заполняется во время работы
    bloklangan_iplar: set = set()

    # Счётчик подозрительных запросов: { "ip": количество }
    shubhali_sorovlar: dict = {}

    @staticmethod
    async def sorovni_tekshirish(request: Request, call_next):
        # Пропускаем WebSocket запросы без проверки
        # Потому что для WebSocket заголовки ответа не работают
        if request.url.scheme in ("ws", "wss"):
            return await call_next(request)

        # Проверяем наличие клиента в HTTP запросе
        if request.client is None:
            return await call_next(request)

        # Получаем IP адрес входящего запроса
        ip = request.client.host

        # Запоминаем время начала запроса — для подсчёта длительности
        boshlanish = time.time()

        # Проверяем есть ли IP в списке заблокированных
        if ip in XavfsizlikMiddleware.bloklangan_iplar:
            # Записываем попытку заблокированного IP в лог
            logger.warning(f"Попытка заблокированного IP: {ip}")
            # Возвращаем ошибку 403 — доступ запрещён
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ваш IP адрес заблокирован!"
            )

        # Передаём запрос следующему middleware или эндпоинту
        response = await call_next(request)

        # Вычисляем время выполнения запроса (в секундах)
        davomiylik = time.time() - boshlanish

        # Защита от определения MIME типа браузером
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Запрещаем открытие сайта в iframe (защита от clickjacking)
        response.headers["X-Frame-Options"] = "DENY"
        # Включаем XSS фильтр для старых браузеров
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Принудительно используем HTTPS (на 1 год)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Ограничиваем заголовок Referer — для конфиденциальности
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Запросы дольше 5 секунд записываем как возможный признак DDoS
        if davomiylik > 5:
            logger.warning(f"Медленный запрос: {ip} - {request.url} - {davomiylik:.2f}s")

        return response
