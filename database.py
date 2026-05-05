from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite — oddiy fayl bazasi, o'rnatish shart emas
SQLALCHEMY_DATABASE_URL = "sqlite:///./messenger.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Har bir so'rov uchun DB sessiyasi ochadi,
    so'rov tugagach avtomatik yopadi.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()