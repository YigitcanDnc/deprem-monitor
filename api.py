# -*- coding: utf-8 -*-
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from database.models import Earthquake, SessionLocal
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
    """Aktif anomalileri getir - Mevcut tablo yapısına göre"""
    
    # SQL ile direkt çek (model uyumsuz olduğu için)
    query = text("""
        SELECT 
            id, 
            region, 
            score, 
            alert_level, 
            anomaly_type,
            description,
            start_time,
            is_resolved
        FROM anomalies 
        WHERE is_resolved = false
        ORDER BY score DESC
    """)
    
    result = db.execute(query).fetchall()
    
    # Bölge isimlerinden koordinat tahmini yap
    def extract_coords_from_region(region_name):
        """Bölge isminden yaklaşık koordinat çıkar"""
        # Türkiye'nin bazı bölgeleri için sabit koordinatlar
        regions = {
            'KUTAHYA': (39.4242, 29.9833),
            'KÜTAHYA': (39.4242, 29.9833),
            'BALIKESIR': (39.6484, 27.8826),
            'MANISA': (38.6191, 27.4289),
            'MALATYA': (38.3552, 38.3095),
            'ADANA': (37.0000, 35.3213),
            'MUGLA': (37.2153, 28.3636),
            'MUĞLA': (37.2153, 28.3636),
            'IZMIR': (38.4237, 27.1428),
            'İZMİR': (38.4237, 27.1428),
            'HISARCIK': (39.2463, 29.2725),
            'SIMAV': (39.0884, 28.9789),
            'SINDIRGI': (39.2381, 28.1826),
            'AKHISAR': (38.9185, 27.8339),
            'YAZIHAN': (38.6167, 38.0167),
            'PUTURGE': (38.2000, 38.9667),
            'YESILYURT': (38.2783, 38.3304),
            'FEKE': (37.8167, 35.9167),
            'ULA': (37.1000, 28.4167),
            'EMET': (39.3414, 29.2619),
            'KALE': (38.4667, 38.9833),
            'KOZAN': (37.4500, 35.8167),
            'KOYCEGIZ': (36.9667, 28.6833),
            'MARMARIS': (36.8547, 28.2744),
        }
        
        if not region_name:
            return (39.0, 35.0)
        
        region_upper = region_name.upper()
        
        # Bölge isminde şehir adı ara
        for city, coords in regions.items():
            if city in region_upper:
                return coords
        
        # Bulunamazsa Türkiye merkezi
        return (39.0, 35.0)
    
    anomalies = []
    for row in result:
        lat, lon = extract_coords_from_region(row[1])  # region
        
        # Yarıçapı score'a göre ayarla (daha büyük score = daha büyük alan)
        radius = min(50.0 + (row[2] if row[2] else 0) * 0.5, 100.0)
        
        anomalies.append({
            "id": row[0],
            "latitude": lat,
            "longitude": lon,
            "radius_km": radius,
            "z_score": row[2] if row[2] else 0.0,  # score
            "earthquake_count": 0,  # Bilinmiyor
            "baseline_rate": 0.0,
            "current_rate": 0.0,
            "location": row[1],  # region
            "detected_at": row[6].isoformat() if row[6] else datetime.now().isoformat(),  # start_time
            "is_active": not row[7] if row[7] is not None else True,  # is_resolved tersine
            "alert_level": row[3] if row[3] else "orange",  # alert_level
            "anomaly_type": row[4] if row[4] else "frequency",  # anomaly_type
            "description": row[5] if row[5] else "Anomali tespit edildi"  # description
        })
    
    return {
        "count": len(anomalies),
        "anomalies": anomalies
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
    
    # Aktif anomaliler (SQL ile)
    active_anomalies_query = text("SELECT COUNT(*) FROM anomalies WHERE is_resolved = false")
    active_anomalies = db.execute(active_anomalies_query).scalar()
    
    # En büyük deprem
    max_magnitude = 0.0
    if earthquakes_24h:
        max_magnitude = max(eq.magnitude for eq in earthquakes_24h)
    
    return {
        "total_24h": len(earthquakes_24h),
        "max_magnitude_24h": max_magnitude,
        "active_anomalies": active_anomalies if active_anomalies else 0,
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