# -*- coding: utf-8 -*-
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from database.models import Earthquake, Anomaly, SessionLocal
import os

app = FastAPI(title="Deprem Takip Sistemi API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Static files ve frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Ana sayfa - Harita"""
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/earthquakes")
async def get_earthquakes(
    hours: int = Query(default=48, description="Son X saatteki depremler"),
    min_magnitude: float = Query(default=2.5, description="Minimum büyüklük"),
    source: str = Query(default="all", description="Kaynak: all, Kandilli, USGS"),
    db: Session = Depends(get_db)
):
    """Deprem verilerini getir"""
    
    # Zaman filtresi
    start_time = datetime.now() - timedelta(hours=hours)
    
    # Query oluştur
    query = db.query(Earthquake).filter(
        Earthquake.timestamp >= start_time,
        Earthquake.magnitude >= min_magnitude
    )
    
    # Kaynak filtresi
    if source != "all":
        query = query.filter(Earthquake.source == source)
    
    earthquakes = query.order_by(Earthquake.timestamp.desc()).all()
    
    return {
        "count": len(earthquakes),
        "earthquakes": [
            {
                "id": eq.id,
                "event_id": eq.event_id,
                "timestamp": eq.timestamp.isoformat(),
                "latitude": eq.latitude,
                "longitude": eq.longitude,
                "magnitude": eq.magnitude,
                "depth": eq.depth,
                "location": eq.location,
                "source": eq.source
            }
            for eq in earthquakes
        ]
    }

@app.get("/api/anomalies")
async def get_anomalies(db: Session = Depends(get_db)):
    """Aktif anomalileri getir - YENİ MODEL"""
    
    try:
        # Yeni model yapısını kullan
        anomalies = db.query(Anomaly).filter(Anomaly.is_active == True).all()
        
        return {
            "count": len(anomalies),
            "anomalies": [
                {
                    "id": a.id,
                    "latitude": a.latitude,
                    "longitude": a.longitude,
                    "radius_km": a.radius_km,
                    "z_score": a.z_score,
                    "earthquake_count": a.earthquake_count,
                    "baseline_rate": a.baseline_rate if a.baseline_rate else 0.0,
                    "current_rate": a.current_rate if a.current_rate else 0.0,
                    "location": a.location,
                    "detected_at": a.detected_at.isoformat() if a.detected_at else datetime.now().isoformat(),
                    "is_active": a.is_active,
                    "alert_level": "red" if a.z_score > 5 else "orange" if a.z_score > 3 else "yellow",
                    "anomaly_type": "frequency",
                    "description": f"{a.earthquake_count} deprem tespit edildi - Z-score: {a.z_score:.1f}"
                }
                for a in anomalies
            ]
        }
    except Exception as e:
        # Eğer anomalies tablosu boşsa veya yoksa
        print(f"Anomaly query hatası: {e}")
        return {
            "count": 0,
            "anomalies": []
        }

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Genel istatistikler"""
    
    now = datetime.now()
    last_24h = now - timedelta(hours=24)
    
    # Son 24 saatteki depremler
    earthquakes_24h = db.query(Earthquake).filter(
        Earthquake.timestamp >= last_24h
    ).all()
    
    # Aktif anomaliler - YENİ MODEL
    try:
        active_anomalies = db.query(Anomaly).filter(Anomaly.is_active == True).count()
    except:
        active_anomalies = 0
    
    # En büyük deprem
    max_magnitude = 0.0
    if earthquakes_24h:
        max_magnitude = max(eq.magnitude for eq in earthquakes_24h)
    
    return {
        "total_24h": len(earthquakes_24h),
        "max_magnitude_24h": max_magnitude,
        "active_anomalies": active_anomalies,
        "last_update": now.isoformat()
    }

@app.get("/api/earthquake/{earthquake_id}")
async def get_earthquake_detail(earthquake_id: int, db: Session = Depends(get_db)):
    """Tek bir depremin detayları"""
    
    earthquake = db.query(Earthquake).filter(Earthquake.id == earthquake_id).first()
    
    if not earthquake:
        return {"error": "Deprem bulunamadı"}
    
    return {
        "id": earthquake.id,
        "event_id": earthquake.event_id,
        "timestamp": earthquake.timestamp.isoformat(),
        "latitude": earthquake.latitude,
        "longitude": earthquake.longitude,
        "magnitude": earthquake.magnitude,
        "depth": earthquake.depth,
        "location": earthquake.location,
        "source": earthquake.source
    }

@app.get("/api/region-stats")
async def get_region_stats(
    lat: float = Query(..., description="Enlem"),
    lon: float = Query(..., description="Boylam"),
    radius_km: float = Query(default=50, description="Yarıçap (km)"),
    hours: int = Query(default=168, description="Son X saat"),
    db: Session = Depends(get_db)
):
    """Belirli bir bölgenin istatistikleri"""
    
    start_time = datetime.now() - timedelta(hours=hours)
    
    # Basit mesafe hesabı (yaklaşık)
    lat_range = radius_km / 111  # 1 derece ~ 111km
    lon_range = radius_km / (111 * 0.7)  # Türkiye için yaklaşık
    
    earthquakes = db.query(Earthquake).filter(
        Earthquake.timestamp >= start_time,
        Earthquake.latitude.between(lat - lat_range, lat + lat_range),
        Earthquake.longitude.between(lon - lon_range, lon + lon_range)
    ).all()
    
    if not earthquakes:
        return {
            "count": 0,
            "max_magnitude": 0,
            "avg_magnitude": 0,
            "earthquakes": []
        }
    
    return {
        "count": len(earthquakes),
        "max_magnitude": max(eq.magnitude for eq in earthquakes),
        "avg_magnitude": sum(eq.magnitude for eq in earthquakes) / len(earthquakes),
        "earthquakes": [
            {
                "timestamp": eq.timestamp.isoformat(),
                "magnitude": eq.magnitude,
                "depth": eq.depth,
                "location": eq.location
            }
            for eq in earthquakes[-20:]  # Son 20 deprem
        ]
    }

@app.get("/health")
async def health_check():
    """Sistem sağlık kontrolü"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("🌍 DEPREM TAKİP SİSTEMİ API")
    print("="*60)
    print("✅ API başlatılıyor...")
    print("📍 URL: http://localhost:8000")
    print("📊 Dokümantasyon: http://localhost:8000/docs")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")