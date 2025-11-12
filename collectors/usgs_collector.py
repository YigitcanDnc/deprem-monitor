# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from datetime import datetime, timedelta, timezone
from database.models import Earthquake, SessionLocal
import hashlib

class USGSCollector:
    def __init__(self):
        self.base_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
        self.source = "USGS"
        
        # Türkiye sınırları (yaklaşık)
        self.min_latitude = 36.0
        self.max_latitude = 42.0
        self.min_longitude = 26.0
        self.max_longitude = 45.0
    
    def generate_event_id(self, timestamp, lat, lon, magnitude):
        """
        Timestamp, konum ve büyüklükten benzersiz ID oluştur
        Kandilli ile aynı mantık
        """
        unique_string = f"usgs-{timestamp}-{lat:.3f}-{lon:.3f}-{magnitude:.1f}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:16]
    
    def collect(self, days=7, min_magnitude=2.5):
        """USGS'den veri topla"""
        print("\n" + "="*50)
        print("🚀 USGS Deprem Verisi Toplama Başladı")
        print("="*50)
        
        try:
            # Tarih aralığı
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=days)
            
            print("🌍 USGS'den veri çekiliyor...")
            print(f"   📅 Tarih aralığı: {start_time.strftime('%Y-%m-%d')} - {end_time.strftime('%Y-%m-%d')}")
            print(f"   📊 Min. büyüklük: {min_magnitude}")
            
            # API parametreleri
            params = {
                'format': 'geojson',
                'starttime': start_time.isoformat(),
                'endtime': end_time.isoformat(),
                'minlatitude': self.min_latitude,
                'maxlatitude': self.max_latitude,
                'minlongitude': self.min_longitude,
                'maxlongitude': self.max_longitude,
                'minmagnitude': min_magnitude,
                'orderby': 'time-asc'
            }
            
            # API isteği
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            features = data.get('features', [])
            
            earthquakes = []
            
            for feature in features:
                try:
                    props = feature['properties']
                    coords = feature['geometry']['coordinates']
                    
                    # Timestamp (milisaniye)
                    timestamp_ms = props['time']
                    dt_utc = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                    
                    # Koordinatlar
                    lat = coords[1]
                    lon = coords[0]
                    depth = coords[2]
                    magnitude = props['mag']
                    
                    # Event ID oluştur (timestamp + konum + büyüklük)
                    event_id = self.generate_event_id(dt_utc, lat, lon, magnitude)
                    
                    earthquake = {
                        'event_id': event_id,
                        'timestamp': dt_utc,
                        'latitude': lat,
                        'longitude': lon,
                        'depth': depth,
                        'magnitude': magnitude,
                        'location': props.get('place', 'Unknown'),
                        'source': self.source
                    }
                    
                    earthquakes.append(earthquake)
                    
                except (KeyError, ValueError, IndexError) as e:
                    continue
            
            print(f"✅ {len(earthquakes)} deprem verisi alındı")
            
            # Veritabanına kaydet
            self.save_to_database(earthquakes)
            
            print("="*50 + "\n")
            
            return earthquakes
            
        except Exception as e:
            print(f"❌ USGS veri toplama hatası: {e}")
            print("="*50 + "\n")
            return []
    
    def save_to_database(self, earthquakes):
        """Depremleri veritabanına kaydet"""
        db = SessionLocal()
        
        try:
            new_count = 0
            existing_count = 0
            
            for eq_data in earthquakes:
                # Event ID ile kontrol et
                existing = db.query(Earthquake).filter(
                    Earthquake.event_id == eq_data['event_id']
                ).first()
                
                if not existing:
                    # Yeni deprem ekle
                    earthquake = Earthquake(**eq_data)
                    db.add(earthquake)
                    new_count += 1
                else:
                    existing_count += 1
            
            # Commit
            db.commit()
            
            print("💾 Veritabanına kaydedildi:")
            print(f"   ✅ {new_count} yeni deprem")
            print(f"   ⏭️  {existing_count} zaten mevcut")
            
        except Exception as e:
            print(f"❌ Veritabanı kayıt hatası: {e}")
            db.rollback()
        finally:
            db.close()

if __name__ == "__main__":
    collector = USGSCollector()
    collector.collect(days=14, min_magnitude=2.5)