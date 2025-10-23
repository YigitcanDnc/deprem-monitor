# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from datetime import datetime, timedelta
from database.models import Earthquake, SessionLocal
import time

class KandilliArchiveScraper:
    """Kandilli Rasathanesi geçmiş deprem verilerini çeker"""
    
    def __init__(self):
        self.base_url = "http://www.koeri.boun.edu.tr/scripts/lst0.asp"
    
    def fetch_archive_data(self, year, month):
        """
        Belirli bir ay için deprem verilerini çek
        Kandilli'nin arşiv sayfası format: lst{YY}{MM}.asp
        """
        # Yıl formatı: 2023 -> 23
        year_short = str(year)[-2:]
        month_str = f"{month:02d}"
        
        # Arşiv URL'si
        archive_url = f"http://www.koeri.boun.edu.tr/scripts/lst{year_short}{month_str}.asp"
        
        print(f"📅 {year}-{month:02d} verisi çekiliyor...")
        print(f"   URL: {archive_url}")
        
        try:
            response = requests.get(archive_url, timeout=30)
            response.encoding = 'ISO-8859-9'
            
            if response.status_code != 200:
                print(f"   ⚠️ Sayfa bulunamadı (HTTP {response.status_code})")
                return []
            
            lines = response.text.split('\n')
            earthquakes = []
            
            # Veri satırlarını bul
            for line in lines[6:]:  # İlk 6 satır başlık
                line = line.strip()
                if not line or line.startswith('-'):
                    continue
                
                parts = line.split()
                if len(parts) < 8:
                    continue
                
                try:
                    eq = {
                        'date': parts[0],
                        'time': parts[1],
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
                
                except (ValueError, IndexError):
                    continue
            
            print(f"   ✅ {len(earthquakes)} deprem bulundu")
            return earthquakes
            
        except requests.exceptions.Timeout:
            print(f"   ⏰ Zaman aşımı")
            return []
        except Exception as e:
            print(f"   ❌ Hata: {e}")
            return []
    
    def save_to_database(self, earthquakes, year, month):
        """Depremleri veritabanına kaydet"""
        if not earthquakes:
            return 0
        
        db = SessionLocal()
        saved_count = 0
        skipped_count = 0
        
        try:
            for eq in earthquakes:
                # Benzersiz ID oluştur
                event_id = f"kandilli_archive_{year}{month:02d}_{eq['date'].replace('.', '')}_{eq['time'].replace(':', '')}_{eq['latitude']:.2f}_{eq['longitude']:.2f}"
                
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
                
                # Yeni kayıt oluştur
                earthquake = Earthquake(
                    event_id=event_id,
                    timestamp=timestamp,
                    latitude=eq['latitude'],
                    longitude=eq['longitude'],
                    magnitude=eq['magnitude'],
                    depth=eq['depth'],
                    location=eq['location'],
                    source='Kandilli_Archive',
                    geometry=f"POINT({eq['longitude']} {eq['latitude']})"
                )
                
                db.add(earthquake)
                saved_count += 1
                
                # Her 100 kayıtta bir commit (performans için)
                if saved_count % 100 == 0:
                    db.commit()
            
            # Kalan kayıtları commit et
            db.commit()
            
            print(f"   💾 {saved_count} yeni, {skipped_count} mevcut kayıt")
            
        except Exception as e:
            db.rollback()
            print(f"   ❌ Veritabanı hatası: {e}")
        finally:
            db.close()
        
        return saved_count
    
    def fetch_date_range(self, start_year, start_month, end_year, end_month):
        """
        Belirli bir tarih aralığındaki tüm verileri çek
        """
        print("\n" + "="*60)
        print("📚 KANDİLLİ ARŞİV VERİ ÇEKME BAŞLADI")
        print("="*60)
        print(f"Tarih Aralığı: {start_year}-{start_month:02d} → {end_year}-{end_month:02d}\n")
        
        total_saved = 0
        total_months = 0
        failed_months = []
        
        current_year = start_year
        current_month = start_month
        
        while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
            earthquakes = self.fetch_archive_data(current_year, current_month)
            
            if earthquakes:
                saved = self.save_to_database(earthquakes, current_year, current_month)
                total_saved += saved
                total_months += 1
            else:
                failed_months.append(f"{current_year}-{current_month:02d}")
            
            # Sonraki aya geç
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1
            
            # Kandilli sunucusunu yormamak için kısa bekleme
            time.sleep(1)
        
        # Özet rapor
        print("\n" + "="*60)
        print("📊 ARŞİV VERİ ÇEKME TAMAMLANDI")
        print("="*60)
        print(f"✅ İşlenen ay sayısı: {total_months}")
        print(f"💾 Toplam kaydedilen deprem: {total_saved:,}")
        
        if failed_months:
            print(f"\n⚠️ Veri çekilemeyen aylar ({len(failed_months)}):")
            for month in failed_months[:10]:  # İlk 10'unu göster
                print(f"   - {month}")
            if len(failed_months) > 10:
                print(f"   ... ve {len(failed_months) - 10} ay daha")
        
        print("="*60 + "\n")
        
        return total_saved


if __name__ == "__main__":
    scraper = KandilliArchiveScraper()
    
    # 2019'dan bugüne kadar tüm verileri çek
    # NOT: Bu işlem 10-20 dakika sürebilir!
    
    current_date = datetime.now()
    
    print("🎯 Hedef: 2019 - Şu an arası TÜM Kandilli verileri")
    print("⏱️ Tahmini süre: 10-20 dakika")
    print("🔄 İşlem sırasında bekleyin...\n")
    
    input("ENTER'a basarak başlatın (veya CTRL+C ile iptal edin): ")
    
    total = scraper.fetch_date_range(
        start_year=2019,
        start_month=1,
        end_year=current_date.year,
        end_month=current_date.month
    )
    
    print(f"\n🎉 BAŞARILI! {total:,} deprem kaydı eklendi!")
    print("📊 Artık retrospektif analizi tekrar çalıştırabilirsiniz:")
    print("   python analysis/retrospective_analysis.py")