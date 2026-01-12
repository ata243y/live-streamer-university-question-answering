from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from qa_app.config import settings
import logging

logger = logging.getLogger(__name__)

class AvatarController:
    def __init__(self):
        self.driver = None
        try:
            options = webdriver.ChromeOptions()
            # OBS Yayını için "App Mode" ve temiz ekran ayarları
            options.add_argument(f"--app={settings.TALKING_HEAD_URL}")
            options.add_argument("--autoplay-policy=no-user-gesture-required")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            self.service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=self.service, options=options)
            self._connect()
        except Exception as e:
            logger.error(f"Avatar Controller başlatılamadı: {e}")

    def _connect(self):
        if self.driver:
            try:
                logger.info(f"Avatar sayfasına bağlanılıyor: {settings.TALKING_HEAD_URL}")
                self.driver.get(settings.TALKING_HEAD_URL)
                time.sleep(2) # Sayfanın yüklenmesi için bekle
            except Exception as e:
                logger.error(f"Avatar sayfasına bağlanılamadı: {e}")

        if self.driver:
            # Temizlik: Sayfa yüklendiğinde eski chat balonlarını temizleyelim
            try:
                # Chatbox'ın içeriğini temizle
                self.driver.execute_script("document.getElementById('chatbox').innerHTML = '';")
                logger.info("Avatar sayfası temizlendi ve yayına hazır hale getirildi.")
            except Exception as e:
                logger.warning(f"Sayfa temizlenirken hata oluştu: {e}")

    def speak(self, question: str, answer: str, audio_filename: str):
        """
        Tarayıcıya JS komutları göndererek avatarı konuşturur.
        """
        if not self.driver:
            logger.warning("Avatar driver aktif değil, komut gönderilemedi.")
            return

        try:
            # 1. Sesi çal
            logger.info(f"Avatar ses dosyası oynatılıyor: {audio_filename}")
            self.driver.execute_script(f'window.playTalkingHeadAudio("{audio_filename}")')
            
            # 2. Chat balonunu ekle
            logger.info("Avatar chat güncelleniyor...")
            # JS tarafında tırnak işaretlerini kaçırmak için basit bir temizleme
            safe_q = question.replace('"', '\\"').replace('\n', ' ')
            safe_a = answer.replace('"', '\\"').replace('\n', ' ')
            self.driver.execute_script(f'window.addQA("{safe_q}", "{safe_a}")')
            
            # 3. Ses bitene kadar bekle (Blocking)
            self.wait_for_audio_finish()
            
        except Exception as e:
            logger.error(f"Avatar kontrol hatası: {e}")
            # Bağlantı koptuysa tekrar denenebilir ama şimdilik logla yetinelim

    def wait_for_audio_finish(self):
        """
        Avatarın konuşması bitene kadar bloklar.
        """
        if not self.driver:
            return

        try:
            # Polling loop
            while True:
                is_playing = self.driver.execute_script("return window.isAvatarPlaying ? window.isAvatarPlaying() : false")
                if not is_playing:
                    break
                time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Audio wait polling error: {e}")
            
    def add_qa_text(self, question: str, answer: str):
        """
        Sadece chat balonunu ekler, ses oynatmaz.
        """
        if not self.driver:
            logger.warning("Avatar driver inactive, ADD_QA_TEXT skipped.")
            return

        try:
            logger.info("Avatar chat (sadece metin) güncelleniyor...")
            safe_q = question.replace('"', '\\"').replace('\n', ' ')
            safe_a = answer.replace('"', '\\"').replace('\n', ' ')
            self.driver.execute_script(f'window.addQA("{safe_q}", "{safe_a}")')
            
            # Give users time to read text-only responses (since no audio blocks)
            time.sleep(3)
        except Exception as e:
            logger.error(f"Avatar metin ekleme hatası: {e}")

    def close(self):
        if self.driver:
            self.driver.quit()
