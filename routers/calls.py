import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Optional
import json
from datetime import datetime, timezone

router = APIRouter(prefix="/calls", tags=["Qo'ng'iroqlar"])


# ==========================================
# QONGIROQ BOSHQARUVCHI KLASS
# ==========================================

class QongiroqManager:
    """
    WebRTC signaling server.

    WebRTC qanday ishlaydi:
    1. Fayzullo Ali ga qo'ng'iroq qiladi
    2. Server ikkalasiga "offer" va "answer" uzatadi
    3. ICE candidate lar almashiladi
    4. To'g'ridan-to'g'ri peer-to-peer ulanish o'rnatiladi
    5. Ovoz/video server orqali emas — to'g'ridan-to'g'ri uzatiladi!

    Bu Telegram va WhatsApp dan ham xavfsizroq —
    chunki media server orqali o'tmaydi!
    """

    def __init__(self):
        # Aktiv WebSocket ulanishlar {user_id: websocket}
        self.ulanishlar: Dict[int, WebSocket] = {}

        # Aktiv qo'ng'iroqlar {caller_id: receiver_id}
        self.aktiv_qongiroqlar: Dict[int, int] = {}

        # Qo'ng'iroq tarixi
        self.tarix = []

    async def ulash(self, websocket: WebSocket, user_id: int):
        """Foydalanuvchini signaling serverga ulaymiz"""
        await websocket.accept()
        self.ulanishlar[user_id] = websocket
        print(f"📞 Qo'ng'iroq serveriga ulandi: User {user_id}")

    def uzish(self, user_id: int):
        """Foydalanuvchini uzamiz"""
        if user_id in self.ulanishlar:
            del self.ulanishlar[user_id]

        # Aktiv qo'ng'iroqni ham tugatamiz
        if user_id in self.aktiv_qongiroqlar:
            del self.aktiv_qongiroqlar[user_id]

    async def signal_yuborish(self, receiver_id: int, signal: dict) -> bool:
        """
        Signal ma'lumotini yuboradi.
        Signallar: offer, answer, ice-candidate, qabul_qilindi, rad_etildi, tugatildi
        """
        if receiver_id in self.ulanishlar:
            await self.ulanishlar[receiver_id].send_text(
                json.dumps(signal, ensure_ascii=False)
            )
            return True
        return False

    def onlayn_mi(self, user_id: int) -> bool:
        """Foydalanuvchi onlayn ekanligini tekshiradi"""
        return user_id in self.ulanishlar


# Global manager
qongiroq_manager = QongiroqManager()


# ==========================================
# WEBSOCKET SIGNALING ENDPOINT
# ==========================================

