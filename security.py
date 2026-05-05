import os
import hmac
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timezone
from typing import Optional
import base64


# ==========================================
# FERNET SHIFRLASH — Xabarlar uchun
# ==========================================

class XabarShifrlash:
    """
    Xabarlarni shifrlash va ochish uchun klass.
    Fernet — AES-128-CBC shifrlash algoritmidan foydalanadi.
    Bu shuni anglatadiki — xabarlar DB da shifrlangan holda saqlanadi.
    Hatto DB ga kirgan odam ham xabarlarni o'qiy olmaydi!
    """

    def __init__(self):
        # Shifrlash kaliti — muhit o'zgaruvchisidan olamiz
        # Agar yo'q bo'lsa — yangi kalit yaratamiz
        kalit = os.environ.get("SHIFRLASH_KALITI")

        if not kalit:
            # Yangi kalit yaratamiz va saqlaymiz
            self.kalit = Fernet.generate_key()
            print(f"⚠️  Yangi shifrlash kaliti yaratildi!")
            print(f"⚠️  Muhit o'zgaruvchisiga saqlang: SHIFRLASH_KALITI={self.kalit.decode()}")
        else:
            self.kalit = kalit.encode()

        self.fernet = Fernet(self.kalit)

    def shifrlash(self, matn: str) -> str:
        """
        Oddiy matnni shifrlangan matnga aylantiradi.
        Misol: "Salom!" -> "gAAAAABh..."
        """
        shifrlangan = self.fernet.encrypt(matn.encode('utf-8'))
        return shifrlangan.decode('utf-8')

    def ochish(self, shifrlangan_matn: str) -> str:
        """
        Shifrlangan matnni oddiy matnga aylantiradi.
        Misol: "gAAAAABh..." -> "Salom!"
        """
        try:
            ochilgan = self.fernet.decrypt(shifrlangan_matn.encode('utf-8'))
            return ochilgan.decode('utf-8')
        except Exception:
            # Noto'g'ri kalit yoki buzilgan ma'lumot
            return "[Xabar o'qib bo'lmadi]"


# ==========================================
# RSA SHIFRLASH — Kalit almashish uchun
# ==========================================

class RSAShifrlash:
    """
    RSA-2048 — ochiq kalit kriptografiyasi.
    Har bir foydalanuvchi uchun juft kalit yaratiladi:
    - Ochiq kalit (public key) — hamma ko'ra oladi
    - Yopiq kalit (private key) — faqat foydalanuvchida
    """

    @staticmethod
    def kalit_juft_yaratish():
        """
        Yangi RSA-2048 kalit juftini yaratadi.
        Qaytaradi: (ochiq_kalit, yopiq_kalit) — ikkalasi ham string formatida
        """
        # Yopiq kalit yaratish
        yopiq_kalit = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Ochiq kalitni ajratib olamiz
        ochiq_kalit = yopiq_kalit.public_key()

        # String formatiga o'tkazamiz (DB ga saqlash uchun)
        yopiq_kalit_str = yopiq_kalit.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')

        ochiq_kalit_str = ochiq_kalit.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        return ochiq_kalit_str, yopiq_kalit_str


# ==========================================
# BRUTE FORCE HIMOYASI
# ==========================================

class BruteForceHimoya:
    """
    Login urinishlarini cheklaydi.
    Misol: 5 marta noto'g'ri parol kiritilsa — 15 daqiqa bloklanadi.
    Bu hack qilishni deyarli imkonsiz qiladi!
    """

    def __init__(self):
        # {ip_manzil: [urinish_vaqtlari]}
        self.urinishlar: dict = {}
        # Maksimal urinishlar soni
        self.max_urinish = 5
        # Bloklash vaqti (soniyada) — 15 daqiqa
        self.bloklash_vaqti = 15 * 60

    def urinish_qoshish(self, ip: str) -> bool:
        """
        Yangi urinishni qayd etadi.
        Qaytaradi: True — ruxsat, False — bloklangan
        """
        hozir = datetime.now(timezone.utc).timestamp()

        if ip not in self.urinishlar:
            self.urinishlar[ip] = []

        # Eski urinishlarni tozalaymiz (bloklash vaqtidan o'tganlarni)
        self.urinishlar[ip] = [
            vaqt for vaqt in self.urinishlar[ip]
            if hozir - vaqt < self.bloklash_vaqti
        ]

        # Urinishlar sonini tekshiramiz
        if len(self.urinishlar[ip]) >= self.max_urinish:
            return False  # Bloklangan!

        # Yangi urinishni qo'shamiz
        self.urinishlar[ip].append(hozir)
        return True  # Ruxsat

    def muvaffaqiyatli_kirish(self, ip: str):
        """Muvaffaqiyatli kirishda urinishlar tarixini tozalaydi"""
        if ip in self.urinishlar:
            del self.urinishlar[ip]

    def qolgan_vaqt(self, ip: str) -> int:
        """Bloklash qancha vaqt qolganini qaytaradi (soniyada)"""
        if ip not in self.urinishlar or not self.urinishlar[ip]:
            return 0

        hozir = datetime.now(timezone.utc).timestamp()
        eng_eski = min(self.urinishlar[ip])
        qoldi = self.bloklash_vaqti - (hozir - eng_eski)
        return max(0, int(qoldi))


# ==========================================
# XAVFSIZ TOKEN YARATISH
# ==========================================

def xavfsiz_token_yaratish(uzunlik: int = 32) -> str:
    """
    Kriptografik xavfsiz tasodifiy token yaratadi.
    Parolni tiklash, email tasdiqlash kabi ishlarda ishlatiladi.
    """
    return base64.urlsafe_b64encode(os.urandom(uzunlik)).decode('utf-8')


def parol_kuchlimi(parol: str) -> tuple[bool, str]:
    """
    Parol kuchliligini tekshiradi.
    Qaytaradi: (kuchli_mi, sabab)

    Talablar:
    - Kamida 8 belgi
    - Kamida 1 ta katta harf
    - Kamida 1 ta kichik harf
    - Kamida 1 ta raqam
    - Kamida 1 ta maxsus belgi
    """
    if len(parol) < 8:
        return False, "Parol kamida 8 belgidan iborat bo'lishi kerak!"

    if not any(c.isupper() for c in parol):
        return False, "Parolda kamida 1 ta katta harf bo'lishi kerak! (A-Z)"

    if not any(c.islower() for c in parol):
        return False, "Parolda kamida 1 ta kichik harf bo'lishi kerak! (a-z)"

    if not any(c.isdigit() for c in parol):
        return False, "Parolda kamida 1 ta raqam bo'lishi kerak! (0-9)"

    maxsus_belgilar = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in maxsus_belgilar for c in parol):
        return False, f"Parolda kamida 1 ta maxsus belgi bo'lishi kerak! ({maxsus_belgilar})"

    return True, "Parol kuchli! ✅"


# Global obyektlar — butun ilova uchun bitta
xabar_shifrlash = XabarShifrlash()
brute_force = BruteForceHimoya()