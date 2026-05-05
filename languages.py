# ==========================================
# KO'P TILLI XABARLAR TIZIMI
# ==========================================
# Barcha xabarlar shu yerda saqlanadi
# Yangi til qo'shish uchun yangi bo'lim oching

MESSAGES = {

    # ------------------------------------------
    # O'ZBEK TILI
    # ------------------------------------------
    "uz": {
        # Auth xabarlari
        "username_band":        "Bu username allaqachon band! Boshqa nom tanlang.",
        "user_yaratildi":       "Foydalanuvchi muvaffaqiyatli ro'yxatdan o'tdi!",
        "login_xato":           "Username yoki parol noto'g'ri!",
        "token_xato":           "Token noto'g'ri yoki muddati o'tgan!",
        "user_topilmadi":       "Foydalanuvchi topilmadi!",

        # Xabar (message) xabarlari
        "xabar_yuborildi":      "Xabar muvaffaqiyatli yuborildi!",
        "xabar_topilmadi":      "Xabar topilmadi!",
        "ozingizga_xabar":      "O'zingizga xabar yubora olmaysiz!",

        # Umumiy
        "server_ishlayapti":    "MyMessenger ishlayapti!",
        "ruxsat_yoq":           "Bunga ruxsatingiz yo'q!",
        "xato":                 "Kutilmagan xato yuz berdi!",
    },

    # ------------------------------------------
    # RUS TILI
    # ------------------------------------------
    "ru": {
        # Auth xabarlari
        "username_band":        "Это имя пользователя уже занято! Выберите другое.",
        "user_yaratildi":       "Пользователь успешно зарегистрирован!",
        "login_xato":           "Неверное имя пользователя или пароль!",
        "token_xato":           "Токен недействителен или истёк!",
        "user_topilmadi":       "Пользователь не найден!",

        # Xabar (message) xabarlari
        "xabar_yuborildi":      "Сообщение успешно отправлено!",
        "xabar_topilmadi":      "Сообщение не найдено!",
        "ozingizga_xabar":      "Вы не можете отправить сообщение самому себе!",

        # Umumiy
        "server_ishlayapti":    "MyMessenger работает!",
        "ruxsat_yoq":           "У вас нет доступа!",
        "xato":                 "Произошла непредвиденная ошибка!",
    },

    # ------------------------------------------
    # INGLIZ TILI
    # ------------------------------------------
    "en": {
        # Auth xabarlari
        "username_band":        "This username is already taken! Please choose another.",
        "user_yaratildi":       "User registered successfully!",
        "login_xato":           "Invalid username or password!",
        "token_xato":           "Token is invalid or has expired!",
        "user_topilmadi":       "User not found!",

        # Xabar (message) xabarlari
        "xabar_yuborildi":      "Message sent successfully!",
        "xabar_topilmadi":      "Message not found!",
        "ozingizga_xabar":      "You cannot send a message to yourself!",

        # Umumiy
        "server_ishlayapti":    "MyMessenger is running!",
        "ruxsat_yoq":           "You don't have permission!",
        "xato":                 "An unexpected error occurred!",
    }
}

# Mavjud tillar ro'yxati
MAVJUD_TILLAR = ["uz", "ru", "en"]

# Standart til (agar til ko'rsatilmasa)
STANDART_TIL = "uz"


def t(kalit: str, til: str = STANDART_TIL) -> str:
    """
    Tarjima funksiyasi — t() deb chaqiriladi (translate qisqartmasi).

    Misol:
        t("username_band", "ru")  →  "Это имя пользователя уже занято!"
        t("login_xato", "en")    →  "Invalid username or password!"
        t("user_topilmadi")      →  "Foydalanuvchi topilmadi!"  (standart: uz)

    Agar til noto'g'ri bo'lsa — o'zbek tilida qaytaradi.
    """

    # Noto'g'ri til berilsa — standartga qaytamiz
    if til not in MAVJUD_TILLAR:
        til = STANDART_TIL

    # Xabarni topib qaytaramiz
    # Agar kalit topilmasa — kalitning o'zini qaytaramiz (xato ketmasin)
    return MESSAGES[til].get(kalit, kalit)