@router.websocket("/ws/{user_id}")
async def qongiroq_websocket(websocket: WebSocket, user_id: int):
    """
    WebRTC Signaling WebSocket.

    Ulanish: ws://localhost:8000/calls/ws/{user_id}

    Signal turlari:

    1. QONGIROQ BOSHLASH:
    {
        "tur": "qongiroq",
        "receiver_id": 2,
        "qongiroq_turi": "ovoz"  yoki  "video"
    }

    2. OFFER YUBORISH (WebRTC):
    {
        "tur": "offer",
        "receiver_id": 2,
        "sdp": "v=0\\r\\no=..."
    }

    3. ANSWER YUBORISH (WebRTC):
    {
        "tur": "answer",
        "receiver_id": 2,
        "sdp": "v=0\\r\\no=..."
    }

    4. ICE CANDIDATE:
    {
        "tur": "ice",
        "receiver_id": 2,
        "candidate": {...}
    }

    5. QABUL QILISH:
    {
        "tur": "qabul",
        "caller_id": 1
    }

    6. RAD ETISH:
    {
        "tur": "rad",
        "caller_id": 1
    }

    7. TUGATISH:
    {
        "tur": "tugatish",
        "receiver_id": 2
    }
    """

    await qongiroq_manager.ulash(websocket, user_id)

    try:
        while True:
            # Signal kutamiz
            data = await websocket.receive_text()
            signal = json.loads(data)
            tur = signal.get("tur")

            # ------------------------------------------
            # QONGIROQ BOSHLASH
            # ------------------------------------------
            if tur == "qongiroq":
                receiver_id = int(signal["receiver_id"])
                qongiroq_turi = signal.get("qongiroq_turi", "ovoz")

                # Qabul qiluvchi onlayn ekanligini tekshiramiz
                if not qongiroq_manager.onlayn_mi(receiver_id):
                    await websocket.send_text(json.dumps({
                        "tur": "xato",
                        "xabar": "Foydalanuvchi onlayn emas!"
                    }))
                    continue

                # Qabul qiluvchi allaqachon qo'ng'iroqda ekanligini tekshiramiz
                if receiver_id in qongiroq_manager.aktiv_qongiroqlar:
                    await websocket.send_text(json.dumps({
                        "tur": "band",
                        "xabar": "Foydalanuvchi hozir band!"
                    }))
                    continue

                # Aktiv qo'ng'iroqni qayd etamiz
                qongiroq_manager.aktiv_qongiroqlar[user_id] = receiver_id

                # Qabul qiluvchiga qo'ng'iroq kelayotganini bildiramiz
                await qongiroq_manager.signal_yuborish(receiver_id, {
                    "tur": "kelayotgan_qongiroq",
                    "caller_id": user_id,
                    "qongiroq_turi": qongiroq_turi,
                    "vaqt": datetime.now(timezone.utc).isoformat()
                })

                print(f"📞 Qo'ng'iroq: User{user_id} -> User{receiver_id} ({qongiroq_turi})")

            # ------------------------------------------
            # WEBRTC OFFER (Qo'ng'iroq boshlagan tomondan)
            # ------------------------------------------
            elif tur == "offer":
                receiver_id = int(signal["receiver_id"])

                # Offer ni qabul qiluvchiga yuboramiz
                await qongiroq_manager.signal_yuborish(receiver_id, {
                    "tur": "offer",
                    "caller_id": user_id,
                    "sdp": signal["sdp"]
                })

            # ------------------------------------------
            # WEBRTC ANSWER (Qabul qilgan tomondan)
            # ------------------------------------------
            elif tur == "answer":
                caller_id = int(signal["caller_id"])

                # Answer ni qo'ng'iroq qilgan tomonga yuboramiz
                await qongiroq_manager.signal_yuborish(caller_id, {
                    "tur": "answer",
                    "receiver_id": user_id,
                    "sdp": signal["sdp"]
                })

            # ------------------------------------------
            # ICE CANDIDATE — Ulanish yo'lini topish
            # ------------------------------------------
            elif tur == "ice":
                receiver_id = int(signal["receiver_id"])

                # ICE candidate ni ikkinchi tomonga yuboramiz
                await qongiroq_manager.signal_yuborish(receiver_id, {
                    "tur": "ice",
                    "sender_id": user_id,
                    "candidate": signal["candidate"]
                })

            # ------------------------------------------
            # QABUL QILISH
            # ------------------------------------------
            elif tur == "qabul":
                caller_id = int(signal["caller_id"])

                # Qo'ng'iroq qiluvchiga qabul qilingani xabarini yuboramiz
                await qongiroq_manager.signal_yuborish(caller_id, {
                    "tur": "qabul_qilindi",
                    "receiver_id": user_id
                })

                # Tarixga yozamiz
                qongiroq_manager.tarix.append({
                    "caller_id": caller_id,
                    "receiver_id": user_id,
                    "holat": "qabul_qilindi",
                    "vaqt": datetime.now(timezone.utc).isoformat()
                })

            # ------------------------------------------
            # RAD ETISH
            # ------------------------------------------
            elif tur == "rad":
                caller_id = int(signal["caller_id"])

                # Qo'ng'iroq qiluvchiga rad etilgani xabarini yuboramiz
                await qongiroq_manager.signal_yuborish(caller_id, {
                    "tur": "rad_etildi",
                    "receiver_id": user_id,
                    "xabar": "Qo'ng'iroq rad etildi!"
                })

                # Aktiv qo'ng'iroqni o'chiramiz
                if caller_id in qongiroq_manager.aktiv_qongiroqlar:
                    del qongiroq_manager.aktiv_qongiroqlar[caller_id]

                # Tarixga yozamiz
                qongiroq_manager.tarix.append({
                    "caller_id": caller_id,
                    "receiver_id": user_id,
                    "holat": "rad_etildi",
                    "vaqt": datetime.now(timezone.utc).isoformat()
                })

            # ------------------------------------------
            # QONGIROQNI TUGATISH
            # ------------------------------------------
            elif tur == "tugatish":
                receiver_id = int(signal.get("receiver_id", 0))

                # Ikkinchi tomonga tugatilgani xabarini yuboramiz
                await qongiroq_manager.signal_yuborish(receiver_id, {
                    "tur": "tugatildi",
                    "sender_id": user_id,
                    "xabar": "Qo'ng'iroq tugadi!"
                })

                # Aktiv qo'ng'iroqni o'chiramiz
                if user_id in qongiroq_manager.aktiv_qongiroqlar:
                    del qongiroq_manager.aktiv_qongiroqlar[user_id]

                print(f"📵 Qo'ng'iroq tugadi: User{user_id} -> User{receiver_id}")

    except WebSocketDisconnect:
        # Foydalanuvchi uzildi — aktiv qo'ng'iroqni ham tugatamiz
        if user_id in qongiroq_manager.aktiv_qongiroqlar:
            receiver_id = qongiroq_manager.aktiv_qongiroqlar[user_id]
            await qongiroq_manager.signal_yuborish(receiver_id, {
                "tur": "tugatildi",
                "sender_id": user_id,
                "xabar": "Ulanish uzildi!"
            })

        qongiroq_manager.uzish(user_id)


# ==========================================
# REST API ENDPOINTLAR
# ==========================================

@router.get("/onlayn", summary="Onlayn foydalanuvchilar")
async def onlayn_foydalanuvchilar():
    """Hozir qo'ng'iroq serveriga ulangan foydalanuvchilar"""
    return {
        "onlayn": list(qongiroq_manager.ulanishlar.keys()),
        "soni": len(qongiroq_manager.ulanishlar),
        "aktiv_qongiroqlar": len(qongiroq_manager.aktiv_qongiroqlar)
    }


@router.get("/tarix", summary="Qo'ng'iroqlar tarixi")
async def qongiroqlar_tarixi():
    """Barcha qo'ng'iroqlar tarixi"""
    return {
        "tarix": qongiroq_manager.tarix,
        "jami": len(qongiroq_manager.tarix)
    }