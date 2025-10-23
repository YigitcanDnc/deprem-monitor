# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import Earthquake, SessionLocal
from datetime import datetime, timedelta
from sqlalchemy import func

class DatabaseAnalyzer:
    """Veritabanındaki mevcut verileri analiz et"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def check_data_coverage(self):
        """Veritabanında hangi tarih aralığında veri var?"""
        print("\n" + "="*60)
        print("📊 VERİTABANI VERİ KAPSAMI ANALİZİ")
        print("="*60 + "\n")
        
        # Toplam deprem sayısı
        total = self.db.query(Earthquake).count()
        print(f"📈 Toplam Deprem Sayısı: {total:,}")
        
        if total == 0:
            print("\n⚠️ Veritabanında hiç veri yok!")
            return
        
        # Kaynak bazında dağılım
        print(f"\n📊 Kaynak Bazında Dağılım:")
        sources = self.db.query(
            Earthquake.source,
            func.count(Earthquake.id).label('count')
        ).group_by(Earthquake.source).all()
        
        for source, count in sources:
            percentage = (count / total) * 100
            print(f"   {source:20s}: {count:8,} deprem ({percentage:5.1f}%)")
        
        # Tarih aralığı
        oldest = self.db.query(func.min(Earthquake.timestamp)).scalar()
        newest = self.db.query(func.max(Earthquake.timestamp)).scalar()
        
        if oldest and newest:
            print(f"\n📅 Tarih Aralığı:")
            print(f"   En eski: {oldest.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   En yeni: {newest.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Kapsam: {(newest - oldest).days:,} gün ({(newest - oldest).days / 365:.1f} yıl)")
        
        # Büyük depremler (M≥5.0)
        print(f"\n🔴 Büyük Depremler (M ≥ 5.0):")
        major = self.db.query(Earthquake).filter(
            Earthquake.magnitude >= 5.0
        ).order_by(Earthquake.magnitude.desc()).limit(15).all()
        
        if major:
            for eq in major:
                print(f"   {eq.timestamp.strftime('%Y-%m-%d')} | M{eq.magnitude:.1f} | {eq.location[:50]}")
        else:
            print("   Bulunamadı")
        
        # Yıllık dağılım
        print(f"\n📊 Yıllık Dağılım:")
        for year in range(oldest.year, newest.year + 1):
            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31, 23, 59, 59)
            
            count = self.db.query(Earthquake).filter(
                Earthquake.timestamp >= year_start,
                Earthquake.timestamp <= year_end
            ).count()
            
            if count > 0:
                bar = '█' * min(count // 200, 60)
                print(f"   {year}: {count:6,} deprem {bar}")
        
        print("\n" + "="*60 + "\n")
    
    def check_major_earthquakes(self):
        """Büyük depremlerin veritabanında olup olmadığını kontrol et"""
        print("🔍 BÜYÜK DEPREMLERİN VERİTABANINDA KONTROL EDİLMESİ")
        print("="*60 + "\n")
        
        major_events = [
            {
                'name': 'Kahramanmaraş (7.7)',
                'date': datetime(2023, 2, 6),
                'lat': 37.226,
                'lon': 37.014,
            },
            {
                'name': 'İzmir Seferihisar (6.6)',
                'date': datetime(2020, 10, 30),
                'lat': 37.919,
                'lon': 26.792,
            },
            {
                'name': 'Elazığ (6.8)',
                'date': datetime(2020, 1, 24),
                'lat': 38.396,
                'lon': 39.063,
            }
        ]
        
        for event in major_events:
            # 90 gün öncesi verileri kontrol et
            start_date = event['date'] - timedelta(days=90)
            end_date = event['date'] - timedelta(days=1)
            
            # Yakın bölgedeki depremleri say (±0.5 derece ~ 50km)
            nearby = self.db.query(Earthquake).filter(
                Earthquake.timestamp >= start_date,
                Earthquake.timestamp <= end_date,
                Earthquake.latitude.between(event['lat'] - 0.5, event['lat'] + 0.5),
                Earthquake.longitude.between(event['lon'] - 0.5, event['lon'] + 0.5)
            ).count()
            
            print(f"📍 {event['name']}")
            print(f"   Depremden 90 gün öncesi (±50km):")
            print(f"   {nearby:,} deprem kaydı bulundu")
            
            if nearby > 100:
                print(f"   ✅ MÜKEMMEL VERİ - Detaylı analiz yapılabilir!")
            elif nearby > 50:
                print(f"   ✅ YETERLİ VERİ - Analiz yapılabilir")
            elif nearby > 20:
                print(f"   ⚠️ SINIRLI VERİ - Kısmi analiz yapılabilir")
            else:
                print(f"   ❌ YETERSİZ VERİ")
            
            print()
        
        print("="*60 + "\n")
    
    def suggest_next_steps(self):
        """Sonraki adımlar öner"""
        total = self.db.query(Earthquake).count()
        
        print("💡 SONRAKİ ADIMLAR:")
        print("="*60 + "\n")
        
        if total < 1000:
            print("⚠️ Veritabanında çok az veri var!")
            print("\nÖneriler:")
            print("1. Kandilli verilerini yükleyin")
            print("2. Veya scheduler.py'yi birkaç gün çalıştırın")
        
        elif total < 10000:
            print("⚡ Makul miktarda veri var!")
            print("\nÖneriler:")
            print("1. Retrospektif analizi çalıştırabilirsiniz:")
            print("   python analysis/retrospective_analysis.py")
            print("2. Ama daha fazla veri daha iyi sonuç verir")
        
        else:
            print("✅ Veritabanında yeterli veri var!")
            print("\nYapılabilecekler:")
            print("1. 🔥 Retrospektif analizi çalıştırın:")
            print("   python analysis/retrospective_analysis.py")
            print("\n2. 📊 Haritada görün:")
            print("   python api.py")
            print("\n3. ⏰ Otomatik sistemi başlatın:")
            print("   python scheduler.py")
        
        print("\n" + "="*60 + "\n")
    
    def __del__(self):
        self.db.close()


if __name__ == "__main__":
    analyzer = DatabaseAnalyzer()
    analyzer.check_data_coverage()
    analyzer.check_major_earthquakes()
    analyzer.suggest_next_steps()