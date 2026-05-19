# ==========================================
# XAVFSIZLIK MIDDLEWARE
# IP himoya, brute force, va security headers
# ==========================================

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime, timezone


# ==========================================
# RATE LIMITER
# ==========================================

limiter = Limiter(key_func=get_remote_address)


# ==========================================
# XAVFSIZLIK MIDDLEWARE
# ==========================================

class XavfsizlikMiddleware:
    """
    Har bir so'rovni tekshirib xavfsizlik headers qo'shadi.
    """

    @staticmethod
    async def sorovni_tekshirish(request: Request, call_next):
        """
        So'rovni tekshirish va response'ga security headers qo'shish
        """
        # Response ni olish
        response = await call_next(request)

        # Security headers qo'shish
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"

        return response
