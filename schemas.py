from pydantic import BaseModel
from datetime import datetime

# Ro'yxatdan o'tish uchun
class UserCreate(BaseModel):
    username: str
    full_name: str
    password: str

# Login uchun
class UserLogin(BaseModel):
    username: str
    password: str

# Javob uchun (parolsiz)
class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    created_at: datetime

    class Config:
        from_attributes = True

# Token
class Token(BaseModel):
    access_token: str
    token_type: str

# Xabar
class MessageCreate(BaseModel):
    receiver_id: int
    content: str

class MessageOut(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True