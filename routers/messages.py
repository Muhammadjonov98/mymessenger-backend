# ==========================================
# РОУТЕР СООБЩЕНИЙ
# WebSocket и REST API для работы с сообщениями и файлами
# ==========================================

import sys, os
# Добавляем корневую директорию проекта в путь импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Dict
import json
import traceback

from database import get_db
from models import User, Message
from languages import t

# Создаём роутер с тегом для группировки в Swagger UI
router = APIRouter(tags=["Xabarlar"])


# ==========================================
# МЕНЕДЖЕР WEBSOCKET СОЕДИНЕНИЙ
# Хранит все активные подключения в словаре {user_id: websocket}
# ==========================================

class ConnectionManager:

    def __init__(self):
        # Словарь активных соединений: ключ — user_id, значение — websocket объект
        self.online_users: Dict[int, WebSocket] = {}

    async def ulash(self, websocket: WebSocket, user_id: int):
        # Принимаем входящее WebSocket соединение
        await websocket.accept()
        # Сохраняем соединение в словарь по user_id
        self.online_users[user_id] = websocket
        # Выводим в терминал список онлайн пользователей
        print(f"✅ Пользователь {user_id} подключён. Онлайн: {list(self.online_users.keys())}")

    def uzish(self, user_id: int):
        # Проверяем есть ли пользователь в словаре перед удалением
        if user_id in self.online_users:
            # Удаляем соединение из словаря
            del self.online_users[user_id]
            # Выводим обновлённый список онлайн пользователей
            print(f"❌ Пользователь {user_id} отключён. Онлайн: {list(self.online_users.keys())}")

    async def xabar_yuborish(self, receiver_id: int, xabar: dict):
        # Проверяем онлайн ли получатель
        if receiver_id in self.online_users:
            try:
                # Получаем WebSocket объект получателя
                websocket = self.online_users[receiver_id]
                # Отправляем сообщение в формате JSON строки
                await websocket.send_text(json.dumps(xabar, ensure_ascii=False))
                # Возвращаем True — сообщение доставлено
                return True
            except Exception as e:
                # Логируем ошибку отправки
                print(f"⚠️ Ошибка отправки пользователю {receiver_id}: {e}")
                # Удаляем битое соединение из словаря
                self.uzish(receiver_id)
                # Возвращаем False — отправка не удалась
                return False
        # Пользователь офлайн — возвращаем False
        return False

    def onlayn_mi(self, user_id: int) -> bool:
        # Проверяем наличие user_id в словаре активных соединений
        return user_id in self.online_users


# Глобальный экземпляр менеджера — один на всё приложение
manager = ConnectionManager()


# ==========================================
# WEBSOCKET ENDPOINT
# ws://localhost:8000/ws/{user_id}
# ==========================================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        user_id: int,
        db: Session = Depends(get_db)
):
    # Проверяем существование пользователя в базе данных
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Закрываем соединение с кодом 4004 — пользователь не найден
        await websocket.close(code=4004)
        return

    # Регистрируем новое соединение в менеджере
    await manager.ulash(websocket, user_id)

    # ==========================================
    # ОБРАБОТКА ОФЛАЙН СООБЩЕНИЙ
    # При подключении помечаем все непрочитанные входящие как прочитанные
    # и уведомляем их отправителей сигналом oqildi_signal
    # ==========================================

    # Получаем все непрочитанные сообщения адресованные этому пользователю
    oflayn_xabarlar = db.query(Message).filter(
        Message.receiver_id == user_id,
        Message.is_read == False
    ).all()

    # Собираем уникальные ID отправителей непрочитанных сообщений
    sender_ids = set()
    for xabar in oflayn_xabarlar:
        # Помечаем каждое сообщение как прочитанное
        xabar.is_read = True
        # Добавляем ID отправителя в множество
        sender_ids.add(xabar.sender_id)

    # Сохраняем изменения в базу данных если были непрочитанные
    if sender_ids:
        db.commit()

    # Отправляем сигнал "прочитано" каждому отправителю офлайн сообщений
    for sender_id in sender_ids:
        await manager.xabar_yuborish(sender_id, {
            "type": "oqildi_signal",
            "receiver_id": user_id,
        })

    # ==========================================
    # ОСНОВНОЙ ЦИКЛ ПРИЁМА СООБЩЕНИЙ
    # Ждём новые сообщения от пользователя в бесконечном цикле
    # ==========================================
    try:
        while True:
            # Ожидаем текстовое сообщение от клиента
            data = await websocket.receive_text()

            try:
                # Парсим JSON строку в словарь
                xabar_data = json.loads(data)
                # Получаем ID получателя — приводим к int на случай строки
                receiver_id = int(xabar_data["receiver_id"])
                # Получаем текст сообщения — убираем пробелы по краям
                content = xabar_data.get("content", "").strip()
                # Получаем URL файла если есть (опционально)
                file_url = xabar_data.get("file_url", None)
                # Получаем тип файла если есть (rasm, video, hujjat, ovoz)
                file_type = xabar_data.get("file_type", None)

                # Запрещаем пустые сообщения без файла
                if not content and not file_url:
                    await websocket.send_text(json.dumps({
                        "xato": "Bo'sh xabar yuborib bo'lmaydi!"
                    }))
                    continue

                # Запрещаем отправку сообщения самому себе
                if receiver_id == user_id:
                    await websocket.send_text(json.dumps({
                        "xato": t("ozingizga_xabar", "uz")
                    }))
                    continue

                # Проверяем существование получателя в базе данных
                receiver = db.query(User).filter(User.id == receiver_id).first()
                if not receiver:
                    await websocket.send_text(json.dumps({
                        "xato": t("user_topilmadi", "uz")
                    }))
                    continue

                # Создаём новый объект сообщения для сохранения в БД
                # is_read всегда False — ✓✓ только когда получатель откроет чат
                yangi_xabar = Message(
                    sender_id=user_id,
                    receiver_id=receiver_id,
                    content=content,
                    file_url=file_url,
                    file_type=file_type,
                    is_read=False,
                    created_at=datetime.now(timezone.utc)
                )
                # Добавляем сообщение в сессию базы данных
                db.add(yangi_xabar)
                # Сохраняем изменения в базу данных
                db.commit()
                # Обновляем объект — получаем сгенерированный id
                db.refresh(yangi_xabar)

                # Формируем пакет данных сообщения для отправки клиентам
                xabar_paketi = {
                    "type": "xabar",
                    "id": yangi_xabar.id,
                    "sender_id": user_id,
                    "sender_name": user.full_name,
                    "receiver_id": receiver_id,
                    "content": content,
                    "file_url": file_url,
                    "file_type": file_type,
                    "created_at": yangi_xabar.created_at.isoformat(),
                    "is_read": False,
                }

                # Отправляем сообщение получателю если он онлайн
                await manager.xabar_yuborish(receiver_id, {
                    **xabar_paketi,
                    "status": "keldi"
                })

                # Отправляем подтверждение отправителю — галочка ✓
                await websocket.send_text(json.dumps({
                    **xabar_paketi,
                    "status": "yuborildi"
                }, ensure_ascii=False))

            except (json.JSONDecodeError, KeyError) as e:
                # Логируем ошибку парсинга сообщения
                print(f"⚠️ Ошибка парсинга: {e}")
                # Отправляем клиенту подсказку правильного формата
                await websocket.send_text(json.dumps({
                    "xato": "Noto'g'ri format! {'receiver_id': 2, 'content': 'Salom'}"
                }))

    except WebSocketDisconnect:
        # Пользователь отключился — удаляем его из словаря активных соединений
        manager.uzish(user_id)


