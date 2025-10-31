# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from schedulers.daily_report import send_daily_report
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger  # ← EKSİK IMPORT
from datetime import datetime
import time

from collectors.usgs_collector import USGSCollector
from collectors.kandilli_collector import KandilliCollector
from analyzers.anomaly_detector import AnomalyDetector
from alerts.email_service import EmailAlertService

def run_data_collection():
    """Veri toplama görevi"""
    print("\n" + "⏰"*30)
    print(f"🔄 OTOMATİK VERİ TOPLAMA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("⏰"*30 + "\n")
    
    try:
        # Kandilli
        print("📍 Kandilli'den veri çekiliyor...")
        kandilli = KandilliCollector()
        kandilli.collect()
        
        # USGS
        print("\n📍 USGS'den veri çekiliyor...")
        usgs = USGSCollector()
        usgs.collect(days=7, min_magnitude=2.5)
        
        print("\n✅ Veri toplama tamamlandı!")
        
    except Exception as e:
        print(f"❌ Veri toplama hatası: {e}")


def run_anomaly_detection():
    """Anomali tespit görevi"""
    print("\n" + "🧠"*30)
    print(f"🔍 OTOMATİK ANOMALİ ANALİZİ - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🧠"*30 + "\n")
    
    try:
        detector = AnomalyDetector()
        anomalies = detector.analyze()
        
        # Anomali varsa email gönder
        if anomalies:
            print(f"\n⚠️ {len(anomalies)} anomali tespit edildi!")
            
            email_service = EmailAlertService()
            if email_service.enabled:
                email_service.send_anomaly_alert(anomalies)
                print("📧 Email uyarısı gönderildi!")
        else:
            print("\n✅ Anomali tespit edilmedi")
        
    except Exception as e:
        print(f"❌ Anomali analizi hatası: {e}")


def start_scheduler():
    """Scheduler'ı başlat"""
    scheduler = BackgroundScheduler()
    
    # Her 15 dakikada bir veri topla
    scheduler.add_job(
        func=run_data_collection,
        trigger=IntervalTrigger(minutes=15),
        id='data_collection_job',
        name='Veri Toplama',
        replace_existing=True
    )
    
    # Günlük rapor - Her gün saat 22:00'da
    scheduler.add_job(
        func=send_daily_report,
        trigger=CronTrigger(hour=22, minute=0),
        id='daily_report',
        name='Günlük Deprem Raporu',
        replace_existing=True
    )
    
    # Her 30 dakikada bir anomali analizi yap
    scheduler.add_job(
        func=run_anomaly_detection,
        trigger=IntervalTrigger(minutes=30),
        id='anomaly_detection_job',
        name='Anomali Tespit',
        replace_existing=True
    )
    
    scheduler.start()
    
    print("\n" + "🚀"*30)
    print("✅ OTOMATİK SİSTEM BAŞLATILDI!")
    print("🚀"*30)
    print("\n📋 Çalışma Programı:")
    print("   🔄 Veri Toplama: Her 15 dakikada bir")
    print("   🧠 Anomali Analizi: Her 30 dakikada bir")
    print("   📧 Günlük Rapor: Her gün 22:00'da")
    print("\n💡 Sistemi durdurmak için CTRL+C basın\n")
    
    # İlk çalıştırmayı hemen yap
    print("🏃 İlk veri toplama başlatılıyor...\n")
    run_data_collection()
    
    print("\n🏃 İlk anomali analizi başlatılıyor...\n")
    run_anomaly_detection()
    
    # Sonsuz döngü - CTRL+C ile dur
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        print("\n\n🛑 Sistem durduruluyor...")
        scheduler.shutdown()
        print("✅ Sistem güvenli şekilde kapatıldı!\n")


if __name__ == "__main__":
    start_scheduler()