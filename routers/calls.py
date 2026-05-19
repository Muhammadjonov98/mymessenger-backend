# ==========================================
# QONGIROQ ROUTER — WebRTC Signaling
# TUZATILGAN VERSIYA - O'TKAZIB YUBORILGAN SIGNALLAR VA RECONNECTION
# ==========================================

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Optional, List
import json
from datetime import datetime, timezone
import asyncio

router = APIRouter(prefix="/calls", tags=["Qo'ng'iroqlar"])


class QongiroqManager:
    """
    WebRTC signaling server - to'g'rilangan ulanish boshqaruvi
    
    Xususiyatlari:
    - O'tkazib yuborilgan signallarni saqlaydi
    - Reconnection logic
    - ICE candidate buffering
    - Aktiv qongiroqlar boshqaruvi
    """

    def __init__(self):
        self.ulanishlar: Dict[int, WebSocket] = {}  # Aktiv ulanishlar
        self.aktiv_qongiroqlar: Dict[int, int] = {}  # {caller_id: receiver_id}
        self.tarix = []  # Qongiroqlar tarixi
        self.pending_signals: Dict[int, List[dict]] = {}  # O'tkazib yuborilgan signallar
        self.ice_candidates: Dict[str, List[dict]] = {}  # ICE candidatlar buffer

    async def ulash(self, websocket: WebSocket, user_id: int):
        """
        Foydalanuvchini signaling serverga ulaymiz.
        O'tkazib yuborilgan signallarni qayta yuboramiz.
        """
        await websocket.accept()
        self.ulanishlar[user_id] = websocket
        print(f"📞 Qo'ng'iroq serveriga ulandi: User {user_id}")
        print(f"   Aktiv ulanishlar: {len(self.ulanishlar)}")

        # ✅ O'TKAZIB YUBORILGAN SIGNALLARNI YUBORAMIZ
        if user_id in self.pending_signals:
            print(f"   ↩️  {len(self.pending_signals[user_id])} ta o'tkazib yuborilgan signal yuborilmoqda...")
            for signal in self.pending_signals[user_id]:
                try:
                    await websocket.send_text(json.dumps(signal, ensure_ascii=False))
                    await asyncio.sleep(0.1)  # Oz kutamiz
                except Exception as e:
                    print(f"   ⚠️  Signal yuborish xatosi: {e}")
            del self.pending_signals[user_id]

        # ✅ ICE CANDIDATLARNI YUBORAMIZ
        key = f"pending_ice_{user_id}"
        if key in self.ice_candidates:
            print(f"   🧊 {len(self.ice_candidates[key])} ta ICE candidate yuborilmoqda...")
            for candidate in self.ice_candidates[key]:
                try:
                    await websocket.send_text(json.dumps(candidate, ensure_ascii=False))
                    await asyncio.sleep(0.05)
                except Exception as e:
                    print(f"   ⚠️  ICE candidate xatosi: {e}")
            del self.ice_candidates[key]

    def uzish(self, user_id: int):
        """
        Foydalanuvchini uzamiz va aktiv qongiroqni tugatamiz
        """
        if user_id in self.ulanishlar:
            del self.ulanishlar[user_id]
            print(f"❌ Foydalanuvchi uzildi: User {user_id}")

        if user_id in self.aktiv_qongiroqlar:
            del self.aktiv_qongiroqlar[user_id]

    async def signal_yuborish(self, receiver_id: int, signal: dict) -> bool:
        """
        Signal ma'lumotini yuboradi yoki oflayn bo'lsa saqlaydi.
        
        Qaytaradi: True - muvaffaqiyatli yuborildi, False - saqland
        """
        if receiver_id in self.ulanishlar:
            try:
                websocket = self.ulanishlar[receiver_id]
                await websocket.send_text(
                    json.dumps(signal, ensure_ascii=False)
                )
                print(f"   ✅ Signal yuborildi: {signal.get('tur')} -> User {receiver_id}")
                return True
            except Exception as e:
                print(f"   ⚠️  Signal yuborish xatosi: {e}")
                self.uzish(receiver_id)
                # Saqlaydi
                self._signal_saqla(receiver_id, signal)
                return False
        else:
            # ✅ OFLAYN BO'LSA SAQLAYMIZ
            self._signal_saqla(receiver_id, signal)
            return False

    def _signal_saqla(self, receiver_id: int, signal: dict):
        """
        Signalni oflayn foydalanuvchi uchun saqlaydi
        """
        if receiver_id not in self.pending_signals:
            self.pending_signals[receiver_id] = []
        self.pending_signals[receiver_id].append(signal)
        print(f"   📦 Signal saqland: {signal.get('tur')} -> User {receiver_id} (oflayn)")

    async def ice_candidate_saqla(self, receiver_id: int, candidate: dict):
        """
        ICE candidatni saqlaydi va yuboradi
        """
        key = f"pending_ice_{receiver_id}"
        
        if receiver_id in self.ulanishlar:
            try:
                await self.ulanishlar[receiver_id].send_text(
                    json.dumps(candidate, ensure_ascii=False)
                )
            except:
                # Xato bo'lsa saqlaymiz
                if key not in self.ice_candidates:
                    self.ice_candidates[key] = []
                self.ice_candidates[key].append(candidate)
        else:
            # Oflayn bo'lsa saqlaymiz
            if key not in self.ice_candidates:
                self.ice_candidates[key] = []
            self.ice_candidates[key].append(candidate)

    def onlayn_mi(self, user_id: int) -> bool:
        """
        Foydalanuvchi onlayn ekanligini tekshiradi
        """
        return user_id in self.ulanishlar

    def get_stats(self) -> dict:
        """
        Server statistikasi
        """
        return {
            "onlayn_foydalanuvchilar": len(self.ulanishlar),
            "aktiv_qongiroqlar": len(self.aktiv_qongiroqlar),
            "o_tkazib_yuborilgan_signallar": sum(len(v) for v in self.pending_signals.values()),
            "ice_buffer_hajmi": sum(len(v) for v in self.ice_candidates.values())
        }


