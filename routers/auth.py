import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional

from database import get_db
from models import User
from schemas import UserCreate, UserLogin, UserOut, Token
from languages import t
from security import brute_force, parol_kuchlimi

# ==========================================
# SOZLAMALAR
# ==========================================

SECRET_KEY = "mymessenger-super-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 kun

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/auth", tags=["Autentifikatsiya"])


# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================

def parolni_shifrlash(parol: str) -> str:
    """Parolni xeshga aylantiradi — bcrypt 72 bayt chegarasi bilan"""
    return pwd_context.hash(parol[:72])


def parolni_tekshirish(oddiy_parol: str, xeshlangan_parol: str) -> bool:
    """Parolni tekshiradi"""
    return pwd_context.verify(oddiy_parol[:72], xeshlangan_parol)


def jwt_token_yaratish(data: dict) -> str:
    """JWT token yaratadi"""
    payload = data.copy()
    expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expires})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def tilni_aniqlash(accept_language: Optional[str] = None) -> str:
    """So'rov headeridan tilni aniqlaymiz"""
    if not accept_language:
        return "uz"
    til = accept_language.strip().lower()[:2]
    return til if til in ["uz", "ru", "en"] else "uz"


# ==========================================
# API ENDPOINTLAR
# ==========================================

@router.post("/register", response_model=UserOut, summary="Ro'yxatdan o'tish | Регистрация | Register")
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    accept_language: Optional[str] = Header(default="uz")
):
    """
    Yangi foydalanuvchi yaratadi.
    - Parol kuchliligi tekshiriladi
    - Username band bo'lsa xato qaytaradi
    - Parol avtomatik xeshlanadi
    """
    til = tilni_aniqlash(accept_language)

    # Parol kuchliligi tekshiruvi
    kuchli, sabab = parol_kuchlimi(user_data.password)
    if not kuchli:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=sabab
        )

    # Username band emasligini tekshiramiz
    mavjud_user = db.query(User).filter(User.username == user_data.username).first()
    if mavjud_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("username_band", til)
        )

    # Yangi foydalanuvchi yaratamiz
    yangi_user = User(
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=parolni_shifrlash(user_data.password)
    )

    db.add(yangi_user)
    db.commit()
    db.refresh(yangi_user)
    return yangi_user


@router.post("/login", response_model=Token, summary="Kirish | Вход | Login")
def login(
    request: Request,
    user_data: UserLogin,
    db: Session = Depends(get_db),
    accept_language: Optional[str] = Header(default="uz")
):
    """
    Tizimga kiradi va JWT token qaytaradi.
    - Brute force himoyasi — 5 urinishdan keyin 15 daqiqa bloklanadi
    - Noto'g'ri parol bo'lsa xato qaytaradi
    """
    til = tilni_aniqlash(accept_language)

    # Foydalanuvchi IP manzilini olamiz
    ip = request.client.host

    # Brute force tekshiruvi
    if not brute_force.urinish_qoshish(ip):
        qoldi = brute_force.qolgan_vaqt(ip)
        daqiqa = qoldi // 60
        soniya = qoldi % 60
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Juda ko'p urinish! {daqiqa} daqiqa {soniya} soniyadan keyin urinib ko'ring."
        )

    # Foydalanuvchini topamiz
    user = db.query(User).filter(User.username == user_data.username).first()

    # Parolni tekshiramiz
    if not user or not parolni_tekshirish(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("login_xato", til),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Muvaffaqiyatli kirishda urinishlar tarixini tozalaymiz
    brute_force.muvaffaqiyatli_kirish(ip)

    # Token yaratamiz
    token = jwt_token_yaratish(data={"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut, summary="Profilim | Мой профиль | My profile")
def get_me(
    token: str,
    db: Session = Depends(get_db),
    accept_language: Optional[str] = Header(default="uz")
):
    """Hozirgi foydalanuvchi ma'lumotlarini qaytaradi"""
    til = tilni_aniqlash(accept_language)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("token_xato", til)
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=t("user_topilmadi", til)
        )

    return user