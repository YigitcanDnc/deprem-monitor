import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from datetime import datetime, timedelta
from database.models import Earthquake, SessionLocal

class AFADCollector:
    """AFAD (Türkiye) deprem verilerini toplar"""
    
    def __init__(self):
        # AFAD'ın API endpoint'i
        self.base_url = "https://deprem.afad.gov.tr/apiv2/event/filter"
    
    def fetch_recent_earthquakes(self):
        """Son 7 günün depremlerini çek"""
        try:
            print(f"🇹🇷 AFAD'dan veri çekiliyor...")
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            }
            
            print(f"📅 Tarih aralığı: {payload['start']} - {payload['end']}")
            
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=30)
            
            # Debug bilgileri
            print(f"📡 Status Code: {response.status_code}")
            print(f"📡 Content-Type: {response.headers.get('Content-Type')}")
            
            if response.status_code != 200:
                print(f"❌ AFAD hata kodu: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return []
            
            data = response.json()
            
            # AFAD'ın response formatına göre veriyi al
            if isinstance(data, list):
                earthquakes = data
            elif isinstance(data, dict):
                earthquakes = data.get('data', data.get('result', []))
            else:
                earthquakes = []
            
            print(f"✅ {len(earthquakes)} deprem verisi alındı")
            return earthquakes
            
        except requests.exceptions.Timeout:
            print("❌ AFAD zaman aşımı")
            return []
        except requests.exceptions.RequestException as e:
            print(f"❌ AFAD bağlantı hatası: {e}")
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
                # AFAD'ın farklı formatlarını destekle
                event_id = f"afad_{eq.get('eventID', eq.get('geoid', eq.get('id', '')))}"
                
                if not event_id or event_id == "afad_":
                    skipped_count += 1
                    continue
                
                # Zaten var mı kontrol et
                existing = db.query(Earthquake).filter_by(event_id=event_id).first()
                if existing:
                    skipped_count += 1
                    continue
                
                # Tarih parse et
                date_field = eq.get('eventDate', eq.get('date', eq.get('dateTime', '')))
                try:
                    if 'T' in date_field:
                        timestamp = datetime.fromisoformat(date_field.replace('Z', '+00:00'))
                    else:
                        timestamp = datetime.strptime(date_field, '%Y-%m-%d %H:%M:%S')
                except:
                    skipped_count += 1
                    continue
                
                # Koordinatlar ve büyüklük
                lat = float(eq.get('latitude', eq.get('lat', eq.get('geojson', {}).get('coordinates', [0, 0])[1])))
                lon = float(eq.get('longitude', eq.get('lon', eq.get('geojson', {}).get('coordinates', [0, 0])[0])))
                mag = float(eq.get('magnitude', eq.get('mag', eq.get('ml', 0))))
                depth = float(eq.get('depth', 0))
                
                if mag == 0 or lat == 0 or lon == 0:
                    skipped_count += 1
                    continue
                
                location = eq.get('location', eq.get('title', eq.get('locationTr', 'Türkiye')))
                
                earthquake = Earthquake(
                    event_id=event_id,
                    timestamp=timestamp,
                    latitude=lat,
                    longitude=lon,
                    magnitude=mag,
                    depth=depth,
                    location=location,
                    source='AFAD',
                    geometry=f'POINT({lon} {lat})'
                )
                
                db.add(earthquake)
                saved_count += 1
            
            db.commit()
            print(f"💾 Veritabanına kaydedildi:")
            print(f"   ✅ {saved_count} yeni deprem")
            print(f"   ⏭️  {skipped_count} zaten mevcut veya geçersiz")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Veritabanı hatası: {e}")
        finally:
            db.close()
    
    def collect(self):
        """Ana toplama fonksiyonu"""
        print("\n" + "="*50)
        print("🚀 AFAD Deprem Verisi Toplama Başladı")
        print("="*50)
        
        earthquakes = self.fetch_recent_earthquakes()
        
        if earthquakes:
            self.save_to_database(earthquakes)
        else:
            print("⚠️  Kaydedilecek veri yok")
        
        print("="*50 + "\n")


if __name__ == "__main__":
    collector = AFADCollector()
    collector.collect()