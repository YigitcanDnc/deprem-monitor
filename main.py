import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from collectors.usgs_collector import USGSCollector
from collectors.kandilli_collector import KandilliCollector
from analyzers.anomaly_detector import AnomalyDetector
from alerts.email_service import EmailAlertService
from database.models import init_database
from datetime import datetime

def collect_all_data():
    """Tüm kaynaklardan veri topla"""
    print("\n" + "="*60)
    print("🌍 DEPREM TAKİP SİSTEMİ - VERİ TOPLAMA")
    print("="*60)
    print(f"⏰ Başlangıç: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    # 1. Kandilli (Türkiye)
    print("📍 1/2: Türkiye depremlerini çekiyorum (Kandilli)...")
    kandilli = KandilliCollector()
    kandilli.collect()
    
    # 2. USGS (Global)
    print("\n📍 2/2: Global depremlerini çekiyorum (USGS)...")
    usgs = USGSCollector()
    usgs.collect(days=7, min_magnitude=2.5)
    
    print("\n" + "="*60)
    print("✅ TÜM VERİLER BAŞARIYLA TOPLANDI!")
    print("="*60 + "\n")


def analyze_anomalies():
    """Anomali analizi yap"""
    detector = AnomalyDetector()
    anomalies = detector.analyze()
    return anomalies


def send_alerts(anomalies):
    """Anomali varsa email gönder"""
    if not anomalies:
        print("📧 Anomali yok, email gönderilmedi")
        return
    
    email_service = EmailAlertService()
    
    if email_service.enabled:
        success = email_service.send_anomaly_alert(anomalies)
        if success:
            print(f"✅ {len(anomalies)} anomali için email uyarısı gönderildi!")
        else:
            print("❌ Email gönderimi başarısız")
    else:
        print("⚠️ Email servisi devre dışı - .env dosyasını kontrol et")


def run_full_system():
    """Sistemi tam çalıştır: Veri topla + Analiz yap + Email gönder"""
    print("\n" + "🔥"*30)
    print("🚀 DEPREM TAKİP SİSTEMİ - TAM ÇALIŞTIRMA")
    print("🔥"*30)
    print(f"⏰ Başlangıç: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. Veri toplama
    collect_all_data()
    
    # 2. Anomali analizi
    anomalies = analyze_anomalies()
    
    # 3. Email uyarısı (anomali varsa)
    if anomalies:
        send_alerts(anomalies)
    
    print("\n" + "🔥"*30)
    print("✅ SİSTEM ÇALIŞTIRMASI TAMAMLANDI!")
    print(f"⏰ Bitiş: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if anomalies:
        print(f"\n⚠️  {len(anomalies)} ANOMALİ TESPİT EDİLDİ!")
        print("📧 Email uyarısı gönderildi")
    else:
        print("\n✅ Anomali tespit edilmedi - her şey normal")
    
    print("🔥"*30 + "\n")


if __name__ == "__main__":
    # Veritabanı kontrol
    print("🔍 Veritabanı kontrol ediliyor...")
    if init_database():
        run_full_system()
    else:
        print("❌ Veritabanı bağlantısı başarısız!")