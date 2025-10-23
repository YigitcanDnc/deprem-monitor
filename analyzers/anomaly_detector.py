# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import and_, func
from database.models import Earthquake, Anomaly, SessionLocal
from sklearn.preprocessing import StandardScaler

class AnomalyDetector:
    """Deprem anomalilerini tespit eder"""
    
    def __init__(self):
        self.db = SessionLocal()
        self.grid_size = 50  # km - her bir grid hücresinin boyutu
        self.time_window = 48  # saat - anomali tespit penceresi
        self.baseline_days = 90  # gün - normal davranışı öğrenmek için
    
    def __del__(self):
        self.db.close()
    
    def get_recent_earthquakes(self, hours=48):
        """Son X saatteki depremleri al"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        earthquakes = self.db.query(Earthquake).filter(
            Earthquake.timestamp >= cutoff
        ).all()
        
        return earthquakes
    
    def get_baseline_earthquakes(self, days=90):
        """Baseline (normal davranış) için eski depremleri al"""
        end_date = datetime.utcnow() - timedelta(hours=self.time_window)
        start_date = end_date - timedelta(days=days)
        
        earthquakes = self.db.query(Earthquake).filter(
            and_(
                Earthquake.timestamp >= start_date,
                Earthquake.timestamp <= end_date
            )
        ).all()
        
        return earthquakes
    
    def create_grid(self, earthquakes):
        """Depremleri grid hücrelerine böl"""
        if not earthquakes:
            return {}
        
        # DataFrame'e çevir
        data = [{
            'lat': eq.latitude,
            'lon': eq.longitude,
            'mag': eq.magnitude,
            'depth': eq.depth,
            'timestamp': eq.timestamp,
            'location': eq.location
        } for eq in earthquakes]
        
        df = pd.DataFrame(data)
        
        # Grid hücresi atama (yaklaşık 50km x 50km)
        df['grid_lat'] = (df['lat'] / 0.45).round() * 0.45  # ~50km enlem
        df['grid_lon'] = (df['lon'] / 0.45).round() * 0.45  # ~50km boylam
        df['grid_id'] = df['grid_lat'].astype(str) + '_' + df['grid_lon'].astype(str)
        
        # Grid'lere göre grupla
        grids = {}
        for grid_id, group in df.groupby('grid_id'):
            grids[grid_id] = {
                'center_lat': group['grid_lat'].iloc[0],
                'center_lon': group['grid_lon'].iloc[0],
                'count': len(group),
                'earthquakes': group.to_dict('records'),
                'avg_magnitude': group['mag'].mean(),
                'max_magnitude': group['mag'].max(),
                'location': group['location'].iloc[0]
            }
        
        return grids
    
    def clean_location(self, location):
        """Konum adını temizle - sadece ana bölge adını al"""
        if not location:
            return "Bilinmiyor"
        
        # "Yüksel" kelimesini kaldır
        location = location.replace(' Yüksel', '').replace(' Yuksel', '').replace(' Yiksel', '').replace(' Ýlksel', '')
        
        # Parantez içindeki kısmı al (şehir adı)
        if '(' in location:
            # "KAVAKCALI-ULA (MUGLA) Yüksel" -> "KAVAKCALI-ULA (MUGLA)"
            location = location.split(')')[0] + ')'
        
        return location.strip()
    
    def detect_frequency_anomaly(self):
        """Frekans anomalisi tespit et (Yöntem 1)"""
        print("\n🔍 Frekans Anomalisi Analizi...")
        
        # Son 48 saat ve baseline verilerini al
        recent = self.get_recent_earthquakes(hours=self.time_window)
        baseline = self.get_baseline_earthquakes(days=self.baseline_days)
        
        if len(baseline) < 10:
            print("⚠️  Yeterli baseline verisi yok (min 10 deprem gerekli)")
            return []
        
        print(f"   📊 Son {self.time_window} saat: {len(recent)} deprem")
        print(f"   📊 Baseline ({self.baseline_days} gün): {len(baseline)} deprem")
        
        # Grid'lere böl
        recent_grids = self.create_grid(recent)
        baseline_grids = self.create_grid(baseline)
        
        anomalies = []
        
        for grid_id, recent_data in recent_grids.items():
            recent_count = recent_data['count']
            
            # Baseline'daki aynı grid
            baseline_data = baseline_grids.get(grid_id, {'count': 0})
            baseline_count = baseline_data['count']
            
            # Baseline'dan günlük ortalama hesapla
            baseline_avg_per_window = (baseline_count / self.baseline_days) * (self.time_window / 24)
            
            if baseline_avg_per_window == 0:
                baseline_avg_per_window = 0.5  # Sıfır bölme hatası
            
            # Z-score hesapla
            if baseline_avg_per_window > 0:
                z_score = (recent_count - baseline_avg_per_window) / np.sqrt(baseline_avg_per_window)
            else:
                z_score = 0
            
            # Anomali tespit et (z-score > 2.5)
            if z_score > 2.5 and recent_count >= 5:
                alert_level = 'yellow' if z_score < 3.5 else 'orange' if z_score < 5 else 'red'
                
                # Konum adını temizle
                clean_location = self.clean_location(recent_data['location'])
                
                anomalies.append({
                    'type': 'frequency',
                    'grid_id': grid_id,
                    'location': clean_location,
                    'center_lat': recent_data['center_lat'],
                    'center_lon': recent_data['center_lon'],
                    'recent_count': recent_count,
                    'baseline_avg': baseline_avg_per_window,
                    'z_score': z_score,
                    'alert_level': alert_level,
                    'max_magnitude': recent_data['max_magnitude']
                })
                
                print(f"\n   🚨 Anomali tespit edildi!")
                print(f"      📍 Konum: {clean_location}")
                print(f"      📊 Son {self.time_window}h: {recent_count} deprem")
                print(f"      📊 Normal: ~{baseline_avg_per_window:.1f} deprem")
                print(f"      📈 Z-score: {z_score:.2f}")
                print(f"      🔴 Seviye: {alert_level.upper()}")
        
        return anomalies
    
    def detect_magnitude_escalation(self):
        """Magnitüd kademeli artış tespit et (Yöntem 2)"""
        print("\n🔍 Magnitüd Kademeli Artış Analizi...")
        
        recent = self.get_recent_earthquakes(hours=self.time_window)
        
        if len(recent) < 5:
            print("   ⚠️  Yeterli veri yok (min 5 deprem)")
            return []
        
        # Grid'lere böl
        grids = self.create_grid(recent)
        
        anomalies = []
        
        for grid_id, data in grids.items():
            if data['count'] < 5:
                continue
            
            # Depremleri zamana göre sırala
            eqs = sorted(data['earthquakes'], key=lambda x: x['timestamp'])
            magnitudes = [eq['mag'] for eq in eqs]
            
            # Son 5 depremde kademeli artış var mı?
            last_5 = magnitudes[-5:]
            
            # Trend kontrolü
            increasing = sum([last_5[i] > last_5[i-1] for i in range(1, 5)])
            
            # Veya son deprem, önceki ortalamanın üstünde mi?
            avg_before_last = np.mean(magnitudes[:-1])
            last_mag = magnitudes[-1]
            
            if increasing >= 3 or (last_mag > avg_before_last + 0.5):
                alert_level = 'orange' if last_mag < 4.0 else 'red'
                
                # Konum adını temizle
                clean_location = self.clean_location(data['location'])
                
                anomalies.append({
                    'type': 'magnitude_escalation',
                    'grid_id': grid_id,
                    'location': clean_location,
                    'center_lat': data['center_lat'],
                    'center_lon': data['center_lon'],
                    'count': data['count'],
                    'last_magnitude': last_mag,
                    'avg_magnitude': avg_before_last,
                    'trend': 'increasing',
                    'alert_level': alert_level,
                    'max_magnitude': last_mag
                })
                
                print(f"\n   🚨 Magnitüd artışı tespit edildi!")
                print(f"      📍 Konum: {clean_location}")
                print(f"      📊 Deprem sayısı: {data['count']}")
                print(f"      📈 Son mag: {last_mag:.1f}")
                print(f"      📉 Önceki ort: {avg_before_last:.1f}")
                print(f"      🔴 Seviye: {alert_level.upper()}")
        
        return anomalies
    
    def save_anomalies(self, anomalies):
        """Anomalileri veritabanına kaydet"""
        if not anomalies:
            return
        
        saved_count = 0
        
        for anomaly in anomalies:
            # Aynı bölgede aktif anomali var mı kontrol et
            existing = self.db.query(Anomaly).filter(
                and_(
                    Anomaly.region == anomaly['location'],
                    Anomaly.is_resolved == False,
                    Anomaly.anomaly_type == anomaly['type']
                )
            ).first()
            
            if existing:
                # Mevcut anomaliyi güncelle
                existing.score = anomaly.get('z_score', anomaly.get('last_magnitude', 0))
                existing.alert_level = anomaly['alert_level']
                existing.end_time = datetime.utcnow()
            else:
                # Yeni anomali kaydet
                description = f"{anomaly['type']} anomalisi: {anomaly.get('recent_count', anomaly.get('count', 0))} deprem"
                
                new_anomaly = Anomaly(
                    region=anomaly['location'],
                    start_time=datetime.utcnow() - timedelta(hours=self.time_window),
                    anomaly_type=anomaly['type'],
                    score=anomaly.get('z_score', anomaly.get('last_magnitude', 0)),
                    alert_level=anomaly['alert_level'],
                    description=description
                )
                
                self.db.add(new_anomaly)
                saved_count += 1
        
        self.db.commit()
        print(f"\n💾 {saved_count} yeni anomali kaydedildi")
    
    def analyze(self):
        """Tüm analizleri çalıştır"""
        print("\n" + "="*60)
        print("🧠 ANOMALİ TESPİT ANALİZİ BAŞLADI")
        print("="*60)
        
        all_anomalies = []
        
        # 1. Frekans anomalisi
        freq_anomalies = self.detect_frequency_anomaly()
        all_anomalies.extend(freq_anomalies)
        
        # 2. Magnitüd artışı
        mag_anomalies = self.detect_magnitude_escalation()
        all_anomalies.extend(mag_anomalies)
        
        # Anomalileri kaydet
        if all_anomalies:
            self.save_anomalies(all_anomalies)
            print(f"\n🎯 Toplam {len(all_anomalies)} anomali tespit edildi!")
        else:
            print("\n✅ Anomali tespit edilmedi - her şey normal görünüyor")
        
        print("="*60 + "\n")
        
        return all_anomalies


if __name__ == "__main__":
    detector = AnomalyDetector()
    detector.analyze()