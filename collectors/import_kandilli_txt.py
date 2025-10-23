# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from database.models import Earthquake, SessionLocal

class KandilliTxtImporter:
    """Kandilli .txt dosyalarını veritabanına aktar"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def parse_kandilli_line(self, line):
        """Kandilli tab-separated formatını parse et"""
        line = line.strip()
        
        # Boş satır veya başlık satırı ise atla
        if not line or 'Deprem Kodu' in line or 'No' in line or line.startswith('---'):
            return None
        
        # TAB ile ayır
        parts = line.split('\t')
        
        if len(parts) < 15:
            return None
        
        try:
            # Sütunlar:
            # 0: No, 1: Deprem Kodu, 2: Tarih, 3: Saat, 4: Enlem, 5: Boylam, 
            # 6: Derinlik, 7: xM, 8: MD, 9: ML, 10: Mw, 11: Ms, 12: Mb, 13: Tip, 14: Yer
            
            date = parts[2].strip()  # 1995.12.31
            time = parts[3].strip()  # 05:16:19.20
            
            # Saniye kısmını sadeleştir (05:16:19.20 -> 05:16:19)
            if '.' in time:
                time = time.split('.')[0]
            
            latitude = float(parts[4].strip())
            longitude = float(parts[5].strip())
            depth = float(parts[6].strip())
            
            # Büyüklükler
            xm = parts[7].strip()
            md = parts[8].strip()
            ml = parts[9].strip()
            mw = parts[10].strip()
            ms = parts[11].strip()
            mb = parts[12].strip()
            
            location = parts[14].strip() if len(parts) > 14 else 'Bilinmiyor'
            
            # En büyük magnitude'ü bul
            mags = []
            for mag_val in [mw, ms, mb, ml, md, xm]:
                if mag_val and mag_val not in ['0.0', '0', '', '0.00']:
                    try:
                        mag_float = float(mag_val)
                        if mag_float > 0:
                            mags.append(mag_float)
                    except:
                        pass
            
            if not mags:
                return None
            
            magnitude = max(mags)
            
            # Tarih parse et
            timestamp = datetime.strptime(f"{date} {time}", "%Y.%m.%d %H:%M:%S")
            
            return {
                'timestamp': timestamp,
                'latitude': latitude,
                'longitude': longitude,
                'depth': depth,
                'magnitude': magnitude,
                'location': location,
                'date': date,
                'time': time
            }
            
        except (ValueError, IndexError) as e:
            return None
    
    def import_file(self, file_path):
        """Tek bir .txt dosyasını içe aktar"""
        
        if not os.path.exists(file_path):
            print(f"❌ Dosya bulunamadı: {file_path}")
            return 0
        
        print(f"\n📄 İşleniyor: {os.path.basename(file_path)}")
        
        saved_count = 0
        skipped_count = 0
        error_count = 0
        
        try:
            encodings = ['ISO-8859-9', 'utf-8', 'latin-1', 'cp1254']
            lines = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        lines = f.readlines()
                    break
                except:
                    continue
            
            if not lines:
                print(f"   ❌ Dosya okunamadı")
                return 0
            
            print(f"   📊 Toplam satır: {len(lines)}")
            
            # İlk satır başlık, onu atla
            data_lines = lines[1:]
            
            for line in data_lines:
                eq_data = self.parse_kandilli_line(line)
                
                if not eq_data:
                    error_count += 1
                    continue
                
                event_id = f"kandilli_manual_{eq_data['date'].replace('.', '')}_{eq_data['time'].replace(':', '')}_{eq_data['latitude']:.2f}_{eq_data['longitude']:.2f}"
                
                existing = self.db.query(Earthquake).filter_by(event_id=event_id).first()
                if existing:
                    skipped_count += 1
                    continue
                
                earthquake = Earthquake(
                    event_id=event_id,
                    timestamp=eq_data['timestamp'],
                    latitude=eq_data['latitude'],
                    longitude=eq_data['longitude'],
                    magnitude=eq_data['magnitude'],
                    depth=eq_data['depth'],
                    location=eq_data['location'],
                    source='Kandilli_Manual',
                    geometry=f"POINT({eq_data['longitude']} {eq_data['latitude']})"
                )
                
                self.db.add(earthquake)
                saved_count += 1
                
                if saved_count % 500 == 0:
                    self.db.commit()
                    print(f"   ⏳ {saved_count:,} kayıt eklendi...")
            
            self.db.commit()
            
            print(f"   ✅ {saved_count:,} yeni kayıt eklendi")
            print(f"   ⏭️  {skipped_count:,} zaten mevcuttu")
            if error_count > 0:
                print(f"   ⚠️  {error_count:,} satır parse edilemedi")
            
        except Exception as e:
            self.db.rollback()
            print(f"   ❌ Hata: {e}")
            import traceback
            traceback.print_exc()
            return 0
        
        return saved_count
    
    def import_multiple_files(self, file_paths):
        """Birden fazla dosyayı içe aktar"""
        print("\n" + "="*60)
        print("📥 KANDİLLİ VERİLERİ İÇE AKTARMA")
        print("   (1990-2025 Arası TAB-Separated Format)")
        print("="*60)
        
        total_saved = 0
        successful_files = 0
        
        for file_path in file_paths:
            saved = self.import_file(file_path)
            if saved > 0:
                successful_files += 1
            total_saved += saved
        
        print("\n" + "="*60)
        print("📊 İÇE AKTARMA TAMAMLANDI")
        print("="*60)
        print(f"✅ İşlenen Dosya: {successful_files}/{len(file_paths)}")
        print(f"✅ Toplam Eklenen Deprem: {total_saved:,}")
        print("="*60 + "\n")
        
        return total_saved
    
    def __del__(self):
        self.db.close()


if __name__ == "__main__":
    importer = KandilliTxtImporter()
    
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(parent_dir, 'data')
    
    print(f"🔍 Aranan konum: {data_dir}\n")
    
    found_files = []
    
    if os.path.exists(data_dir):
        all_files = os.listdir(data_dir)
        txt_files = [f for f in all_files if f.endswith('.txt')]
        
        print(f"📂 data/ klasöründeki .txt dosyaları:\n")
        for txt_file in sorted(txt_files):
            file_path = os.path.join(data_dir, txt_file)
            found_files.append(file_path)
            print(f"   ✅ {txt_file}")
    
    if not found_files:
        print("❌ data/ klasöründe .txt dosyası bulunamadı!")
    else:
        print(f"\n⏱️  Tahmini süre: {len(found_files) * 3}-{len(found_files) * 8} dakika")
        print("💾 Veritabanına onbinlerce kayıt eklenecek...\n")
        
        response = input("ENTER'a basarak içe aktarmayı başlat (veya CTRL+C ile iptal): ")
        
        total = importer.import_multiple_files(found_files)
        
        if total > 0:
            print("\n🎉 BAŞARILI! 35 YILLIK VERİ YÜKLENDİ!")
            print(f"\n📊 Toplam {total:,} deprem kaydı eklendi!")
            print("\n💡 Şimdi şunları yapabilirsiniz:")
            print("   1. Veritabanını kontrol edin:")
            print("      python analysis/check_database.py")
            print("\n   2. Retrospektif analizi çalıştırın:")
            print("      python analysis/retrospective_analysis.py")