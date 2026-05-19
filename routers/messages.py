# ==========================================
# РОУТЕР СООБЩЕНИЙ
# WebSocket и REST API для работы с сообщениями и файлами
# ==========================================

import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Dict, Optional
import json
import traceback

from database import get_db
from models import User, Message
from languages import t

router = APIRouter(tags=["Xabarlar"])


# ==========================================
# МЕНЕДЖЕР WEBSOCKET СОЕДИНЕНИЙ
# ==========================================

class ConnectionManager:

    def __init__(self):
        self.online_users: Dict[int, WebSocket] = {}
        self.offline_messages: Dict[int, list] = {}  # ✅ OFLAYN XABARLAR

    async def ulash(self, websocket: WebSocket, user_id: int, db: Session):
        await websocket.accept()
        self.online_users[user_id] = websocket

        # ✅ OFLAYN XABARLARNI YUBORISH
        if user_id in self.offline_messages:
            for msg in self.offline_messages[user_id]:
                try:
                    await websocket.send_text(json.dumps(msg, ensure_ascii=False))
                except:
                    pass
            del self.offline_messages[user_id]

        print(f"✅ Пользователь {user_id} подключён. Онлайн: {list(self.online_users.keys())}")

    def uzish(self, user_id: int):
        if user_id in self.online_users:
            del self.online_users[user_id]
            print(f"❌ Пользователь {user_id} отключён. Онлайн: {list(self.online_users.keys())}")

    async def xabar_yuborish(self, receiver_id: int, xabar: dict):
        if receiver_id in self.online_users:
            try:
                websocket = self.online_users[receiver_id]
                await websocket.send_text(json.dumps(xabar, ensure_ascii=False))
                return True
            except Exception as e:
                print(f"⚠️ Ошибка отправки пользователю {receiver_id}: {e}")
                self.uzish(receiver_id)
                return False
        else:
            # ✅ OFLAYN SAQLASH
            if receiver_id not in self.offline_messages:
                self.offline_messages[receiver_id] = []
            self.offline_messages[receiver_id].append(xabar)
            print(f"📦 Сообщение сохранено для офлайн пользователя {receiver_id}")
            return False

    def onlayn_mi(self, user_id: int) -> bool:
        return user_id in self.online_users


manager = ConnectionManager()


# ==========================================
# WEBSOCKET ENDPOINT
# ==========================================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
        websocket: WebSocket,
        user_id: int,
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        await websocket.close(code=4004)
        return

    await manager.ulash(websocket, user_id, db)

    # O'qilmagan xabarlarni o'qilgan deb belgilash
    oflayn_xabarlar = db.query(Message).filter(
        Message.receiver_id == user_id,
        Message.is_read == False
    ).all()

    sender_ids = set()
    for xabar in oflayn_xabarlar:
        xabar.is_read = True
        sender_ids.add(xabar.sender_id)

    if sender_ids:
        db.commit()
        for sender_id in sender_ids:
            await manager.xabar_yuborish(sender_id, {
                "type": "oqildi_signal",
                "receiver_id": user_id,
            })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                xabar_data = json.loads(data)
                receiver_id = int(xabar_data["receiver_id"])
                content = xabar_data.get("content", "").strip()
                file_url = xabar_data.get("file_url", None)
                file_type = xabar_data.get("file_type", None)

                if not content and not file_url:
                    await websocket.send_text(json.dumps({"xato": "Bo'sh xabar yuborib bo'lmaydi!"}))
                    continue

                if receiver_id == user_id:
                    await websocket.send_text(json.dumps({"xato": t("ozingizga_xabar", "uz")}))
                    continue

                receiver = db.query(User).filter(User.id == receiver_id).first()
                if not receiver:
                    await websocket.send_text(json.dumps({"xato": t("user_topilmadi", "uz")}))
                    continue

                yangi_xabar = Message(
                    sender_id=user_id,
                    receiver_id=receiver_id,
                    content=content,
                    file_url=file_url,
                    file_type=file_type,
                    is_read=False,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(yangi_xabar)
                db.commit()
                db.refresh(yangi_xabar)

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

                # ✅ QABUL QILUVCHIGA YUBORISH (online bo'lsa, yo'qsa offline saqlanadi)
                await manager.xabar_yuborish(receiver_id, {**xabar_paketi, "status": "keldi"})

                # ✅ YUBORUVCHIGA TASDIQ (✓)
                await websocket.send_text(json.dumps({**xabar_paketi, "status": "yuborildi"}, ensure_ascii=False))

            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠️ Ошибка парсинга: {e}")
                await websocket.send_text(json.dumps({"xato": "Noto'g'ri format!"}))

    except WebSocketDisconnect:
        manager.uzish(user_id)


# ==========================================
# ✅ REST API — История сообщений (TUZATILGAN)
# ==========================================

@router.get("/messages/{other_user_id}", summary="Xabarlar tarixini olish")
async def get_messages(
        other_user_id: int,
        current_user_id: int = Query(..., description="Joriy foydalanuvchi ID si"),  # ✅ QUERY PARAMETER
        db: Session = Depends(get_db)
):
    """
    Ikki foydalanuvchi orasidagi xabarlar tarixini qaytaradi.
    Shu bilan birga, current_user ga kelgan o'qilmagan xabarlarni o'qilgan deb belgilaydi.
    """
    try:
        xabarlar = db.query(Message).filter(
            (
                    (Message.sender_id == current_user_id) &
                    (Message.receiver_id == other_user_id)
            ) | (
                    (Message.sender_id == other_user_id) &
                    (Message.receiver_id == current_user_id)
            )
        ).order_by(Message.created_at).all()

        ozgardi = False
        for x in xabarlar:
            if x.receiver_id == current_user_id and not x.is_read:
                x.is_read = True
                ozgardi = True

        if ozgardi:
            db.commit()
            # ✅ O'QILGANLIK SIGNALI (✓✓)
            await manager.xabar_yuborish(other_user_id, {
                "type": "oqildi_signal",
                "receiver_id": current_user_id,
            })

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
        traceback.print_exc()
        raise


# ==========================================
# REST API — Отметить сообщение прочитанным
# ==========================================

@router.post("/messages/{message_id}/read")
async def mark_as_read(message_id: int, db: Session = Depends(get_db)):
    xabar = db.query(Message).filter(Message.id == message_id).first()
    if xabar and not xabar.is_read:
        xabar.is_read = True
        db.commit()

        # ✅ YUBORUVCHIGA SIGNAL
        await manager.xabar_yuborish(xabar.sender_id, {
            "type": "oqildi_signal",
            "message_id": message_id,
            "receiver_id": xabar.receiver_id
        })

    return {"ok": True}


# ==========================================
# REST API — Список всех пользователей
# ==========================================

@router.get("/users", summary="Barcha foydalanuvchilarni ko'rish")
def get_users(
        current_user_id: Optional[int] = Query(None),
        db: Session = Depends(get_db)
):
    query = db.query(User).filter(User.is_active == True)
    if current_user_id:
        query = query.filter(User.id != current_user_id)

    users = query.all()

    return [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "onlayn": manager.onlayn_mi(u.id)
        }
        for u in users
    ]