# Global manager
qongiroq_manager = QongiroqManager()


# ==========================================
# WEBSOCKET ENDPOINT
# ==========================================

@router.websocket("/ws/{user_id}")
async def qongiroq_websocket(websocket: WebSocket, user_id: int):
    """
    WebRTC Signaling WebSocket - TUZATILGAN VERSIYA
    
    Signal turlari:
    1. qongiroq - Qongiroq boshlash
    2. offer - WebRTC offer
    3. answer - WebRTC answer
    4. ice - ICE candidate
    5. qabul - Qongiroqni qabul qilish
    6. rad - Qongiroqni rad etish
    7. tugatish - Qongiroqni tugatish
    """

    await qongiroq_manager.ulash(websocket, user_id)

    try:
        while True:
            # Signal kutamiz
            data = await websocket.receive_text()
            signal = json.loads(data)
            tur = signal.get("tur")
            
            print(f"\n📨 Signal qabul: {tur} from User {user_id}")

            # ------------------------------------------
            # QONGIROQ BOSHLASH
            # ------------------------------------------
            if tur == "qongiroq":
                receiver_id = int(signal["receiver_id"])
                qongiroq_turi = signal.get("qongiroq_turi", "ovoz")

                print(f"   📞 Qongiroq boshlash: {user_id} -> {receiver_id} ({qongiroq_turi})")

                # Qabul qiluvchi onlayn ekanligini tekshiramiz
                if not qongiroq_manager.onlayn_mi(receiver_id):
                    await websocket.send_text(json.dumps({
                        "tur": "xato",
                        "xabar": "Foydalanuvchi onlayn emas!",
                        "receiver_id": receiver_id
                    }, ensure_ascii=False))
                    print(f"   ⚠️  Receiver oflayn: {receiver_id}")
                    continue

                # Qabul qiluvchi allaqachon qo'ng'iroqda ekanligini tekshiramiz
                if receiver_id in qongiroq_manager.aktiv_qongiroqlar:
                    await websocket.send_text(json.dumps({
                        "tur": "band",
                        "xabar": "Foydalanuvchi hozir band!",
                        "receiver_id": receiver_id
                    }, ensure_ascii=False))
                    print(f"   ⚠️  Receiver band: {receiver_id}")
                    continue

                # Aktiv qo'ng'iroqni qayd etamiz
                qongiroq_manager.aktiv_qongiroqlar[user_id] = receiver_id

                # Qabul qiluvchiga qo'ng'iroq kelayotganini bildiramiz
                success = await qongiroq_manager.signal_yuborish(receiver_id, {
                    "tur": "kelayotgan_qongiroq",
                    "caller_id": user_id,
                    "qongiroq_turi": qongiroq_turi,
                    "vaqt": datetime.now(timezone.utc).isoformat()
                })

                # Yuboruvchiga tasdiq
                await websocket.send_text(json.dumps({
                    "tur": "qongiroq_yuborildi",
                    "receiver_id": receiver_id,
                    "status": "ok"
                }, ensure_ascii=False))

            # ------------------------------------------
            # WEBRTC OFFER (Qo'ng'iroq boshlagan tomondan)
            # ------------------------------------------
            elif tur == "offer":
                receiver_id = int(signal["receiver_id"])
                sdp = signal.get("sdp")

                print(f"   📤 Offer yuborilmoqda: {user_id} -> {receiver_id}")

                await qongiroq_manager.signal_yuborish(receiver_id, {
                    "tur": "offer",
                    "caller_id": user_id,
                    "sdp": sdp
                })

            # ------------------------------------------
            # WEBRTC ANSWER (Qabul qilgan tomondan)
            # ------------------------------------------
            elif tur == "answer":
                caller_id = int(signal.get("caller_id"))
                sdp = signal.get("sdp")

                print(f"   📥 Answer yuborilmoqda: {user_id} -> {caller_id}")

                await qongiroq_manager.signal_yuborish(caller_id, {
                    "tur": "answer",
                    "receiver_id": user_id,
                    "sdp": sdp
                })

            # ------------------------------------------
            # ICE CANDIDATE — Ulanish yo'lini topish
            # ------------------------------------------
            elif tur == "ice":
                receiver_id = int(signal["receiver_id"])
                candidate = signal.get("candidate")

                print(f"   🧊 ICE candidate: {user_id} -> {receiver_id}")

                await qongiroq_manager.ice_candidate_saqla(receiver_id, {
                    "tur": "ice",
                    "sender_id": user_id,
                    "candidate": candidate
                })

            # ------------------------------------------
            # QABUL QILISH
            # ------------------------------------------
            elif tur == "qabul":
                caller_id = int(signal["caller_id"])

                print(f"   ✅ Qongiroq qabul qilindi: {user_id} <- {caller_id}")

                await qongiroq_manager.signal_yuborish(caller_id, {
                    "tur": "qabul_qilindi",
                    "receiver_id": user_id
                })

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

                print(f"   ❌ Qongiroq rad etildi: {user_id} <- {caller_id}")

                await qongiroq_manager.signal_yuborish(caller_id, {
                    "tur": "rad_etildi",
                    "receiver_id": user_id,
                    "xabar": "Qo'ng'iroq rad etildi!"
                })

                if caller_id in qongiroq_manager.aktiv_qongiroqlar:
                    del qongiroq_manager.aktiv_qongiroqlar[caller_id]

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

                print(f"   📵 Qongiroq tugadi: {user_id} -> {receiver_id}")

                if receiver_id > 0:
                    await qongiroq_manager.signal_yuborish(receiver_id, {
                        "tur": "tugatildi",
                        "sender_id": user_id,
                        "xabar": "Qo'ng'iroq tugadi!"
                    })

                if user_id in qongiroq_manager.aktiv_qongiroqlar:
                    del qongiroq_manager.aktiv_qongiroqlar[user_id]

                qongiroq_manager.tarix.append({
                    "caller_id": user_id,
                    "receiver_id": receiver_id,
                    "holat": "tugadi",
                    "vaqt": datetime.now(timezone.utc).isoformat()
                })

    except WebSocketDisconnect:
        print(f"\n🔌 WebSocket uzildi: User {user_id}")
        
        # Aktiv qo'ng'iroqni tugatamiz
        if user_id in qongiroq_manager.aktiv_qongiroqlar:
            receiver_id = qongiroq_manager.aktiv_qongiroqlar[user_id]
            await qongiroq_manager.signal_yuborish(receiver_id, {
                "tur": "tugatildi",
                "sender_id": user_id,
                "xabar": "Ulanish uzildi!"
            })
            qongiroq_manager.tarix.append({
                "caller_id": user_id,
                "receiver_id": receiver_id,
                "holat": "uzildi",
                "vaqt": datetime.now(timezone.utc).isoformat()
            })

        qongiroq_manager.uzish(user_id)

    except Exception as e:
        print(f"\n⚠️  WebSocket xatosi: {e}")
        qongiroq_manager.uzish(user_id)