# ==========================================
# REST API — История сообщений
# Вызывается когда пользователь открывает чат с другим пользователем
# Помечает входящие сообщения как прочитанные и отправляет oqildi_signal
# ==========================================

@router.get("/messages/{other_user_id}", summary="Xabarlar tarixini olish")
async def get_messages(
        other_user_id: int,
        current_user_id: int,
        db: Session = Depends(get_db)
):
    try:
        # Получаем все сообщения между двумя пользователями в хронологическом порядке
        xabarlar = db.query(Message).filter(
            (
                (Message.sender_id == current_user_id) &
                (Message.receiver_id == other_user_id)
            ) | (
                (Message.sender_id == other_user_id) &
                (Message.receiver_id == current_user_id)
            )
        ).order_by(Message.created_at).all()

        # Флаг — были ли изменения для последующего commit
        ozgardi = False
        for x in xabarlar:
            # Помечаем только входящие непрочитанные сообщения
            if x.receiver_id == current_user_id and not x.is_read:
                x.is_read = True
                ozgardi = True

        # Сохраняем изменения и отправляем сигнал только если были непрочитанные
        if ozgardi:
            db.commit()
            # Отправляем сигнал "прочитано" отправителю — вызывает ✓✓ у него
            await manager.xabar_yuborish(other_user_id, {
                "type": "oqildi_signal",
                "receiver_id": current_user_id,
            })

        # Возвращаем список сообщений включая данные о файлах
        return [
            {
                "id": x.id,
                "sender_id": x.sender_id,
                "receiver_id": x.receiver_id,
                "content": x.content,
                "file_url": x.file_url,
                "file_type": x.file_type,
                "is_read": x.is_read,
                "created_at": x.created_at.isoformat()
            }
            for x in xabarlar
        ]
    except Exception as e:
        # Выводим полный стек ошибки в терминал для отладки
        traceback.print_exc()
        # Пробрасываем исключение дальше — FastAPI вернёт 500
        raise


# ==========================================
# REST API — Отметить сообщение прочитанным
# ==========================================

@router.post("/messages/{message_id}/read")
def mark_as_read(message_id: int, db: Session = Depends(get_db)):
    # Ищем сообщение по ID в базе данных
    xabar = db.query(Message).filter(Message.id == message_id).first()
    if xabar:
        # Помечаем сообщение как прочитанное
        xabar.is_read = True
        # Сохраняем изменение в базу данных
        db.commit()
    return {"ok": True}


# ==========================================
# REST API — Список всех пользователей
# ==========================================

@router.get("/users", summary="Barcha foydalanuvchilarni ko'rish")
def get_users(db: Session = Depends(get_db)):
    # Получаем только активных пользователей из базы данных
    users = db.query(User).filter(User.is_active == True).all()
    # Возвращаем список с онлайн статусом каждого пользователя
    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "onlayn": manager.onlayn_mi(u.id)
        }
        for u in users
    ]