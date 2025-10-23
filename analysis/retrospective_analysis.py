# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from database.models import Earthquake, SessionLocal
from sqlalchemy import and_

class RetrospectiveAnalysis:
    """Geçmiş büyük depremler öncesi anomali analizi - FAY HATTI VERSİYONU"""
    
    def __init__(self):
        self.db = SessionLocal()
        
        # Türkiye'deki kritik büyük depremler + Fay hatları
        self.major_earthquakes_turkey = [
            {
                'name': 'Kahramanmaraş',
                'date': datetime(2023, 2, 6, 4, 17),
                'magnitude': 7.7,
                'lat': 37.226,
                'lon': 37.014,
                'fault_name': 'Doğu Anadolu Fay Zonu',
                'fault_direction': 'NE-SW',  # KB-GD
                'fault_length_km': 200,
                'fault_width_km': 50
            },
            {
                'name': 'İzmir Seferihisar',
                'date': datetime(2020, 10, 30, 14, 51),
                'magnitude': 6.6,
                'lat': 37.919,
                'lon': 26.792,
                'fault_name': 'Ege Graben Sistemi',
                'fault_direction': 'E-W',  # D-B
                'fault_length_km': 150,
                'fault_width_km': 50
            },
            {
                'name': 'Elazığ',
                'date': datetime(2020, 1, 24, 20, 55),
                'magnitude': 6.8,
                'lat': 38.396,
                'lon': 39.063,
                'fault_name': 'Doğu Anadolu Fay Zonu',
                'fault_direction': 'NE-SW',
                'fault_length_km': 150,
                'fault_width_km': 50
            }
        ]
    
    def calculate_fault_zone_bounds(self, event):
        """Fay hattı boyunca tarama alanını hesapla"""
        
        lat = event['lat']
        lon = event['lon']
        length_km = event['fault_length_km']
        width_km = event['fault_width_km']
        direction = event['fault_direction']
        
        # 1 derece = ~111km (enlem), ~111*cos(lat) km (boylam)
        lat_per_km = 1 / 111
        lon_per_km = 1 / (111 * np.cos(np.radians(lat)))
        
        if direction == 'NE-SW':
            # KB-GD yönlü fay (45 derece)
            length_lat = length_km * lat_per_km * 0.707  # cos(45)
            length_lon = length_km * lon_per_km * 0.707
            width_lat = width_km * lat_per_km * 0.707
            width_lon = width_km * lon_per_km * 0.707
            
        elif direction == 'E-W':
            # D-B yönlü fay
            length_lat = 0
            length_lon = length_km * lon_per_km
            width_lat = width_km * lat_per_km
            width_lon = 0
            
        elif direction == 'N-S':
            # K-G yönlü fay
            length_lat = length_km * lat_per_km
            length_lon = 0
            width_lat = 0
            width_lon = width_km * lon_per_km
        else:
            # Varsayılan: Dairesel alan
            length_lat = length_km * lat_per_km
            length_lon = length_km * lon_per_km
            width_lat = width_km * lat_per_km
            width_lon = width_km * lon_per_km
        
        # Toplam alan
        total_lat = length_lat + width_lat
        total_lon = length_lon + width_lon
        
        return {
            'lat_min': lat - total_lat,
            'lat_max': lat + total_lat,
            'lon_min': lon - total_lon,
            'lon_max': lon + total_lon,
            'center_lat': lat,
            'center_lon': lon
        }
    
    def fetch_fault_zone_data(self, event, days_before=90):
        """Fay hattı boyunca geniş alandan veri çek"""
        print(f"\n{'='*60}")
        print(f"📊 {event['name']} Depremi Analizi")
        print(f"   Tarih: {event['date'].strftime('%d.%m.%Y %H:%M')}")
        print(f"   Büyüklük: {event['magnitude']}")
        print(f"   Fay Hattı: {event['fault_name']}")
        print(f"{'='*60}\n")
        
        end_date = event['date'] - timedelta(days=1)
        start_date = end_date - timedelta(days=days_before)
        
        # Fay hattı boyunca tarama alanı
        bounds = self.calculate_fault_zone_bounds(event)
        
        try:
            print(f"💾 Fay hattı boyunca tarama yapılıyor...")
            print(f"   📅 Tarih: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
            print(f"   📍 Fay: {event['fault_direction']} yönlü, {event['fault_length_km']}km × {event['fault_width_km']}km")
            print(f"   📍 Alan: {bounds['lat_min']:.2f}°-{bounds['lat_max']:.2f}°N, {bounds['lon_min']:.2f}°-{bounds['lon_max']:.2f}°E")
            
            earthquakes = self.db.query(Earthquake).filter(
                and_(
                    Earthquake.timestamp >= start_date,
                    Earthquake.timestamp <= end_date,
                    Earthquake.latitude.between(bounds['lat_min'], bounds['lat_max']),
                    Earthquake.longitude.between(bounds['lon_min'], bounds['lon_max']),
                    Earthquake.magnitude >= 2.0
                )
            ).all()
            
            print(f"✅ {len(earthquakes)} deprem verisi bulundu\n")
            
            return earthquakes, bounds
            
        except Exception as e:
            print(f"❌ Veri çekme hatası: {e}")
            return [], bounds
    
    def analyze_foreshock_activity(self, earthquakes, event, bounds):
        """Öncü deprem aktivitesini analiz et"""
        
        if not earthquakes or len(earthquakes) < 10:
            print(f"⚠️ Yeterli veri yok - sadece {len(earthquakes)} deprem bulundu")
            print(f"   Minimum 10 deprem gerekli\n")
            return {
                'total_earthquakes': len(earthquakes),
                'increase_ratio': None,
                'would_detect': False,
                'event_name': event['name'],
                'insufficient_data': True
            }
        
        # DataFrame'e çevir
        data = [{
            'time': eq.timestamp,
            'magnitude': eq.magnitude,
            'depth': eq.depth,
            'lat': eq.latitude,
            'lon': eq.longitude,
            'location': eq.location,
            'distance_km': self.calculate_distance(
                eq.latitude, eq.longitude,
                event['lat'], event['lon']
            )
        } for eq in earthquakes]
        
        df = pd.DataFrame(data)
        df = df.sort_values('time')
        
        print(f"📈 GENEL İSTATİSTİKLER:")
        print(f"   Toplam deprem sayısı: {len(df)}")
        print(f"   Ortalama büyüklük: {df['magnitude'].mean():.2f}")
        print(f"   En büyük: {df['magnitude'].max():.2f}")
        print(f"   Ortalama derinlik: {df['depth'].mean():.1f} km")
        print(f"   Ortalama uzaklık: {df['distance_km'].mean():.1f} km")
        
        # Mesafeye göre dağılım
        close = len(df[df['distance_km'] < 50])
        medium = len(df[(df['distance_km'] >= 50) & (df['distance_km'] < 100)])
        far = len(df[df['distance_km'] >= 100])
        
        print(f"\n📍 MESAFE DAĞILIMI:")
        print(f"   0-50 km: {close} deprem")
        print(f"   50-100 km: {medium} deprem")
        print(f"   100+ km: {far} deprem")
        
        # Zaman serisi analizi - haftalık aktivite
        df['week'] = df['time'].apply(lambda x: (event['date'] - x).days // 7)
        weekly_counts = df.groupby('week').size()
        
        print(f"\n📊 HAFTALIK AKTİVİTE (Fay hattı boyunca):")
        max_week = min(12, weekly_counts.index.max())
        for week in range(max_week + 1):
            count = weekly_counts.get(week, 0)
            bar = '█' * min(count // 3, 60)
            print(f"   {week:2d} hafta önce: {count:4d} deprem {bar}")
        
        # Anomali tespiti - son 2 hafta vs önceki dönem
        last_2_weeks = df[df['week'] <= 2]
        earlier = df[df['week'] > 2]
        
        increase_ratio = None
        
        if len(earlier) > 0 and len(last_2_weeks) > 0:
            baseline_rate = len(earlier) / (len(earlier['week'].unique()) * 7)
            recent_rate = len(last_2_weeks) / 14
            
            increase_ratio = recent_rate / baseline_rate if baseline_rate > 0 else 0
            
            print(f"\n🔍 ANOMALİ ANALİZİ:")
            print(f"   Baseline (8-13 hafta öncesi): {baseline_rate:.2f} deprem/gün")
            print(f"   Son 2 hafta: {recent_rate:.2f} deprem/gün")
            print(f"   Artış oranı: {increase_ratio:.2f}x")
            
            if increase_ratio >= 2.5:
                print(f"   ✅ SİSTEMİMİZ BUNU TESPİT EDERDİ! (≥2.5x artış)")
                print(f"   🎯 {len(last_2_weeks)} deprem ile anomali yakalanırdı")
            elif increase_ratio >= 2.0:
                print(f"   ⚡ YAKALAMA SINIRINDA (2.0-2.5x artış)")
                print(f"   💡 Eşik düşürülürse yakalanabilir")
            elif increase_ratio >= 1.5:
                print(f"   ⚠️ Orta seviye artış (1.5-2.0x artış)")
                print(f"   📊 İstatistiksel olarak anlamlı ama eşiğin altında")
            else:
                print(f"   ✅ Normal aktivite seviyesi (<1.5x)")
        else:
            print(f"\n⚠️ Yetersiz veri - baseline hesaplanamıyor")
        
        # Büyüklük ve mekan analizi
        if len(last_2_weeks) >= 5:
            print(f"\n📈 SON 2 HAFTA DETAYLI ANALİZ:")
            
            # En büyük depremler
            top_recent = last_2_weeks.nlargest(5, 'magnitude')
            print(f"   En büyük 5 deprem:")
            for idx, row in top_recent.iterrows():
                print(f"     M{row['magnitude']:.1f} - {row['distance_km']:.0f}km uzakta - {row['location'][:40]}")
            
            # Clustering kontrolü
            close_recent = last_2_weeks[last_2_weeks['distance_km'] < 50]
            if len(close_recent) >= 3:
                print(f"\n   ⚠️ 50km içinde {len(close_recent)} deprem - Merkeze yakın aktivite!")
        
        return {
            'total_earthquakes': len(df),
            'close_earthquakes': close,
            'weekly_counts': weekly_counts.to_dict(),
            'increase_ratio': increase_ratio,
            'would_detect': increase_ratio is not None and increase_ratio >= 2.5,
            'event_name': event['name'],
            'insufficient_data': False
        }
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """İki nokta arası mesafe (km) - Haversine formula"""
        R = 6371  # Dünya yarıçapı (km)
        
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c
    
    def analyze_all_events(self):
        """Tüm büyük depremleri analiz et"""
        print("\n" + "🔥"*30)
        print("🧪 RETROSPEKTİF ANALİZ - FAY HATTI VERSİYONU")
        print("   (Genişletilmiş fay hattı taraması)")
        print("🔥"*30 + "\n")
        
        results = []
        
        for event in self.major_earthquakes_turkey:
            earthquakes, bounds = self.fetch_fault_zone_data(event, days_before=90)
            
            result = self.analyze_foreshock_activity(earthquakes, event, bounds)
            results.append(result)
            
            print("\n" + "-"*60 + "\n")
        
        # Özet rapor
        print("\n" + "📋"*30)
        print("📊 GENEL ÖZET RAPORU")
        print("📋"*30 + "\n")
        
        detected_count = sum(1 for r in results if r.get('would_detect', False))
        insufficient_count = sum(1 for r in results if r.get('insufficient_data', False))
        analyzable = len(results) - insufficient_count
        total = len(results)
        
        print(f"✅ Analiz edilen büyük deprem: {total}")
        print(f"📊 Analiz yapılabilir veri: {analyzable}/{total}")
        
        if analyzable > 0:
            print(f"✅ Sistemimiz tespit ederdi: {detected_count}/{analyzable} (%{detected_count/analyzable*100:.0f})")
            print(f"❌ Kaçırırdı: {analyzable - detected_count}/{analyzable}")
        
        print(f"\n📊 DETAYLI SONUÇLAR:\n")
        
        for result in results:
            event_name = result['event_name']
            
            if result.get('insufficient_data'):
                print(f"❌ {event_name:20s} - YETERSİZ VERİ")
            elif result.get('would_detect'):
                ratio = result.get('increase_ratio', 0)
                total_eq = result.get('total_earthquakes', 0)
                close_eq = result.get('close_earthquakes', 0)
                print(f"✅ {event_name:20s} - TESPİT EDERDİ! (Artış: {ratio:.2f}x, {total_eq} deprem, {close_eq} yakın)")
            else:
                ratio = result.get('increase_ratio')
                total_eq = result.get('total_earthquakes', 0)
                if ratio is not None:
                    print(f"⚠️ {event_name:20s} - KAÇIRIRDI (Artış: {ratio:.2f}x, {total_eq} deprem)")
                else:
                    print(f"❌ {event_name:20s} - ANALİZ EDİLEMEDİ")
        
        print("\n" + "📋"*30 + "\n")
        
        return results
    
    def optimize_thresholds(self, results):
        """Sonuçlara göre öneriler"""
        print("\n🎯 SİSTEM PERFORMANSI VE ÖNERİLER:")
        print("="*60)
        
        valid_results = [r for r in results if not r.get('insufficient_data') and r.get('increase_ratio') is not None]
        
        if valid_results:
            ratios = [r.get('increase_ratio', 0) for r in valid_results]
            
            print(f"\n📊 Artış Oranları:")
            for r in valid_results:
                name = r['event_name']
                ratio = r.get('increase_ratio', 0)
                status = "✅ YAKALANDI" if r.get('would_detect') else "❌ KAÇIRILDI"
                print(f"   {name:20s}: {ratio:.2f}x - {status}")
            
            avg = np.mean(ratios)
            print(f"\n   Ortalama: {avg:.2f}x")
            
            print(f"\n💡 SONUÇ:")
            detected = len([r for r in valid_results if r.get('would_detect')])
            total = len(valid_results)
            
            if detected == total:
                print(f"   ✅ Mükemmel! Tüm büyük depremler yakalandı!")
            elif detected > 0:
                print(f"   ⚡ {detected}/{total} deprem yakalandı")
                print(f"   💡 Eşik ayarları ile iyileştirilebilir")
            else:
                print(f"   ⚠️ Hiçbir deprem yakalanamadı")
                print(f"   💡 Büyük depremler öncesi aktivite az olabilir")
        
        print("\n" + "="*60 + "\n")
    
    def __del__(self):
        self.db.close()


if __name__ == "__main__":
    analyzer = RetrospectiveAnalysis()
    results = analyzer.analyze_all_events()
    analyzer.optimize_thresholds(results)