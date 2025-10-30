import sys
import os

# Proje kök dizinini Python path'ine ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import Earthquake, SessionLocal

import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import Earthquake, SessionLocal

class USGSCollector:
    """USGS (Amerika Jeoloji Kurumu) deprem verilerini toplar"""
    
    def __init__(self):
        self.base_url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    
    def fetch_recent_earthquakes(self, days=7, min_magnitude=2.5, max_results=1000):
        """
        Son X günün depremlerini çek
        
        Args:
            days: Kaç gün geriye git
            min_magnitude: Minimum büyüklük
            max_results: Maksimum sonuç sayısı
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        params = {
            'format': 'geojson',
            'starttime': start_time.strftime('%Y-%m-%d'),
            'endtime': end_time.strftime('%Y-%m-%d'),
            'minmagnitude': min_magnitude,
            'limit': max_results,
            'orderby': 'time-asc'
        }
        
        try:
            print(f"🌍 USGS'den veri çekiliyor...")
            print(f"   📅 Tarih aralığı: {start_time.strftime('%Y-%m-%d')} - {end_time.strftime('%Y-%m-%d')}")
            print(f"   📊 Min. büyüklük: {min_magnitude}")
            
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            earthquakes = data.get('features', [])
            
            print(f"✅ {len(earthquakes)} deprem verisi alındı")
            return earthquakes
            
        except requests.exceptions.Timeout:
            print("❌ USGS zaman aşımı - sunucu yanıt vermiyor")
            return []
        except requests.exceptions.RequestException as e:
            print(f"❌ USGS bağlantı hatası: {e}")
            return []
        except Exception as e:
            print(f"❌ Beklenmeyen hata: {e}")
            return []
    
    def save_to_database(self, earthquakes):
        """Depremleri veritabanına kaydet"""
        db = SessionLocal()
        saved_count = 0
        skipped_count = 0
        
        try:
            for eq in earthquakes:
                props = eq['properties']
                coords = eq['geometry']['coordinates']
                
                # Bazı depremlerde magnitude null olabiliyor
                if props.get('mag') is None:
                    skipped_count += 1
                    continue
                
                event_id = f"usgs_{eq['id']}"
                
                # Zaten var mı kontrol et
                existing = db.query(Earthquake).filter_by(event_id=event_id).first()
                if existing:
                    skipped_count += 1
                    continue
                
                # Yeni deprem kaydı oluştur
                earthquake = Earthquake(
                    event_id=event_id,
                    timestamp=datetime.fromtimestamp(props['time'] / 1000),
                    latitude=coords[1],
                    longitude=coords[0],
                    magnitude=props['mag'],
                    depth=coords[2] if len(coords) > 2 else 0,
                    location=props.get('place', 'Bilinmiyor'),
                    source='USGS',
                    # geometry=f'POINT({coords[0]} {coords[1]})' # KALDIRILDI
                )
                
                db.add(earthquake)
                saved_count += 1
            
            db.commit()
            print(f"💾 Veritabanına kaydedildi:")
            print(f"   ✅ {saved_count} yeni deprem")
            print(f"   ⏭️  {skipped_count} zaten mevcut")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Veritabanına kaydetme hatası: {e}")
        finally:
            db.close()
    
    def collect(self, days=7, min_magnitude=2.5):
        """Ana toplama fonksiyonu"""
        print("\n" + "="*50)
        print("🚀 USGS Deprem Verisi Toplama Başladı")
        print("="*50)
        
        earthquakes = self.fetch_recent_earthquakes(days=days, min_magnitude=min_magnitude)
        
        if earthquakes:
            self.save_to_database(earthquakes)
        else:
            print("⚠️  Kaydedilecek veri yok")
        
        print("="*50 + "\n")


if __name__ == "__main__":
    collector = USGSCollector()
    collector.collect(days=7, min_magnitude=2.5)