# ==========================================
# REST API ENDPOINTLAR
# ==========================================

@router.get("/onlayn", summary="Onlayn foydalanuvchilar")
async def onlayn_foydalanuvchilar():
    """
    Hozir qo'ng'iroq serveriga ulangan foydalanuvchilar
    """
    return {
        "onlayn": list(qongiroq_manager.ulanishlar.keys()),
        "soni": len(qongiroq_manager.ulanishlar),
        "aktiv_qongiroqlar": len(qongiroq_manager.aktiv_qongiroqlar),
        "statistika": qongiroq_manager.get_stats()
    }


@router.get("/tarix", summary="Qo'ng'iroqlar tarixi")
async def qongiroqlar_tarixi():
    """
    Barcha qo'ng'iroqlar tarixi
    """
    return {
        "tarix": qongiroq_manager.tarix[-100:],  # Oxirgi 100 ta
        "jami": len(qongiroq_manager.tarix),
        "aktiv": len(qongiroq_manager.aktiv_qongiroqlar)
    }


@router.get("/stats", summary="Server statistikasi")
async def server_stats():
    """
    Qongiroq serveri statistikasi
    """
    stats = qongiroq_manager.get_stats()
    return {
        **stats,
        "vaqt": datetime.now(timezone.utc).isoformat(),
        "pending_signals_count": len(qongiroq_manager.pending_signals),
        "ice_buffer_total": len(qongiroq_manager.ice_candidates)
    }
