import json
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import statistics

# Proje kök dizini
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

try:
    from qa_app.core.rag_engine import RAGEngine

except ImportError:
    print("HATA: 'qa_app.rag_engine' modülü bulunamadı.")
    sys.exit(1)


@dataclass
class TestCase:
    """Tek bir test sorusunu temsil eder"""
    question: str
    category: str
    difficulty: str  # "easy", "medium", "hard"
    expected_keywords: List[str]  # Cevaptazı burada olması gereken kelimeler
    should_contain_source: bool = True  # Context'te kaynak belge bekleniyor mu?
    

@dataclass
class TestResult:
    """Bir test sonucunu temsil eder"""
    question: str
    category: str
    difficulty: str
    answer: str
    contexts: List[str]
    response_time: float
    contains_keywords: bool
    has_context: bool
    error: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


# --- GENİŞLETİLMİŞ TEST SETİ (100+ SORU) ---
TEST_SUITE = [
    # === ÇAP / YANDAL (20 soru) ===
    TestCase("Çift anadal programına başvuru koşulları nelerdir?", "cap_yandal", "medium",
             ["GANO", "3.0", "başvuru", "koşul"]),
    TestCase("ÇAP yapmak için GANO en az kaç olmalı?", "cap_yandal", "easy",
             ["3.0", "GANO"]),
    TestCase("Yandal başvurusu nasıl yapılır?", "cap_yandal", "medium",
             ["başvuru", "online", "sistem"]),
    TestCase("Kimler çift anadal programına başvuramaz?", "cap_yandal", "medium",
             ["disiplin", "ceza", "şart"]),
    TestCase("ÇAP programından çıkarılma şartları nelerdir?", "cap_yandal", "medium",
             ["GANO", "düşük", "başarısız"]),
    TestCase("Yandal diploma almak için kaç kredi gerekir?", "cap_yandal", "easy",
             ["kredi", "30", "diploma"]),
    TestCase("ÇAP'tan mezuniyet için şartlar nelerdir?", "cap_yandal", "hard",
             ["mezuniyet", "GANO", "gerekli"]),
    TestCase("Yandal programında kaç ders almak zorunludur?", "cap_yandal", "medium",
             ["ders", "sayı", "zorunlu"]),
    TestCase("ÇAP öğrencisi dönemde en fazla kaç AKTS alabilir?", "cap_yandal", "medium",
             ["AKTS", "dönem", "maksimum"]),
    TestCase("Yandal programına hangi dönemde başvurulur?", "cap_yandal", "easy",
             ["dönem", "başvuru", "tarih"]),
    TestCase("ÇAP öğrencisi ara sınıfta kalırsa ne olur?", "cap_yandal", "hard",
             ["ara sınıf", "durum", "sonuç"]),
    TestCase("Yandal programı kaç yılda tamamlanır?", "cap_yandal", "medium",
             ["yıl", "süre", "tamamlama"]),
    TestCase("ÇAP öğrencisi staj yapmak zorunda mı?", "cap_yandal", "medium",
             ["staj", "zorunlu", "ÇAP"]),
    TestCase("Yandal diploması ana diploma ile birlikte mi verilir?", "cap_yandal", "easy",
             ["diploma", "teslim", "birlikte"]),
    TestCase("ÇAP başvurusu için hangi belgeler gerekir?", "cap_yandal", "medium",
             ["belge", "başvuru", "gerekli"]),
    TestCase("Yandal programında ders seçimi nasıl yapılır?", "cap_yandal", "medium",
             ["ders seçimi", "kayıt", "sistem"]),
    TestCase("ÇAP öğrencisinin danışmanı kim olur?", "cap_yandal", "easy",
             ["danışman", "kim", "ÇAP"]),
    TestCase("Yandal programında FF aldığımda ne olur?", "cap_yandal", "hard",
             ["FF", "başarısızlık", "sonuç"]),
    TestCase("ÇAP ile yandal arasındaki fark nedir?", "cap_yandal", "medium",
             ["fark", "ÇAP", "yandal"]),
    TestCase("Yandal öğrencisi mezuniyet projesine katılır mı?", "cap_yandal", "hard",
             ["mezuniyet projesi", "katılım", "yandal"]),
    
    # === YATAY GEÇİŞ (15 soru) ===
    TestCase("Kurumlar arası yatay geçiş için YKS puanı ne kadar etkili?", "yatay_gecis", "medium",
             ["YKS", "puan", "%50"]),
    TestCase("Yatay geçiş başvuruları ne zaman yapılır?", "yatay_gecis", "easy",
             ["başvuru", "tarih", "dönem"]),
    TestCase("AGNO ile yatay geçiş şartları nelerdir?", "yatay_gecis", "medium",
             ["AGNO", "şart", "geçiş"]),
    TestCase("Hazırlık okuyan öğrenci yatay geçiş yapabilir mi?", "yatay_gecis", "medium",
             ["hazırlık", "yatay geçiş", "şart"]),
    TestCase("Yatay geçişte kontenjan nasıl belirlenir?", "yatay_gecis", "hard",
             ["kontenjan", "belirleme", "kriter"]),
    TestCase("DGS ile yatay geçiş yapılabilir mi?", "yatay_gecis", "medium",
             ["DGS", "geçiş", "mümkün"]),
    TestCase("Yatay geçişte hangi dersler muaf tutuluır?", "yatay_gecis", "hard",
             ["ders muafiyeti", "intibak", "kabul"]),
    TestCase("Kurumlar arası yatay geçiş için minimum AGNO kaç olmalı?", "yatay_gecis", "easy",
             ["AGNO", "minimum", "şart"]),
    TestCase("Yatay geçiş başvurusu hangi belgeleri içerir?", "yatay_gecis", "medium",
             ["belge", "başvuru", "gerekli"]),
    TestCase("Yatay geçişte ek kontenjan var mı?", "yatay_gecis", "medium",
             ["ek kontenjan", "var", "yok"]),
    TestCase("Yatay geçiş sonuçları ne zaman açıklanır?", "yatay_gecis", "easy",
             ["sonuç", "açıklama", "tarih"]),
    TestCase("İç yatay geçiş ile dış yatay geçiş arasındaki fark nedir?", "yatay_gecis", "medium",
             ["iç", "dış", "fark"]),
    TestCase("Yatay geçişte üst sınıfa geçiş koşulu var mı?", "yatay_gecis", "hard",
             ["üst sınıf", "koşul", "şart"]),
    TestCase("Yatay geçiş yapan öğrenci hangi sınıfa yerleşir?", "yatay_gecis", "medium",
             ["sınıf", "yerleştirme", "belirleme"]),
    TestCase("Yatay geçiş başvurusu reddedilirse itiraz edilebilir mi?", "yatay_gecis", "medium",
             ["red", "itiraz", "başvuru"]),
    
    # === LİSANSÜSTÜ (20 soru) ===
    TestCase("Lisansüstü eğitim yönetmeliğine göre bir dersten başarılı sayılma notu nedir?", "lisansustu", "easy",
             ["CB", "2.5", "başarı"]),
    TestCase("Tez savunmasına girmek için şartlar nelerdir?", "lisansustu", "hard",
             ["tez savunma", "şart", "koşul"]),
    TestCase("Yüksek lisans tez süresi kaç yıldır?", "lisansustu", "easy",
             ["yüksek lisans", "2 yıl", "süre"]),
    TestCase("Doktora programına kimler başvurabilir?", "lisansustu", "medium",
             ["doktora", "başvuru", "şart"]),
    TestCase("Lisansüstü öğrenci kayıt dondurabilir mi?", "lisansustu", "medium",
             ["kayıt dondurma", "izin", "süre"]),
    TestCase("Yüksek lisans tez jürisinde kaç kişi olur?", "lisansustu", "easy",
             ["jüri", "3", "5"]),
    TestCase("Doktora yeterlik sınavı kaç defa yapılabilir?", "lisansustu", "medium",
             ["yeterlik", "sınav", "hak"]),
    TestCase("Lisansüstü öğrencisi en fazla kaç AKTS alabilir?", "lisansustu", "medium",
             ["AKTS", "maksimum", "dönem"]),
    TestCase("Tez yazım kuralları nerede belirtiliyor?", "lisansustu", "medium",
             ["tez yazım", "kılavuz", "format"]),
    TestCase("Doktorada dil şartı nedir?", "lisansustu", "hard",
             ["dil", "ALES", "puan"]),
    TestCase("Yüksek lisans tez jürisi nasıl belirlenir?", "lisansustu", "hard",
             ["jüri", "seçim", "onay"]),
    TestCase("Lisansüstü öğrenci yurt dışına çıkabilir mi?", "lisansustu", "medium",
             ["yurt dışı", "izin", "süre"]),
    TestCase("Doktora tez önerisi ne zaman sunulur?", "lisansustu", "medium",
             ["tez önerisi", "tarih", "dönem"]),
    TestCase("Lisansüstü burs başvurusu nasıl yapılır?", "lisansustu", "medium",
             ["burs", "başvuru", "şart"]),
    TestCase("Yüksek lisans tezsiz programda kaç kredi alınır?", "lisansustu", "easy",
             ["tezsiz", "kredi", "30"]),
    TestCase("Doktora öğrencisi ders görevlisi olabilir mi?", "lisansustu", "medium",
             ["ders görevlisi", "çalışma", "izin"]),
    TestCase("Lisansüstü mezuniyet için GANO şartı var mı?", "lisansustu", "medium",
             ["GANO", "mezuniyet", "şart"]),
    TestCase("Tez danışmanı nasıl değiştirilir?", "lisansustu", "hard",
             ["danışman", "değiştirme", "prosedür"]),
    TestCase("Doktorada yayın şartı nedir?", "lisansustu", "hard",
             ["yayın", "makale", "şart"]),
    TestCase("Lisansüstü program değişikliği yapılabilir mi?", "lisansustu", "medium",
             ["program değişikliği", "geçiş", "şart"]),
    
    # === STAJ (12 soru) ===
    TestCase("İşletme fakültesi staj yönergesine göre staj süresi kaç gündür?", "staj", "easy",
             ["30 gün", "süre", "iş günü"]),
    TestCase("Staj raporu ne zaman teslim edilmeli?", "staj", "medium",
             ["rapor", "teslim", "tarih"]),
    TestCase("Staj yapabileceğim yerler nasıl onaylanır?", "staj", "medium",
             ["onay", "kurum", "SGK"]),
    TestCase("Zorunlu staj hangi dönemde yapılır?", "staj", "easy",
             ["dönem", "yaz", "staj"]),
    TestCase("Staj defteri nasıl doldurulur?", "staj", "medium",
             ["defter", "form", "doldurma"]),
    TestCase("Yurt dışında staj yapılabilir mi?", "staj", "medium",
             ["yurt dışı", "staj", "onay"]),
    TestCase("Staj komisyonu kimlerden oluşur?", "staj", "medium",
             ["komisyon", "üye", "öğretim"]),
    TestCase("Staj değerlendirmesi nasıl yapılır?", "staj", "hard",
             ["değerlendirme", "not", "başarı"]),
    TestCase("Staj sigorta işlemleri kim tarafından yapılır?", "staj", "medium",
             ["sigorta", "SGK", "işlemler"]),
    TestCase("Staj başvurusu hangi belgeleri içerir?", "staj", "medium",
             ["başvuru", "belge", "gerekli"]),
    TestCase("Kendi şirketimde staj yapabilir miyim?", "staj", "hard",
             ["kendi şirket", "akraba", "onay"]),
    TestCase("Staj yapmazsam ne olur?", "staj", "easy",
             ["zorunlu", "mezuniyet", "engel"]),
    
    # === EĞİTİM YÖNETMELİĞİ (15 soru) ===
    TestCase("İngilizce hazırlık programından muafiyet koşulları nelerdir?", "egitim", "medium",
             ["muafiyet", "TÖMER", "puan"]),
    TestCase("Bir dönemde en fazla kaç AKTS alabilirim?", "egitim", "easy",
             ["AKTS", "maksimum", "45"]),
    TestCase("FF notu GANO'ya nasıl etki eder?", "egitim", "medium",
             ["FF", "GANO", "hesap"]),
    TestCase("Ders kaydını ne zamana kadar iptal edebilirim?", "egitim", "medium",
             ["ders kaydı", "iptal", "tarih"]),
    TestCase("Ara sınıfta kalma şartları nelerdir?", "egitim", "hard",
             ["ara sınıf", "şart", "AKTS"]),
    TestCase("Mazeret sınavına kimler girebilir?", "egitim", "medium",
             ["mazeret", "sınav", "şart"]),
    TestCase("Ders tekrarı nasıl yapılır?", "egitim", "medium",
             ["tekrar", "ders", "kayıt"]),
    TestCase("Devamsızlık sınırı nedir?", "egitim", "easy",
             ["devamsızlık", "%30", "sınır"]),
    TestCase("Bütünleme sınavına kimler girer?", "egitim", "medium",
             ["bütünleme", "şart", "başarısız"]),
    TestCase("Ders programı değişikliği ne zaman yapılabilir?", "egitim", "medium",
             ["ders programı", "değişiklik", "tarih"]),
    TestCase("Öğrenci disiplin cezaları nelerdir?", "egitim", "hard",
             ["disiplin", "ceza", "türü"]),
    TestCase("Kayıt dondurmak için şartlar nelerdir?", "egitim", "medium",
             ["kayıt dondurma", "şart", "süre"]),
    TestCase("Çift kayıt yapılabilir mi?", "egitim", "easy",
             ["çift kayıt", "yasak", "mümkün"]),
    TestCase("Özel öğrenci statüsü nedir?", "egitim", "hard",
             ["özel öğrenci", "tanım", "şart"]),
    TestCase("Mezuniyet için gereken toplam AKTS kaçtır?", "egitim", "easy",
             ["mezuniyet", "AKTS", "240"]),
    
    # === FİKRİ MÜLKİYET & TTO (10 soru) ===
    TestCase("Teknoloji Transfer Ofisi'nin görevleri nelerdir?", "fikri_mulkiyet", "medium",
             ["TTO", "görev", "buluş"]),
    TestCase("Fikri ve Sınai Mülkiyet Hakları yönergesine göre buluş bildirimi nasıl yapılır?", "fikri_mulkiyet", "hard",
             ["buluş", "bildirim", "form"]),
    TestCase("Patent başvurusu kime aittir?", "fikri_mulkiyet", "medium",
             ["patent", "sahiplik", "üniversite"]),
    TestCase("Buluştan elde edilen gelir nasıl paylaşılır?", "fikri_mulkiyet", "hard",
             ["gelir", "paylaşım", "yüzde"]),
    TestCase("Araştırmacı buluş bildirimi yapmak zorunda mı?", "fikri_mulkiyet", "medium",
             ["zorunluluk", "bildirim", "buluş"]),
    TestCase("TTO hangi birimlere hizmet verir?", "fikri_mulkiyet", "medium",
             ["TTO", "hizmet", "araştırmacı"]),
    TestCase("Patent masrafları kim tarafından karşılanır?", "fikri_mulkiyet", "medium",
             ["masraf", "patent", "ödeme"]),
    TestCase("Ticari sır kapsamına neler girer?", "fikri_mulkiyet", "hard",
             ["ticari sır", "tanım", "kapsam"]),
    TestCase("Lisans anlaşması nedir?", "fikri_mulkiyet", "medium",
             ["lisans", "anlaşma", "patent"]),
    TestCase("Spin-off şirket kurulabilir mi?", "fikri_mulkiyet", "hard",
             ["spin-off", "şirket", "izin"]),
    
    # === KISMI ZAMANLI ÇALIŞMA (8 soru) ===
    TestCase("Kısmi zamanlı öğrenci çalıştırma programına kimler başvurabilir?", "kismi_zamanli", "medium",
             ["başvuru", "şart", "öğrenci"]),
    TestCase("Kısmi zamanlı çalışmada haftalık çalışma süresi kaç saattir?", "kismi_zamanli", "easy",
             ["10 saat", "haftalık", "süre"]),
    TestCase("Kısmi zamanlı çalışan öğrenciye ücret ödenir mi?", "kismi_zamanli", "easy",
             ["ücret", "ödeme", "var"]),
    TestCase("Kısmi zamanlı çalışma başvurusu ne zaman yapılır?", "kismi_zamanli", "medium",
             ["başvuru", "tarih", "dönem"]),
    TestCase("Hangi birimlerde kısmi zamanlı çalışılabilir?", "kismi_zamanli", "medium",
             ["birim", "yer", "kütüphane"]),
    TestCase("Kısmi zamanlı çalışma sözleşmesi kaç dönem geçerlidir?", "kismi_zamanli", "medium",
             ["sözleşme", "süre", "dönem"]),
    TestCase("Kısmi zamanlı çalışmadan çıkarılma sebepleri nelerdir?", "kismi_zamanli", "hard",
             ["çıkarılma", "sebep", "disiplin"]),
    TestCase("Kısmi zamanlı çalışan öğrencinin GANO şartı var mı?", "kismi_zamanli", "medium",
             ["GANO", "şart", "2.0"]),
    
    # === KAPSAM DIŞI / OUT-OF-SCOPE (10 soru) ===
    TestCase("GTÜ yemekhanesinde bugün ne yemek var?", "out_of_scope", "easy",
             [], False),  # Cevap verilememeli
    TestCase("Rektörün adı nedir?", "out_of_scope", "easy",
             [], False),
    TestCase("Merhaba, nasılsın?", "out_of_scope", "easy",
             [], False),
    TestCase("Bugün hava nasıl?", "out_of_scope", "easy",
             [], False),
    TestCase("Yakınlarda iyi bir kafe var mı?", "out_of_scope", "medium",
             [], False),
    TestCase("Python'da liste nasıl oluşturulur?", "out_of_scope", "medium",
             [], False),
    TestCase("En sevdiğin renk hangisi?", "out_of_scope", "easy",
             [], False),
    TestCase("Bugün hangi dersten sınav var?", "out_of_scope", "medium",
             [], False),
    TestCase("Kantinde çay kaç lira?", "out_of_scope", "easy",
             [], False),
    TestCase("Otobüs saatleri nedir?", "out_of_scope", "easy",
             [], False),
]


