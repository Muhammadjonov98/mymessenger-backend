import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import aiofiles
import uuid
from PIL import Image
import io

from database import get_db
from models import User

router = APIRouter(prefix="/files", tags=["Fayllar"])

# ==========================================
# SOZLAMALAR
# ==========================================

# Fayllar saqlanadigan papka
UPLOAD_PAPKA = "uploads"

# Ruxsat etilgan fayl turlari
RUXSAT_RASMLAR = {"image/jpeg", "image/png", "image/gif", "image/webp"}
RUXSAT_VIDEOLAR = {"video/mp4", "video/avi", "video/mov", "video/mkv"}
RUXSAT_HUJJATLAR = {"application/pdf", "application/msword",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "text/plain"}

# Maksimal fayl hajmi (baytda)
MAX_RASM_HAJMI = 10 * 1024 * 1024      # 10 MB
MAX_VIDEO_HAJMI = 200 * 1024 * 1024    # 200 MB
MAX_HUJJAT_HAJMI = 50 * 1024 * 1024   # 50 MB

# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================

def papka_yaratish():
    """Kerakli papkalarni yaratadi — mavjud bo'lmasa"""
    for papka in ["uploads/images", "uploads/videos", "uploads/documents", "uploads/voices"]:
        os.makedirs(papka, exist_ok=True)

# Ilova ishga tushganda papkalarni yaratamiz
papka_yaratish()


def fayl_turi_aniqlash(content_type: str) -> str:
    """
    Fayl turini aniqlaymiz.
    Qaytaradi: 'rasm', 'video', 'hujjat' yoki xato
    """
    if content_type in RUXSAT_RASMLAR:
        return "rasm"
    elif content_type in RUXSAT_VIDEOLAR:
        return "video"
    elif content_type in RUXSAT_HUJJATLAR:
        return "hujjat"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bu fayl turi qo'llab-quvvatlanmaydi: {content_type}"
        )


def fayl_hajmini_tekshirish(hajm: int, tur: str):
    """Fayl hajmini tekshiradi — oshib ketsa xato beradi"""
    if tur == "rasm" and hajm > MAX_RASM_HAJMI:
        raise HTTPException(
            status_code=400,
            detail=f"Rasm hajmi 10 MB dan oshmasligi kerak!"
        )
    elif tur == "video" and hajm > MAX_VIDEO_HAJMI:
        raise HTTPException(
            status_code=400,
            detail=f"Video hajmi 200 MB dan oshmasligi kerak!"
        )
    elif tur == "hujjat" and hajm > MAX_HUJJAT_HAJMI:
        raise HTTPException(
            status_code=400,
            detail=f"Hujjat hajmi 50 MB dan oshmasligi kerak!"
        )


def noyob_fayl_nomi(asl_nom: str) -> str:
    """
    Noyob fayl nomi yaratadi.
    Misol: "rasm.jpg" -> "a3f5b2c1-rasm.jpg"
    Bu bir xil nomli fayllar bir-birini ustiga yozilmasligini ta'minlaydi.
    """
    kengaytma = os.path.splitext(asl_nom)[1].lower()
    return f"{uuid.uuid4().hex}{kengaytma}"


async def rasmni_siqish(kontent: bytes, sifat: int = 85) -> bytes:
    """
    Rasmni siqadi — hajmini kamaytiradi.
    Sifat: 85% (ko'zga farq sezilmaydi, lekin hajm kamayadi)
    """
    try:
        rasm = Image.open(io.BytesIO(kontent))

        # RGBA -> RGB (JPEG uchun)
        if rasm.mode in ("RGBA", "P"):
            rasm = rasm.convert("RGB")

        # Maksimal o'lcham: 1920x1080
        max_olcham = (1920, 1080)
        rasm.thumbnail(max_olcham, Image.Resampling.LANCZOS)

        # Siqilgan rasmni qaytaramiz
        chiqish = io.BytesIO()
        rasm.save(chiqish, format="JPEG", quality=sifat, optimize=True)
        return chiqish.getvalue()
    except Exception:
        # Siqib bo'lmasa — aslini qaytaramiz
        return kontent


# ==========================================
# API ENDPOINTLAR
# ==========================================

