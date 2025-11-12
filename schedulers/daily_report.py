# -*- coding: utf-8 -*-
"""
Günlük Deprem Raporu - Her gün saat 22:00'da email gönderir
"""
import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_
from dotenv import load_dotenv

# PYTHON PATH DÜZELTMESİ - Proje root'unu ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Şimdi import edebiliriz
from database.models import Earthquake, Anomaly, SessionLocal

load_dotenv()

def get_turkey_time():
    """Türkiye saatini döndür (UTC+3)"""
    turkey_tz = timezone(timedelta(hours=3))
    return datetime.now(timezone.utc).astimezone(turkey_tz)

def get_daily_stats(days_back=0):
    """
    Belirtilen gün öncesinin deprem istatistiklerini hesapla
    days_back=0: Bugün
    days_back=1: Dün
    """
    db = SessionLocal()
    
    try:
        # Türkiye saati ile hedef günün başlangıcı (00:00)
        turkey_now = get_turkey_time()
        target_day = turkey_now - timedelta(days=days_back)
        today_start = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # UTC'ye çevir
        today_start_utc = today_start.astimezone(timezone.utc)
        today_end_utc = today_end.astimezone(timezone.utc)
        
        print(f"\n🔍 Tarih Aralığı:")
        print(f"   📅 Başlangıç (TR): {today_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   📅 Bitiş (TR): {today_end.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   🌍 Başlangıç (UTC): {today_start_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   🌍 Bitiş (UTC): {today_end_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Hedef günün depremleri - Naive timestamp karşılaştırması
        earthquakes_today = db.query(Earthquake).filter(
            and_(
                Earthquake.timestamp >= today_start_utc.replace(tzinfo=None),
                Earthquake.timestamp < today_end_utc.replace(tzinfo=None)
            )
        ).all()
        
        # Eğer hala bulamazsa, son 24 saati dene
        if len(earthquakes_today) == 0:
            print("⚠️  Bugünün verisi bulunamadı, son 24 saat deneniyor...")
            last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
            earthquakes_today = db.query(Earthquake).filter(
                Earthquake.timestamp >= last_24h.replace(tzinfo=None)
            ).all()
        
        # İstatistikler
        total_count = len(earthquakes_today)
        
        print(f"\n📊 Bulunan deprem sayısı: {total_count}")
        
        if total_count == 0:
            return None
        
        max_eq = max(earthquakes_today, key=lambda x: x.magnitude)
        
        # Büyüklük dağılımı
        mag_distribution = {
            '5.0+': len([eq for eq in earthquakes_today if eq.magnitude >= 5.0]),
            '4.0-4.9': len([eq for eq in earthquakes_today if 4.0 <= eq.magnitude < 5.0]),
            '3.0-3.9': len([eq for eq in earthquakes_today if 3.0 <= eq.magnitude < 4.0]),
            '2.5-2.9': len([eq for eq in earthquakes_today if 2.5 <= eq.magnitude < 3.0]),
        }
        
        # Aktif anomaliler - TÜM ANOMALİLERİ SAY (is_active kontrolü yapma)
        try:
            # Son 48 saatteki tüm anomalileri say
            recent_anomalies = db.query(Anomaly).filter(
                Anomaly.detected_at >= datetime.now(timezone.utc) - timedelta(hours=48)
            ).all()
            active_anomalies = recent_anomalies
            print(f"📊 Aktif anomali sayısı: {len(active_anomalies)}")
        except Exception as e:
            print(f"⚠️ Anomali sorgusu hatası: {e}")
            active_anomalies = []
        
        # Bölgesel dağılım (şehir bazlı) - GELİŞTİRİLMİŞ PARSE
        regional_counts = {}
        for eq in earthquakes_today:
            # Lokasyonu temizle
            location = eq.location.replace('İlksel', '').replace('Revize', '').strip()
    
            # Şehir çıkarma mantığı
            city = None
    
            # 1. Önce parantez içini kontrol et
            if '(' in location and ')' in location:
                city = location.split('(')[-1].replace(')', '').strip()
                # 2. Parantez yoksa, tire sonrasını al
            elif '-' in location:
                parts = location.split('-')
                city = parts[-1].strip()
                # 3. Hiçbiri yoksa tüm metni al (Kıbrıs gibi)
            else:
                city = location.strip()
    
            # Son temizlik
            if city:
                city = city.replace('İlksel', '').replace('Revize', '').strip()
            if city:  # Boş değilse
                regional_counts[city] = regional_counts.get(city, 0) + 1
        
        # En aktif 5 bölge
        top_regions = sorted(regional_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Son 7 günlük trend
        trend_data = []
        for i in range(6, -1, -1):
            day_start = (today_start - timedelta(days=i)).astimezone(timezone.utc).replace(tzinfo=None)
            day_end = (today_start - timedelta(days=i-1)).astimezone(timezone.utc).replace(tzinfo=None)
            
            day_count = db.query(Earthquake).filter(
                and_(
                    Earthquake.timestamp >= day_start,
                    Earthquake.timestamp < day_end
                )
            ).count()
            
            trend_data.append({
                'date': (today_start - timedelta(days=i)).strftime('%d %b'),
                'count': day_count
            })
        
        return {
            'date': target_day.strftime('%d %B %Y'),
            'total_count': total_count,
            'max_earthquake': {
                'magnitude': max_eq.magnitude,
                'location': max_eq.location.replace('İlksel', '').replace('Revize', '').strip(),
                'time': max_eq.timestamp.strftime('%H:%M') if hasattr(max_eq.timestamp, 'strftime') else str(max_eq.timestamp)
            },
            'mag_distribution': mag_distribution,
            'top_regions': top_regions,
            'active_anomalies': active_anomalies,
            'trend_data': trend_data
        }
        
    except Exception as e:
        print(f"❌ İstatistik hesaplama hatası: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()

def create_html_report(stats):
    """HTML email raporu oluştur"""
    if not stats:
        return """
        <html>
        <body style="font-family: Arial, sans-serif; background: #f3f4f6; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 20px;">
                <h2 style="color: #dc2626;">📊 Günlük Deprem Raporu</h2>
                <p>Bugün herhangi bir deprem kaydı bulunmamaktadır.</p>
                <p style="color: #6b7280; font-size: 14px; margin-top: 20px;">
                    Not: Eğer bu mesajı sürekli alıyorsanız, veri toplama sistemini kontrol edin.
                </p>
            </div>
        </body>
        </html>
        """
    
    anomalies_html = ""
    if stats['active_anomalies']:
        anomalies_html = "<h3 style='color: #dc2626;'>🚨 Aktif Anomaliler</h3><ul>"
        for anomaly in stats['active_anomalies'][:5]:
            alert_level = "RED" if anomaly.z_score > 5 else "ORANGE" if anomaly.z_score > 3 else "YELLOW"
            anomalies_html += f"""
            <li>
                <strong>{anomaly.location}</strong> - 
                Z-Score: {anomaly.z_score:.1f} - 
                <span style='color: #dc2626; font-weight: bold;'>{alert_level}</span>
            </li>
            """
        anomalies_html += "</ul>"
    else:
        anomalies_html = "<p style='color: #22c55e;'>✅ Aktif anomali bulunmamaktadır.</p>"
    
    regions_html = "<ol>"
    for city, count in stats['top_regions']:
        regions_html += f"<li><strong>{city}</strong>: {count} deprem</li>"
    regions_html += "</ol>"
    
    trend_html = "<table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>"
    for idx, day in enumerate(stats['trend_data']):
        trend_arrow = ""
        if idx > 0:
            prev_count = stats['trend_data'][idx - 1]['count']
            if day['count'] > prev_count:
                trend_arrow = "↗️"
            elif day['count'] < prev_count:
                trend_arrow = "↘️"
            else:
                trend_arrow = "→"
        
        trend_html += f"""
        <tr style='border-bottom: 1px solid #e5e7eb;'>
            <td style='padding: 8px;'>{day['date']}</td>
            <td style='padding: 8px; text-align: right;'>{day['count']} deprem {trend_arrow}</td>
        </tr>
        """
    trend_html += "</table>"
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f3f4f6; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            h2 {{ color: #dc2626; border-bottom: 3px solid #dc2626; padding-bottom: 10px; }}
            h3 {{ color: #374151; margin-top: 25px; }}
            .stat-box {{ background: #f9fafb; padding: 15px; border-radius: 6px; margin: 15px 0; border-left: 4px solid #dc2626; }}
            .highlight {{ font-size: 24px; font-weight: bold; color: #dc2626; }}
            ul, ol {{ line-height: 1.8; }}
            .footer {{ margin-top: 30px; padding-top: 20px; border-top: 2px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🌍 Günlük Deprem Raporu</h2>
            <p style="color: #6b7280; font-size: 16px;">{stats['date']}</p>
            
            <div class="stat-box">
                <h3 style="margin-top: 0;">📊 Özet İstatistikler</h3>
                <p><strong>Toplam Deprem:</strong> <span class="highlight">{stats['total_count']}</span></p>
                <p><strong>En Büyük:</strong> M{stats['max_earthquake']['magnitude']:.1f} - {stats['max_earthquake']['location']}</p>
                <p><strong>Saat:</strong> {stats['max_earthquake']['time']} (Türkiye Saati)</p>
                <p><strong>Aktif Anomali:</strong> {len(stats['active_anomalies'])} bölge</p>
            </div>
            
            <h3>📈 Büyüklük Dağılımı</h3>
            <ul>
                <li><strong>M5.0+:</strong> {stats['mag_distribution']['5.0+']} deprem</li>
                <li><strong>M4.0-4.9:</strong> {stats['mag_distribution']['4.0-4.9']} deprem</li>
                <li><strong>M3.0-3.9:</strong> {stats['mag_distribution']['3.0-3.9']} deprem</li>
                <li><strong>M2.5-2.9:</strong> {stats['mag_distribution']['2.5-2.9']} deprem</li>
            </ul>
            
            <h3>🗺️ En Aktif Bölgeler</h3>
            {regions_html}
            
            {anomalies_html}
            
            <h3>📉 7 Günlük Trend</h3>
            {trend_html}
            
            <div class="footer">
                <p>🗺️ <a href="https://web-production-33a32.up.railway.app" style="color: #dc2626; text-decoration: none;">Detaylı Haritayı Görüntüle</a></p>
                <p>Bu rapor otomatik olarak oluşturulmuştur.</p>
                <p style="font-size: 12px; color: #9ca3af;">Deprem Takip ve Anomali Tespit Sistemi © 2025</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def send_daily_report():
    """Günlük raporu email olarak gönder"""
    print("\n" + "="*60)
    print("📧 GÜNLÜK DEPREM RAPORU GÖNDERİLİYOR")
    print("="*60)
    
    try:
        # İstatistikleri hesapla (bugün)
        stats = get_daily_stats(days_back=0)
        
        if not stats:
            print("⚠️  Bugün deprem verisi yok.")
            
            # Dün veri var mı kontrol et
            print("\n🔍 Dünün verisi kontrol ediliyor...")
            stats = get_daily_stats(days_back=1)
            
            if not stats:
                print("⚠️  Dün de veri yok, rapor gönderilmedi.")
                return
            else:
                print("✅ Dünün verisi bulundu, onunla rapor gönderiliyor...")
        
        # HTML rapor oluştur
        html_content = create_html_report(stats)
        
        # Email ayarları
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT'))
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        alert_email = os.getenv('ALERT_EMAIL')
        
        if not all([smtp_server, smtp_port, smtp_username, smtp_password, alert_email]):
            print("❌ SMTP ayarları eksik!")
            return
        
        # Email mesajı oluştur
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"📊 Günlük Deprem Raporu - {stats['date']}"
        msg['From'] = smtp_username
        msg['To'] = alert_email
        
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # SMTP ile gönder
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        print(f"\n✅ Günlük rapor gönderildi: {alert_email}")
        print(f"📊 Toplam deprem: {stats['total_count']}")
        print(f"📈 En büyük: M{stats['max_earthquake']['magnitude']:.1f}")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Günlük rapor gönderme hatası: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Manuel test için
    send_daily_report()