class TestRunner:
    """Test suite'ini çalıştıran ve sonuçları analiz eden sınıf"""
    
    def __init__(self, output_dir: str = None):
        self.rag_engine = RAGEngine()
        self.output_dir = output_dir or project_root
        self.results: List[TestResult] = []
        
    def run_single_test(self, test_case: TestCase) -> TestResult:
        """Tek bir test case'ini çalıştırır"""
        start_time = time.time()
        error = None
        answer = ""
        contexts = []
        
        try:
            response = self.rag_engine.answer_query_with_context(test_case.question)
            answer_gen = response.get("answer", [])
            contexts = response.get("contexts", [])
            
            # Generator'ı stringe çevir
            answer = "".join(list(answer_gen))
            
        except Exception as e:
            error = str(e)
            answer = "[HATA]"
            
        response_time = time.time() - start_time
        
        # Keyword kontrolü
        contains_keywords = self._check_keywords(answer, test_case.expected_keywords)
        has_context = len(contexts) > 0 if test_case.should_contain_source else True
        
        return TestResult(
            question=test_case.question,
            category=test_case.category,
            difficulty=test_case.difficulty,
            answer=answer.strip(),
            contexts=contexts,
            response_time=response_time,
            contains_keywords=contains_keywords,
            has_context=has_context,
            error=error
        )
    
    def _check_keywords(self, answer: str, keywords: List[str]) -> bool:
        """Cevabın önemli kelimeleri içerip içermediğini kontrol eder"""
        if not keywords:
            return True
        answer_lower = answer.lower()
        return any(kw.lower() in answer_lower for kw in keywords)
    
    def run_tests(self, max_workers: int = 5):
        """Tüm testleri paralel olarak çalıştırır"""
        print(f"\n{'='*60}")
        print(f"GTÜ QA Bot Evaluation Suite")
        print(f"Toplam Test: {len(TEST_SUITE)}")
        print(f"Paralel Worker: {max_workers}")
        print(f"{'='*60}\n")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.run_single_test, tc): tc for tc in TEST_SUITE}
            
            for future in tqdm(as_completed(futures), total=len(TEST_SUITE), desc="Testler"):
                result = future.result()
                self.results.append(result)
    
    def calculate_metrics(self) -> Dict:
        """Test sonuçlarından metrikler hesaplar"""
        total = len(self.results)
        
        # Kategori bazlı skorlar
        category_scores = {}
        difficulty_scores = {}
        
        for result in self.results:
            # Kategori
            if result.category not in category_scores:
                category_scores[result.category] = {"total": 0, "passed": 0}
            category_scores[result.category]["total"] += 1
            
            # Zorluk
            if result.difficulty not in difficulty_scores:
                difficulty_scores[result.difficulty] = {"total": 0, "passed": 0}
            difficulty_scores[result.difficulty]["total"] += 1
            
            # Başarı kontrolü (keywords ve context)
            passed = result.contains_keywords and result.has_context and not result.error
            if passed:
                category_scores[result.category]["passed"] += 1
                difficulty_scores[result.difficulty]["passed"] += 1
        
        # Response time istatistikleri
        response_times = [r.response_time for r in self.results if r.response_time]
        
        # Başarı oranı
        total_passed = sum(cs["passed"] for cs in category_scores.values())
        overall_success_rate = (total_passed / total * 100) if total > 0 else 0
        
        metrics = {
            "total_tests": total,
            "total_passed": total_passed,
            "overall_success_rate": round(overall_success_rate, 2),
            "avg_response_time": round(statistics.mean(response_times), 3) if response_times else 0,
            "median_response_time": round(statistics.median(response_times), 3) if response_times else 0,
            "max_response_time": round(max(response_times), 3) if response_times else 0,
            "category_scores": {
                cat: {
                    "passed": data["passed"],
                    "total": data["total"],
                    "success_rate": round(data["passed"] / data["total"] * 100, 2)
                }
                for cat, data in category_scores.items()
            },
            "difficulty_scores": {
                diff: {
                    "passed": data["passed"],
                    "total": data["total"],
                    "success_rate": round(data["passed"] / data["total"] * 100, 2)
                }
                for diff, data in difficulty_scores.items()
            },
            "errors": sum(1 for r in self.results if r.error)
        }
        
        return metrics
    
    def save_results(self):
        """Sonuçları ve metrikleri kaydeder"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Detaylı sonuçlar
        results_file = os.path.join(self.output_dir, f"test_results_{timestamp}.json")
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(r) for r in self.results], f, ensure_ascii=False, indent=2)
        
        # Metrikler
        metrics = self.calculate_metrics()
        metrics_file = os.path.join(self.output_dir, f"test_metrics_{timestamp}.json")
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        
        # Özet rapor (okunabilir)
        report_file = os.path.join(self.output_dir, f"test_report_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(self._generate_report(metrics))
        
        print(f"\n{'='*60}")
        print(f"✅ Test Tamamlandı!")
        print(f"📊 Sonuçlar: {results_file}")
        print(f"📈 Metrikler: {metrics_file}")
        print(f"📄 Rapor: {report_file}")
        print(f"{'='*60}\n")
        
        # Konsola özet yazdır
        print(self._generate_report(metrics))
    
    def _generate_report(self, metrics: Dict) -> str:
        """Okunabilir metin raporu oluşturur"""
        report = []
        report.append("="*60)
        report.append("GTÜ QA BOT DEĞERLENDİRME RAPORU")
        report.append("="*60)
        report.append(f"\nTarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\n📊 GENEL SONUÇLAR:")
        report.append(f"  • Toplam Test: {metrics['total_tests']}")
        report.append(f"  • Başarılı: {metrics['total_passed']}")
        report.append(f"  • Başarı Oranı: %{metrics['overall_success_rate']}")
        report.append(f"  • Hata Sayısı: {metrics['errors']}")
        
        report.append(f"\n⏱️  PERFORMANS:")
        report.append(f"  • Ortalama Yanıt Süresi: {metrics['avg_response_time']}s")
        report.append(f"  • Medyan Yanıt Süresi: {metrics['median_response_time']}s")
        report.append(f"  • Maksimum Yanıt Süresi: {metrics['max_response_time']}s")
        
        report.append(f"\n📂 KATEGORİ BAZLI BAŞARI ORANLARI:")
        for cat, data in sorted(metrics['category_scores'].items(), 
                               key=lambda x: x[1]['success_rate'], reverse=True):
            report.append(f"  • {cat:20s}: {data['passed']:2d}/{data['total']:2d} (%{data['success_rate']:5.1f})")
        
        report.append(f"\n🎯 ZORLUK SEVİYESİNE GÖRE:")
        for diff in ['easy', 'medium', 'hard']:
            if diff in metrics['difficulty_scores']:
                data = metrics['difficulty_scores'][diff]
                report.append(f"  • {diff.capitalize():10s}: {data['passed']:2d}/{data['total']:2d} (%{data['success_rate']:5.1f})")
        
        # Başarısız testleri listele
        failed_tests = [r for r in self.results 
                       if not (r.contains_keywords and r.has_context and not r.error)]
        
        if failed_tests:
            report.append(f"\n❌ BAŞARISIZ TESTLER ({len(failed_tests)} adet):")
            for i, test in enumerate(failed_tests[:10], 1):  # İlk 10'u göster
                report.append(f"\n  {i}. [{test.category}] {test.question}")
                if not test.contains_keywords:
                    report.append(f"     → Beklenen kelimeler bulunamadı")
                if not test.has_context:
                    report.append(f"     → Context bulunamadı")
                if test.error:
                    report.append(f"     → Hata: {test.error[:100]}")
            
            if len(failed_tests) > 10:
                report.append(f"\n  ... ve {len(failed_tests)-10} test daha")
        
        # Öneriler
        report.append(f"\n💡 ÖNERİLER:")
        if metrics['overall_success_rate'] < 70:
            report.append(f"  ⚠️  Başarı oranı düşük! RAG pipeline'ınızı gözden geçirin:")
            report.append(f"     - Embedding model kalitesi")
            report.append(f"     - Chunk stratejisi")
            report.append(f"     - Retrieval parametreleri (k, score threshold)")
        
        if metrics['avg_response_time'] > 3:
            report.append(f"  ⚠️  Yanıt süreleri yüksek! Optimizasyon önerileri:")
            report.append(f"     - Batch processing")
            report.append(f"     - Cache mekanizması")
            report.append(f"     - Model quantization")
        
        if metrics['errors'] > 0:
            report.append(f"  ⚠️  Hata tespit edildi! Log dosyalarını inceleyin")
        
        report.append(f"\n{'='*60}")
        
        return "\n".join(report)
    
    def export_failed_for_annotation(self):
        """Başarısız testleri manuel değerlendirme için export eder"""
        failed = [r for r in self.results 
                 if not (r.contains_keywords and r.has_context and not r.error)]
        
        if not failed:
            print("Başarısız test yok!")
            return
        
        annotation_file = os.path.join(self.output_dir, "failed_tests_for_review.json")
        
        annotation_data = []
        for r in failed:
            annotation_data.append({
                "question": r.question,
                "category": r.category,
                "answer": r.answer,
                "contexts": r.contexts,
                "review_notes": "",  # Manuel not alanı
                "is_correct": None,  # True/False/None
                "suggested_improvement": ""
            })
        
        with open(annotation_file, 'w', encoding='utf-8') as f:
            json.dump(annotation_data, f, ensure_ascii=False, indent=2)
        
        print(f"📝 Başarısız {len(failed)} test manuel inceleme için kaydedildi:")
        print(f"   {annotation_file}")


def main():
    """Ana çalıştırma fonksiyonu"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GTÜ QA Bot Evaluation Suite')
    parser.add_argument('--workers', type=int, default=5, 
                       help='Paralel çalışacak thread sayısı (default: 5)')
    parser.add_argument('--output-dir', type=str, default=None,
                       help='Sonuç dosyalarının kaydedileceği dizin')
    parser.add_argument('--export-failed', action='store_true',
                       help='Başarısız testleri manuel inceleme için export et')
    
    args = parser.parse_args()
    
    # Test runner'ı başlat
    runner = TestRunner(output_dir=args.output_dir)
    
    # Testleri çalıştır
    runner.run_tests(max_workers=args.workers)
    
    # Sonuçları kaydet
    runner.save_results()
    
    # Başarısız testleri export et
    if args.export_failed:
        runner.export_failed_for_annotation()


if __name__ == "__main__":
    main()