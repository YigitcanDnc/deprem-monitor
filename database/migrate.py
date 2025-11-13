# -*- coding: utf-8 -*-
"""Database migration - Add missing columns"""
import os
import sys

# PYTHON PATH düzeltmesi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL bulunamadı!")
    sys.exit(1)

print(f"🔗 Bağlanıyorum: {DATABASE_URL[:40]}...")

engine = create_engine(DATABASE_URL)

def migrate():
    """Add missing columns to anomalies table"""
    try:
        with engine.connect() as conn:
            print("🔧 Kolonları ekliyorum...")
            
            conn.execute(text('ALTER TABLE anomalies ADD COLUMN IF NOT EXISTS alert_level VARCHAR;'))
            print("  ✅ alert_level eklendi")
            
            conn.execute(text('ALTER TABLE anomalies ADD COLUMN IF NOT EXISTS anomaly_type VARCHAR;'))
            print("  ✅ anomaly_type eklendi")
            
            conn.execute(text('ALTER TABLE anomalies ADD COLUMN IF NOT EXISTS description TEXT;'))
            print("  ✅ description eklendi")
            
            conn.commit()
            
            print("\n✅ Migration tamamlandı!")
            
            # Kontrol et
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'anomalies';"))
            columns = [row[0] for row in result]
            print(f"\n📋 Anomalies kolonları: {', '.join(columns)}")
            
    except Exception as e:
        print(f"\n❌ Migration hatası: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate()