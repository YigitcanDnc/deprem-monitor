# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from database.models import AlertLog, SessionLocal

class EmailAlertService:
    """Email ile uyarı gönderme servisi"""
    
    def __init__(self):
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.alert_email = os.getenv('ALERT_EMAIL')
        
        if not all([self.email_user, self.email_password, self.alert_email]):
            print("⚠️  Email ayarları yapılmamış (.env dosyasını kontrol et)")
            self.enabled = False
        else:
            self.enabled = True
    
    def send_anomaly_alert(self, anomalies):
        """Anomali uyarısı gönder"""
        if not self.enabled:
            print("📧 Email servisi devre dışı")
            return False
        
        if not anomalies:
            return False
        
        try:
            # Email içeriği oluştur
            subject = f"🚨 {len(anomalies)} Deprem Anomalisi Tespit Edildi!"
            
            html_body = self._create_html_body(anomalies)
            
            # Email mesajı oluştur
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_user
            msg['To'] = self.alert_email
            
            html_part = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Gmail SMTP ile gönder
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(self.email_user, self.email_password)
                smtp.send_message(msg)
            
            print(f"✅ Email uyarısı gönderildi: {self.alert_email}")
            
            # Log kaydet
            self._log_alert(anomalies)
            
            return True
            
        except Exception as e:
            print(f"❌ Email gönderme hatası: {e}")
            return False
    
    def _create_html_body(self, anomalies):
        """HTML email içeriği oluştur"""
        
        anomaly_rows = ""
        for anomaly in anomalies:
            alert_color = {
                'yellow': '#FFD700',
                'orange': '#FF8C00',
                'red': '#FF0000'
            }.get(anomaly.get('alert_level', 'yellow'), '#FFD700')
            
            # Anomali tipi Türkçeleştir
            anomaly_type_tr = {
                'frequency': 'Frekans Artışı',
                'magnitude_escalation': 'Büyüklük Artışı',
                'b_value': 'B-Değer Değişimi'
            }.get(anomaly.get('type', 'frequency'), 'Frekans Artışı')
            
            anomaly_rows += f"""
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 12px;">{anomaly.get('location', 'Bilinmiyor')}</td>
                <td style="padding: 12px;">{anomaly_type_tr}</td>
                <td style="padding: 12px; text-align: center;">
                    <span style="background: {alert_color}; color: white; padding: 5px 10px; border-radius: 5px; font-weight: bold;">
                        {anomaly.get('alert_level', 'yellow').upper()}
                    </span>
                </td>
                <td style="padding: 12px; text-align: center;">
                    {anomaly.get('recent_count', anomaly.get('count', 0))}
                </td>
                <td style="padding: 12px; text-align: center;">
                    {anomaly.get('max_magnitude', 0):.1f}
                </td>
            </tr>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="margin: 0;">🚨 Deprem Anomali Uyarısı</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Deprem Takip ve Anomali Tespit Sistemi</p>
                </div>
                
                <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; margin-top: 0;">
                        <strong>{len(anomalies)} bölgede</strong> anormal deprem aktivitesi tespit edildi.
                    </p>
                    
                    <p style="background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0;">
                        ⚠️ <strong>Önemli:</strong> Bu uyarı, belirlenen bölgelerde normalin üzerinde deprem aktivitesi olduğunu gösterir. 
                        Lütfen hazırlıklı olun ve güncel gelişmeleri takip edin.
                    </p>
                    
                    <table style="width: 100%; border-collapse: collapse; background: white; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <thead>
                            <tr style="background: #667eea; color: white;">
                                <th style="padding: 12px; text-align: left;">Bölge</th>
                                <th style="padding: 12px; text-align: left;">Tip</th>
                                <th style="padding: 12px; text-align: center;">Seviye</th>
                                <th style="padding: 12px; text-align: center;">Deprem Sayısı</th>
                                <th style="padding: 12px; text-align: center;">En Büyük</th>
                            </tr>
                        </thead>
                        <tbody>
                            {anomaly_rows}
                        </tbody>
                    </table>
                    
                    <div style="margin-top: 30px; padding-top: 20px; border-top: 2px solid #ddd;">
                        <p style="font-size: 14px; color: #666;">
                            <strong>Tarih:</strong> {(datetime.now() + timedelta(hours=3)).strftime('%d.%m.%Y %H:%M:%S')} (GMT+3)<br>
                            <strong>Sistem:</strong> Deprem Takip ve Anomali Tespit Sistemi<br>
                            <strong>Geliştirici:</strong> Yiğit - İnşaat Mühendisi
                        </p>
                        
                        <p style="margin-top: 15px; padding: 12px; background: #e3f2fd; border-left: 4px solid #2196f3; font-size: 13px; border-radius: 4px;">
                            💡 <strong>Not:</strong> Bu sistem otomatik olarak çalışır ve anormal deprem aktivitesi tespit ettiğinde sizi bilgilendirir. 
                            Daha fazla detay için web arayüzünü ziyaret edebilirsiniz.
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _log_alert(self, anomalies):
        """Gönderilen uyarıyı logla"""
        db = SessionLocal()
        
        try:
            for anomaly in anomalies:
                log = AlertLog(
                    anomaly_id=anomaly.get('id', 0),
                    recipient=self.alert_email,
                    alert_type='email',
                    message=f"Anomali uyarısı: {anomaly.get('location', 'Bilinmiyor')}"
                )
                db.add(log)
            
            db.commit()
        except:
            db.rollback()
        finally:
            db.close()


if __name__ == "__main__":
    # Test için
    service = EmailAlertService()
    
    test_anomalies = [{
        'location': 'MARMARA DENİZİ (İSTANBUL)',
        'type': 'frequency',
        'alert_level': 'orange',
        'recent_count': 15,
        'max_magnitude': 4.2
    }]
    
    service.send_anomaly_alert(test_anomalies)