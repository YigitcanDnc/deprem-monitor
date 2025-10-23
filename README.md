# 🌍 Deprem Takip ve Anomali Tespit Sistemi

Türkiye ve dünya genelindeki depremleri gerçek zamanlı takip eden, anormal aktiviteleri tespit edip email ile uyaran sistem.

## 🎯 Özellikler

- ✅ **Gerçek Zamanlı Veri Toplama** - Kandilli ve USGS'den otomatik veri çekme
- ✅ **Anomali Tespiti** - İstatistiksel analiz ile anormal deprem aktivitesi tespiti
- ✅ **Email Uyarıları** - Kritik anomaliler için otomatik email bildirimleri
- ✅ **İnteraktif Harita** - Google Maps üzerinde görselleştirme
- ✅ **35 Yıllık Veri Arşivi** - 1990-2025 arası 38,963 deprem kaydı
- ✅ **Retrospektif Analiz** - Geçmiş büyük depremler öncesi analiz

## 🚀 Teknolojiler

- **Backend:** Python, FastAPI, SQLAlchemy
- **Database:** PostgreSQL + PostGIS
- **Frontend:** HTML5, JavaScript, Google Maps API
- **Data Sources:** Kandilli Rasathanesi, USGS

## 📊 Kurulum
```bash
# Clone repository
git clone https://github.com/yourusername/deprem-monitor.git
cd deprem-monitor

# Virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your credentials

# Initialize database
python database/init_db.py

# Run API
python api.py

# Run scheduler (separate terminal)
python scheduler.py
```

## 🗺️ Kullanım

API başladıktan sonra tarayıcıda aç:
```
http://localhost:8000
```

## 📈 Sistem Performansı

- **Veri Toplama:** 15 dakikada bir
- **Anomali Kontrolü:** 1 saatte bir
- **API Response:** < 100ms
- **Otomatik Yenileme:** 5 dakika

## 🔬 Retrospektif Analiz
```bash
python analysis/retrospective_analysis.py
```

## 👨‍💻 Geliştirici

**Yiğit** - İnşaat Mühendisi | Deprem İzleme Sistemi Geliştiricisi

---

**Not:** Bu sistem deprem tahmini yapmaz, sadece anormal aktiviteleri tespit eder.