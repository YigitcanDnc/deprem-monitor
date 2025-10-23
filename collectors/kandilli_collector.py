# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from datetime import datetime
from database.models import Earthquake, SessionLocal

class KandilliCollector:
    """Kandilli Rasathanesi deprem verilerini toplar"""
    
    def __init__(self):
        self.base_url = "http://www.koeri.boun.edu.tr/scripts/lst0.asp"
    
    def fetch_recent_earthquakes(self):
        """Son depremleri çek"""
        try:
            print(f"🇹🇷 Kandilli Rasathanesi'nden veri çekiliyor...")
            
            response = requests.get(self.base_url, timeout=30)
            # Türkçe karakterler için doğru encoding
            response.encoding = 'ISO-8859-9'  # Türkçe için
            
            lines = response.text.split('\n')
            earthquakes = []
            
            # Veri satırlarını bul (başlık satırlarını atla)
            for line in lines[6:]:  # İlk 6 satır başlık
                line = line.strip()
                if not line or line.startswith('-'):
                    continue
                
                # Satırı boşluklara göre ayır
                parts = line.split()
                if len(parts) < 8:
                    continue
                
                try:
                    # Kandilli formatı:
                    # Tarih Saat Lat Lon Derinlik MD ML Mw Yer
                    eq = {
                        'date': parts[0],      # YYYY.MM.DD
                        'time': parts[1],      # HH:MM:SS
                        'latitude': float(parts[2]),
                        'longitude': float(parts[3]),
                        'depth': float(parts[4]),
                        'md': parts[5] if parts[5] != '-.-' else None,
                        'ml': parts[6] if parts[6] != '-.-' else None,
                        'mw': parts[7] if parts[7] != '-.-' else None,
                        'location': ' '.join(parts[8:])
                    }
                    
                    # En büyük magnitude'ü seç
                    mags = []
                    if eq['mw'] and eq['mw'] != '-.-':
                        mags.append(float(eq['mw']))
                    if eq['ml'] and eq['ml'] != '-.-':
                        mags.append(float(eq['ml']))
                    if eq['md'] and eq['md'] != '-.-':
                        mags.append(float(eq['md']))
                    
                    if mags:
                        eq['magnitude'] = max(mags)
                        earthquakes.append(eq)
                    
                except (ValueError, IndexError) as e:
                    continue
            
            print(f"✅ {len(earthquakes)} deprem verisi alındı")
            return earthquakes
            
        except Exception as e:
            print(f"❌ Kandilli hatası: {e}")
            return []
    
    def save_to_database(self, earthquakes):
        """Depremleri veritabanına kaydet"""
        db = SessionLocal()
        saved_count = 0
        skipped_count = 0
        
        try:
            for eq in earthquakes:
                # Benzersiz ID oluştur
                event_id = f"kandilli_{eq['date'].replace('.', '')}_{eq['time'].replace(':', '')}_{eq['latitude']:.2f}_{eq['longitude']:.2f}"
                
                # Zaten var mı kontrol et
                existing = db.query(Earthquake).filter_by(event_id=event_id).first()
                if existing:
                    skipped_count += 1
                    continue
                
                # Tarih parse et
                try:
                    timestamp = datetime.strptime(f"{eq['date']} {eq['time']}", "%Y.%m.%d %H:%M:%S")
                except:
                    skipped_count += 1
                    continue
                
                earthquake = Earthquake(
                    event_id=event_id,
                    timestamp=timestamp,
                    latitude=eq['latitude'],
                    longitude=eq['longitude'],
                    magnitude=eq['magnitude'],
                    depth=eq['depth'],
                    location=eq['location'],  # Artık düzgün Türkçe
                    source='Kandilli',
                    geometry=f"POINT({eq['longitude']} {eq['latitude']})"
                )
                
                db.add(earthquake)
                saved_count += 1
            
            db.commit()
            print(f"💾 Veritabanına kaydedildi:")
            print(f"   ✅ {saved_count} yeni deprem")
            print(f"   ⏭️  {skipped_count} zaten mevcut")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Veritabanı hatası: {e}")
        finally:
            db.close()
    
    def collect(self):
        """Ana toplama fonksiyonu"""
        print("\n" + "="*50)
        print("🚀 Kandilli Deprem Verisi Toplama Başladı")
        print("="*50)
        
        earthquakes = self.fetch_recent_earthquakes()
        
        if earthquakes:
            self.save_to_database(earthquakes)
        else:
            print("⚠️  Kaydedilecek veri yok")
        
        print("="*50 + "\n")


if __name__ == "__main__":
    collector = KandilliCollector()
    collector.collect()