@router.post("/upload", summary="Fayl yuklash | Загрузить файл | Upload file")
async def fayl_yuklash(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Fayl yuklaydi va saqlaydi.

    Qo'llab-quvvatlanadigan formatlar:
    - Rasmlar: JPG, PNG, GIF, WEBP (max 10MB)
    - Videolar: MP4, AVI, MOV, MKV (max 200MB)
    - Hujjatlar: PDF, DOC, DOCX, TXT (max 50MB)

    Qaytaradi: fayl URL si
    """

    # Fayl turini aniqlaymiz
    tur = fayl_turi_aniqlash(file.content_type)

    # Faylni o'qiymiz
    kontent = await file.read()

    # Hajmini tekshiramiz
    fayl_hajmini_tekshirish(len(kontent), tur)

    # Rasm bo'lsa — siqamiz
    if tur == "rasm":
        kontent = await rasmni_siqish(kontent)
        saqlash_papka = "uploads/images"
    elif tur == "video":
        saqlash_papka = "uploads/videos"
    else:
        saqlash_papka = "uploads/documents"

    # Noyob fayl nomi yaratamiz
    fayl_nomi = noyob_fayl_nomi(file.filename)
    fayl_yoli = os.path.join(saqlash_papka, fayl_nomi)

    # Faylni diskka saqlaymiz
    async with aiofiles.open(fayl_yoli, 'wb') as f:
        await f.write(kontent)

    # Fayl URL sini qaytaramiz
    url = f"/files/download/{tur}/{fayl_nomi}"

    return {
        "xabar": "Fayl muvaffaqiyatli yuklandi!",
        "fayl_nomi": fayl_nomi,
        "asl_nom": file.filename,
        "tur": tur,
        "hajm": f"{len(kontent) / 1024:.1f} KB",
        "url": url
    }


@router.post("/voice", summary="Ovozli xabar yuklash")
async def ovoz_yuklash(
    file: UploadFile = File(...)
):
    """
    Ovozli xabarni yuklaydi.
    Qo'llab-quvvatlanadigan: OGG, MP3, WAV, M4A
    """
    # Ovoz fayl turlari
    ruxsat_ovoz = {"audio/ogg", "audio/mpeg", "audio/wav", "audio/mp4", "audio/webm"}

    if file.content_type not in ruxsat_ovoz:
        raise HTTPException(
            status_code=400,
            detail="Faqat ovoz fayllari qabul qilinadi (OGG, MP3, WAV)!"
        )

    kontent = await file.read()

    # Maksimal 10 daqiqalik ovoz — 10MB
    if len(kontent) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="Ovozli xabar 10 MB dan oshmasligi kerak!"
        )

    fayl_nomi = noyob_fayl_nomi(file.filename or "voice.ogg")
    fayl_yoli = f"uploads/voices/{fayl_nomi}"

    async with aiofiles.open(fayl_yoli, 'wb') as f:
        await f.write(kontent)

    return {
        "xabar": "Ovozli xabar saqlandi!",
        "fayl_nomi": fayl_nomi,
        "url": f"/files/download/voice/{fayl_nomi}",
        "hajm": f"{len(kontent) / 1024:.1f} KB"
    }


@router.get("/download/{tur}/{fayl_nomi}", summary="Fayl yuklab olish")
async def fayl_yuklab_olish(tur: str, fayl_nomi: str):
    """
    Saqlangan faylni qaytaradi.
    Brauzer yoki ilova bu URL orqali faylni yuklab oladi.
    """

    # Fayl turига qarab papkani aniqlaymiz
    papkalar = {
        "rasm": "uploads/images",
        "video": "uploads/videos",
        "hujjat": "uploads/documents",
        "voice": "uploads/voices"
    }

    if tur not in papkalar:
        raise HTTPException(status_code=400, detail="Noto'g'ri fayl turi!")

    fayl_yoli = os.path.join(papkalar[tur], fayl_nomi)

    # Fayl mavjudligini tekshiramiz
    if not os.path.exists(fayl_yoli):
        raise HTTPException(status_code=404, detail="Fayl topilmadi!")

    # Path traversal hujumidan himoya
    # "../../../etc/passwd" kabi hujumlarni bloklaydi
    if ".." in fayl_nomi or "/" in fayl_nomi:
        raise HTTPException(status_code=400, detail="Noto'g'ri fayl nomi!")

    return FileResponse(fayl_yoli)


@router.get("/list/{tur}", summary="Yuklangan fayllar ro'yxati")
async def fayllar_royxati(tur: str):
    """Yuklangan fayllar ro'yxatini qaytaradi"""

    papkalar = {
        "rasm": "uploads/images",
        "video": "uploads/videos",
        "hujjat": "uploads/documents",
        "voice": "uploads/voices"
    }

    if tur not in papkalar:
        raise HTTPException(status_code=400, detail="Noto'g'ri fayl turi!")

    papka = papkalar[tur]

    if not os.path.exists(papka):
        return {"fayllar": []}

    fayllar = []
    for fayl in os.listdir(papka):
        fayl_yoli = os.path.join(papka, fayl)
        hajm = os.path.getsize(fayl_yoli)
        fayllar.append({
            "nom": fayl,
            "hajm": f"{hajm / 1024:.1f} KB",
            "url": f"/files/download/{tur}/{fayl}"
        })

    return {"fayllar": fayllar, "jami": len(fayllar)}