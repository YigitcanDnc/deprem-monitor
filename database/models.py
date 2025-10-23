# -*- coding: utf-8 -*-
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry
from datetime import datetime
import os

# Railway ve local için DATABASE_URL okuma
DATABASE_URL = os.environ.get("DATABASE_URL")

# Eğer bulunamazsa .env'den dene
if not DATABASE_URL:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL bulunamadı! Railway Variables veya .env dosyasını kontrol et.")

# PostgreSQL URL düzeltmesi (Railway postgres:// -> postgresql:// olabilir)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"✅ DATABASE_URL bulundu: {DATABASE_URL[:30]}...")

# SQLAlchemy engine oluştur
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Base ve Session
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Earthquake Model
class Earthquake(Base):
    __tablename__ = "earthquakes"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    magnitude = Column(Float, nullable=False, index=True)
    depth = Column(Float, nullable=False)
    location = Column(String, nullable=False)
    source = Column(String, nullable=False, index=True)
    geometry = Column(Geometry('POINT', srid=4326))
    created_at = Column(DateTime, default=datetime.utcnow)

# Anomaly Model
class Anomaly(Base):
    __tablename__ = "anomalies"
    
    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False)
    z_score = Column(Float, nullable=False)
    earthquake_count = Column(Integer, nullable=False)
    baseline_rate = Column(Float)
    current_rate = Column(Float)
    location = Column(String)
    is_active = Column(Boolean, default=True, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)

# Alert Log Model
class AlertLog(Base):
    __tablename__ = "alert_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    anomaly_id = Column(Integer, nullable=False, index=True)
    alert_type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)
    recipient = Column(String)
    status = Column(String, default="sent")

# Database initialization
def init_db():
    """Veritabanı tablolarını oluştur"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Veritabanı tabloları oluşturuldu")
        return True
    except Exception as e:
        print(f"❌ Veritabanı hatası: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Veritabanı başlatılıyor...")
    if init_db():
        print("✅ Başarılı!")
    else:
        print("❌ Başarısız!")