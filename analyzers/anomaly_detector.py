# -*- coding: utf-8 -*-
"""
Anomali Tespit Modülü
- Frekans bazlı anomali tespiti (Z-score)
- Magnitüd artış tespiti
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta, timezone
from database.models import Earthquake, Anomaly, SessionLocal
import numpy as np
import pandas as pd
from sqlalchemy import and_

class AnomalyDetector:
    def __init__(self):
        self.db = SessionLocal()
        self.grid_size = 0.45  # ~50km grid
    
    def analyze(self):
        """Tüm anomali analizlerini çalıştır"""
        print("\n" + "="*60)
        print("🧠 ANOMALİ TESPİT ANALİZİ BAŞLADI")
        print("="*60 + "\n")
        
        all_anomalies = []
        
        # 1. Frekans anomalisi
        freq_anomalies = self.detect_frequency_anomaly()
        all_anomalies.extend(freq_anomalies)
        
        # 2. Magnitüd artış anomalisi
        mag_anomalies = self.detect_magnitude_escalation()
        all_anomalies.extend(mag_anomalies)
        
        # Anomalileri kaydet
        if all_anomalies:
            self.save_anomalies(all_anomalies)
        
        print(f"\n🎯 Toplam {len(all_anomalies)} anomali tespit edildi!")
        print("="*60 + "\n")
        
        return all_anomalies
    
    def get_recent_earthquakes(self, hours=48):
        """Son X saatteki depremleri getir"""
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self.db.query(Earthquake).filter(
            Earthquake.timestamp >= time_threshold.replace(tzinfo=None)
        ).all()
    
    def get_baseline_earthquakes(self, days=90):
        """Baseline için geçmiş depremleri getir (son 48 saat hariç)"""
        end_time = datetime.now(timezone.utc) - timedelta(hours=48)
        start_time = end_time - timedelta(days=days)
        
        return self.db.query(Earthquake).filter(
            and_(
                Earthquake.timestamp >= start_time.replace(tzinfo=None),
                Earthquake.timestamp <= end_time.replace(tzinfo=None)
            )
        ).all()
    
    def create_grid(self, earthquakes):
        """Depremleri grid'lere böl"""
        if not earthquakes:
            return {}
        
        # DataFrame oluştur
        df = pd.DataFrame([{
            'lat': eq.latitude,
            'lon': eq.longitude,
            'mag': eq.magnitude,
            'location': eq.location
        } for eq in earthquakes])
        
        # Grid koordinatları
        df['grid_lat'] = (df['lat'] / self.grid_size).round() * self.grid_size
        df['grid_lon'] = (df['lon'] / self.grid_size).round() * self.grid_size
        df['grid_id'] = df['grid_lat'].astype(str) + '_' + df['grid_lon'].astype(str)
        
        # Grid'lere göre grupla
        grids = {}
        for grid_id, group in df.groupby('grid_id'):
            grids[grid_id] = {
                'center_lat': group['grid_lat'].iloc[0],
                'center_lon': group['grid_lon'].iloc[0],
                'count': len(group),
                'avg_magnitude': group['mag'].mean(),
                'max_magnitude': group['mag'].max(),
                'location': group['location'].iloc[0]
            }
        
        return grids
    
    def detect_frequency_anomaly(self):
        """Frekans bazlı anomali tespiti"""
        print("🔍 Frekans Anomalisi Analizi...")
        
        # Son 48 saat
        recent_earthquakes = self.get_recent_earthquakes(hours=48)
        print(f"   📊 Son 48 saat: {len(recent_earthquakes)} deprem")
        
        # Baseline (90 gün)
        baseline_earthquakes = self.get_baseline_earthquakes(days=90)
        print(f"   📊 Baseline (90 gün): {len(baseline_earthquakes)} deprem")
        
        if len(baseline_earthquakes) < 10:
            print("   ⚠️  Yeterli baseline verisi yok\n")
            return []
        
        # Grid'lere böl
        recent_grids = self.create_grid(recent_earthquakes)
        baseline_grids = self.create_grid(baseline_earthquakes)
        
        anomalies = []
        
        for grid_id, recent_data in recent_grids.items():
            recent_count = recent_data['count']
            
            # Baseline'daki sayı
            baseline_count = baseline_grids.get(grid_id, {'count': 0})['count']
            
            # Günlük ortalamayı 48 saate çevir
            baseline_avg = (baseline_count / 90) * 2
            
            # Z-score hesapla
            if baseline_avg > 0:
                z_score = (recent_count - baseline_avg) / np.sqrt(baseline_avg)
            else:
                z_score = recent_count  # Yeni bölge
            
            # Anomali kontrolü
            if z_score > 2.5 and recent_count >= 5:
                alert_level = 'red' if z_score > 5 else 'orange' if z_score > 3.5 else 'yellow'
                
                print(f"\n   🚨 Anomali tespit edildi!")
                print(f"      📍 Konum: {recent_data['location']}")
                print(f"      📊 Son 48h: {recent_count} deprem")
                print(f"      📊 Normal: ~{baseline_avg:.1f} deprem")
                print(f"      📈 Z-score: {z_score:.2f}")
                print(f"      🔴 Seviye: {alert_level.upper()}")
                
                anomalies.append({
                    'latitude': recent_data['center_lat'],
                    'longitude': recent_data['center_lon'],
                    'radius_km': 50.0,
                    'z_score': z_score,
                    'earthquake_count': recent_count,
                    'baseline_rate': baseline_avg,
                    'current_rate': recent_count,
                    'location': recent_data['location'],
                    'is_active': True,
                    'detected_at': datetime.now(timezone.utc),
                    'alert_level': alert_level,
                    'anomaly_type': 'frequency',
                    'description': f"{recent_count} deprem tespit edildi - Z-score: {z_score:.1f}"
                })
        
        return anomalies
    
    def detect_magnitude_escalation(self):
        """Magnitüd artış anomalisi"""
        print("\n🔍 Magnitüd Kademeli Artış Analizi...")
        
        # Son 48 saat
        recent_earthquakes = self.get_recent_earthquakes(hours=48)
        
        if len(recent_earthquakes) < 5:
            return []
        
        # Grid'lere böl
        grids = self.create_grid(recent_earthquakes)
        
        anomalies = []
        
        for grid_id, grid_data in grids.items():
            if grid_data['count'] < 5:
                continue
            
            # Bu grid'deki depremleri al
            grid_earthquakes = [eq for eq in recent_earthquakes 
                              if abs(eq.latitude - grid_data['center_lat']) < self.grid_size/2
                              and abs(eq.longitude - grid_data['center_lon']) < self.grid_size/2]
            
            # Zamana göre sırala
            grid_earthquakes.sort(key=lambda x: x.timestamp)
            
            # Son 3 depremin ortalaması
            if len(grid_earthquakes) >= 3:
                last_3_avg = np.mean([eq.magnitude for eq in grid_earthquakes[-3:]])
                prev_avg = np.mean([eq.magnitude for eq in grid_earthquakes[:-3]]) if len(grid_earthquakes) > 3 else 0
                
                # Artış var mı?
                if last_3_avg > prev_avg + 0.5 and last_3_avg >= 3.0:
                    print(f"\n   🚨 Magnitüd artışı tespit edildi!")
                    print(f"      📍 Konum: {grid_data['location']}")
                    print(f"      📊 Deprem sayısı: {len(grid_earthquakes)}")
                    print(f"      📈 Son mag: {last_3_avg:.1f}")
                    print(f"      📉 Önceki ort: {prev_avg:.1f}")
                    print(f"      🔴 Seviye: ORANGE")
                    
                    anomalies.append({
                        'latitude': grid_data['center_lat'],
                        'longitude': grid_data['center_lon'],
                        'radius_km': 50.0,
                        'z_score': (last_3_avg - prev_avg) * 2,  # Yaklaşık skor
                        'earthquake_count': len(grid_earthquakes),
                        'baseline_rate': prev_avg,
                        'current_rate': last_3_avg,
                        'location': grid_data['location'],
                        'is_active': True,
                        'detected_at': datetime.now(timezone.utc),
                        'alert_level': 'orange',
                        'anomaly_type': 'magnitude_escalation',
                        'description': f"Magnitüd artışı: {prev_avg:.1f} → {last_3_avg:.1f}"
                    })
        
        return anomalies
    
    def save_anomalies(self, anomalies):
        """Anomalileri veritabanına kaydet - Gruplandırma ile"""
        try:
            new_count = 0
            
            for anomaly_data in anomalies:
                location = anomaly_data['location']
                
                # Aynı konumda aktif anomali var mı kontrol et
                existing = self.db.query(Anomaly).filter(
                    Anomaly.location == location,
                    Anomaly.is_active == True
                ).first()
                
                if existing:
                    # Mevcut anomaliyi güncelle
                    existing.z_score = anomaly_data['z_score']
                    existing.earthquake_count = anomaly_data['earthquake_count']
                    existing.current_rate = anomaly_data['current_rate']
                    existing.detected_at = datetime.now(timezone.utc)
                else:
                    # Yeni anomali ekle
                    anomaly = Anomaly(**anomaly_data)
                    self.db.add(anomaly)
                    new_count += 1
            
            self.db.commit()
            print(f"\n💾 {new_count} yeni anomali kaydedildi")
            
        except Exception as e:
            print(f"\n⚠️  Anomali kaydetme hatası: {e}")
            import traceback
            traceback.print_exc()
            self.db.rollback()
    
    def __del__(self):
        """Destructor - DB bağlantısını kapat"""
        if hasattr(self, 'db'):
            self.db.close()

if __name__ == "__main__":
    detector = AnomalyDetector()
    anomalies = detector.analyze()
    print(f"\n✅ {len(anomalies)} anomali tespit edildi!")