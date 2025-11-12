# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class Earthquake(Base):
    """Deprem modeli"""
    __tablename__ = "earthquakes"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True)
    timestamp = Column(DateTime, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    magnitude = Column(Float, index=True)
    depth = Column(Float)
    location = Column(String)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Anomaly(Base):
    """Anomali modeli"""
    __tablename__ = "anomalies"
    
    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    radius_km = Column(Float)
    z_score = Column(Float)
    earthquake_count = Column(Integer)
    baseline_rate = Column(Float)
    current_rate = Column(Float)
    location = Column(String)
    is_active = Column(Boolean, default=True)
    detected_at = Column(DateTime)
    resolved_at = Column(DateTime, nullable=True)
    alert_level = Column(String, nullable=True)
    anomaly_type = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AlertLog(Base):
    """Email uyarı log modeli"""
    __tablename__ = "alert_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String)
    anomaly_id = Column(Integer, nullable=True)
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String)

# Database bağlantısı
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    print(f"✅ DATABASE_URL bulundu: {DATABASE_URL[:30]}...")
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    raise ValueError("❌ DATABASE_URL environment variable bulunamadı!")

def init_db():
    """Veritabanı tablolarını oluştur"""
    Base.metadata.create_all(bind=engine)
    print("✅ Veritabanı tabloları oluşturuldu")

if __name__ == "__main__":
    init_db()