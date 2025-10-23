from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry
from datetime import datetime
import os
from dotenv import load_dotenv

# .env dosyasından oku
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL bulunamadı! .env dosyasını kontrol et.")

# Veritabanı bağlantısı
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Earthquake(Base):
    """Deprem verileri tablosu"""
    __tablename__ = "earthquakes"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True)  # Benzersiz deprem ID
    timestamp = Column(DateTime, index=True)            # Deprem zamanı
    latitude = Column(Float)                            # Enlem
    longitude = Column(Float)                           # Boylam
    magnitude = Column(Float, index=True)               # Büyüklük
    depth = Column(Float)                               # Derinlik (km)
    location = Column(String)                           # Konum açıklaması
    source = Column(String)                             # AFAD, USGS, vb.
    geometry = Column(Geometry('POINT', srid=4326))     # Coğrafi nokta
    created_at = Column(DateTime, default=datetime.utcnow)


class Anomaly(Base):
    """Tespit edilen anomaliler"""
    __tablename__ = "anomalies"
    
    id = Column(Integer, primary_key=True, index=True)
    region = Column(String)                             # Bölge adı
    start_time = Column(DateTime)                       # Anomali başlangıcı
    end_time = Column(DateTime, nullable=True)          # Anomali bitişi
    anomaly_type = Column(String)                       # frequency, b_value, vb.
    score = Column(Float)                               # Anomali skoru
    alert_level = Column(String)                        # yellow, orange, red
    is_resolved = Column(Boolean, default=False)        # Çözüldü mü?
    description = Column(String)                        # Açıklama
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertLog(Base):
    """Gönderilen uyarılar"""
    __tablename__ = "alert_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    anomaly_id = Column(Integer)                        # Hangi anomali için
    sent_at = Column(DateTime, default=datetime.utcnow)
    recipient = Column(String)                          # Alıcı email
    alert_type = Column(String)                         # email, sms
    message = Column(String)                            # Mesaj içeriği


def init_database():
    """Veritabanı tablolarını oluştur"""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Veritabanı tabloları başarıyla oluşturuldu!")
        print(f"📊 Tablolar: {', '.join(Base.metadata.tables.keys())}")
        return True
    except Exception as e:
        print(f"❌ Veritabanı hatası: {e}")
        return False


def get_db():
    """Veritabanı session'ı oluştur"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    print("🔧 Veritabanı tabloları oluşturuluyor...")
    init_database()