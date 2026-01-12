"""
Voice Processor - RAG cevaplarını sesli okuma
TTS (Text-to-Speech) entegrasyonu
YouTube Stream Sync Desteği
"""

import os
import logging
import time
import re
from pathlib import Path
import queue
import threading
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


# TTS kütüphaneleri
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import play
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
#  STREAM SYNC CONFIGURATION
# =============================================================================
class StreamConfig:
    """YouTube/Twitch stream senkronizasyon ayarları"""
    
    ENABLED = os.getenv("STREAM_MODE", "false").lower() == "true"
    AUDIO_DELAY = float(os.getenv("STREAM_AUDIO_DELAY", "0"))
    
    @classmethod
    def log_config(cls):
        if cls.ENABLED:
            logger.info("🎬 Stream Mode: AKTIF")
            logger.info(f"   Audio Delay: {cls.AUDIO_DELAY}s")
        else:
            logger.info("🎬 Stream Mode: KAPALI (Lokal mod)")


# =============================================================================
#  VOICE PROCESSOR
# =============================================================================
class VoiceProcessor:
    """
    RAG cevaplarını sesli okuma işlemcisi
    """
    
    def __init__(self, tts_engine: str = "auto", voice_settings: dict = None, 
                 stream_mode: bool = None):
        self.tts_engine = tts_engine
        self.voice_settings = voice_settings or {}
        
        self.stream_mode = stream_mode if stream_mode is not None else StreamConfig.ENABLED
        self.audio_delay = StreamConfig.AUDIO_DELAY
        
        if self.stream_mode:
            logger.info(f"🎬 Stream Mode AKTIF - Audio Delay: {self.audio_delay}s")
        
        self.speech_queue = queue.Queue()
        self.is_speaking = False
        self.should_stop = False
        
        self.audio_dir = Path("audio_output")
        self.audio_dir.mkdir(exist_ok=True)
        
        self.elevenlabs_client = None
        self.pyttsx3_engine = None
        
        self._initialize_engine()
        
        self.worker = None
        
        self.stats = {
            "total_generated": 0,
            "total_played": 0,
            "total_errors": 0
        }
    
    def set_stream_delay(self, audio_delay: float = None):
        if audio_delay is not None:
            self.audio_delay = audio_delay
            logger.info(f"🎬 Audio delay güncellendi: {audio_delay}s")
    
    def _initialize_engine(self):
        if self.tts_engine == "auto":
            if ELEVENLABS_AVAILABLE and os.getenv("ELEVENLABS_API_KEY"):
                self.tts_engine = "elevenlabs"
                logger.info("TTS Motor: ElevenLabs (En kaliteli)")
            elif PYTTSX3_AVAILABLE:
                self.tts_engine = "pyttsx3"
                logger.info("TTS Motor: pyttsx3 (Offline)")
            elif GTTS_AVAILABLE:
                self.tts_engine = "gtts"
                logger.info("TTS Motor: gTTS (Google)")
            else:
                raise RuntimeError("Hiçbir TTS motoru yüklü değil!")
        
        if self.tts_engine == "elevenlabs":
            self._init_elevenlabs()
        elif self.tts_engine == "pyttsx3":
            self._init_pyttsx3()
        elif self.tts_engine == "gtts":
            logger.info("gTTS motoru hazır")
        else:
            raise ValueError(f"Bilinmeyen TTS motoru: {self.tts_engine}")
    
    def _init_elevenlabs(self):
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY ortam değişkeni gerekli!")
        self.elevenlabs_client = ElevenLabs(api_key=api_key)
        logger.info("ElevenLabs client başlatıldı")
    
    def _init_pyttsx3(self):
        self.pyttsx3_engine = pyttsx3.init()
        rate = self.voice_settings.get("rate", 150)
        volume = self.voice_settings.get("volume", 1.0)
        self.pyttsx3_engine.setProperty('rate', rate)
        self.pyttsx3_engine.setProperty('volume', volume)
        
        voices = self.pyttsx3_engine.getProperty('voices')
        for voice in voices:
            if 'turkish' in voice.name.lower() or 'tr' in voice.id.lower():
                self.pyttsx3_engine.setProperty('voice', voice.id)
                logger.info(f"Türkçe ses bulundu: {voice.name}")
                break
        
        logger.info("pyttsx3 motoru başlatıldı")
    
    def generate_audio(self, text: str, author: str = "Kullanıcı") -> Path:
        try:
            if not text or not text.strip():
                logger.warning("Boş metin, ses üretilmedi")
                return None
            
            clean_text = self._clean_text_for_tts(text)
            
            if not clean_text:
                logger.warning("Temizleme sonrası metin boş")
                return None
            
            logger.info(f"Ses üretimi başlatıldı. Karakter: {len(clean_text)}")
            print(f"\n{'='*50}")
            print(f"🔊 OKUNACAK METİN:")
            print(f"{'='*50}")
            print(clean_text)
            print(f"{'='*50}\n")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_file = self.audio_dir / f"response_{timestamp}.mp3"
            
            if self.tts_engine == "elevenlabs":
                audio_file = self._generate_elevenlabs(clean_text, audio_file)
            elif self.tts_engine == "gtts":
                audio_file = self._generate_gtts(clean_text, audio_file)
            elif self.tts_engine == "pyttsx3":
                audio_file = None
            
            self.speech_queue.put((clean_text, audio_file))
            self.stats["total_generated"] += 1
            
            logger.info(f"Ses kuyruğa eklendi (Kuyruk: {self.speech_queue.qsize()})")
            
            return audio_file
            
        except Exception as e:
            logger.error(f"Ses üretme hatası: {e}")
            self.stats["total_errors"] += 1
            return None
    
    def _clean_text_for_tts(self, text: str) -> str:
        if not text:
            return ""
        
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'__([^_]+?)__', r'\1', text)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _generate_elevenlabs(self, text: str, output_file: Path) -> Path:
        try:
            voice_id = self.voice_settings.get("voice_id", "pNInz6obpgDQGcFmaJgB")
            model = self.voice_settings.get("model", "eleven_multilingual_v2")
            
            audio_generator = self.elevenlabs_client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=model
            )
            
            audio_bytes = b"".join(audio_generator)
            
            with open(output_file, 'wb') as f:
                f.write(audio_bytes)
            
            logger.info(f"ElevenLabs ses kaydedildi: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"ElevenLabs hatası: {e}")
            return None
    
    def _generate_gtts(self, text: str, output_file: Path) -> Path:
        try:
            tts = gTTS(text=text, lang='tr', slow=False)
            tts.save(str(output_file))
            logger.info(f"gTTS ses kaydedildi: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"gTTS hatası: {e}")
            return None
    
    def _play_audio_with_sync(self, audio_file: Path, text: str):
        try:
            import subprocess
            import platform
            
            logger.info(f"🔊 Ses oynatılıyor: {audio_file}")
            
            if self.stream_mode:
                logger.info(f"🎬 Stream mode aktif - Sync başlatılıyor...")
            
            # STREAM SYNC DELAY
            if self.stream_mode and self.audio_delay > 0:
                logger.info(f"⏳ Stream sync: {self.audio_delay}s bekleniyor...")
                time.sleep(self.audio_delay)
                logger.info("✅ Stream sync bekleme tamamlandı, ses başlıyor...")
            else:
                time.sleep(0.15)
            
            # SESİ OYNAT
            system = platform.system()
            
            if system == "Darwin":
                process = subprocess.Popen(
                    ["afplay", str(audio_file)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                process.wait()
                
            elif system == "Linux":
                try:
                    subprocess.run(["mpg123", "-q", str(audio_file)], check=True)
                except FileNotFoundError:
                    try:
                        subprocess.run(["aplay", str(audio_file)], check=True)
                    except FileNotFoundError:
                        self._play_with_pygame(audio_file)
            elif system == "Windows":
                try:
                    subprocess.run(
                        ["powershell", "-c", 
                         f'(New-Object Media.SoundPlayer "{audio_file}").PlaySync()'],
                        check=True
                    )
                except Exception:
                    self._play_with_pygame(audio_file)
            else:
                self._play_with_pygame(audio_file)
            
            self.stats["total_played"] += 1
            logger.info(f"✅ Ses oynatma tamamlandı")
            
        except Exception as e:
            logger.error(f"Ses çalma hatası: {e}")
            self.stats["total_errors"] += 1
    
    def _play_with_pygame(self, audio_file: Path):
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(str(audio_file))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.quit()
        except ImportError:
            logger.error("pygame yüklü değil: pip install pygame")
        except Exception as e:
            logger.error(f"pygame hatası: {e}")
    
    def _play_pyttsx3(self, text: str):
        try:
            if self.stream_mode and self.audio_delay > 0:
                logger.info(f"⏳ Stream sync: {self.audio_delay}s bekleniyor...")
                time.sleep(self.audio_delay)
            else:
                time.sleep(0.15)
            
            self.pyttsx3_engine.say(text)
            self.pyttsx3_engine.runAndWait()
            
            self.stats["total_played"] += 1
            
        except Exception as e:
            logger.error(f"pyttsx3 oynatma hatası: {e}")
            self.stats["total_errors"] += 1
    
    def _speech_worker(self):
        """Kuyruktan sesleri sırayla oynat"""
        logger.info("🎙️ Ses worker başlatıldı")
        
        while not self.should_stop:
            try:
                # Kuyruktan al
                try:
                    item = self.speech_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # Tuple parse
                if isinstance(item, tuple):
                    text = item[0] if len(item) > 0 else ""
                    audio_file = item[1] if len(item) > 1 else None
                else:
                    text = str(item)
                    audio_file = None
                
                self.is_speaking = True
                logger.info(f"▶ Sesli okuma başladı: {text[:50]}...")
                
                # Sesi oynat
                if self.tts_engine == "pyttsx3":
                    self._play_pyttsx3(text)
                elif audio_file and Path(audio_file).exists():
                    self._play_audio_with_sync(audio_file, text)
                    
                    if self.voice_settings.get("delete_after_play", True):
                        try:
                            Path(audio_file).unlink()
                        except Exception:
                            pass
                else:
                    logger.warning(f"Ses dosyası bulunamadı: {audio_file}")
                
                self.is_speaking = False
                self.speech_queue.task_done()
                logger.info("✓ Sesli okuma tamamlandı")
                
            except Exception as e:
                logger.error(f"Speech worker hatası: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.is_speaking = False
                self.stats["total_errors"] += 1
                
                try:
                    self.speech_queue.task_done()
                except ValueError:
                    pass
        
        logger.info("⏹ Ses worker durduruldu")
    
    def start(self):
        if self.worker and self.worker.is_alive():
            logger.warning("Ses worker zaten çalışıyor")
            return
        
        self.should_stop = False
        self.worker = threading.Thread(target=self._speech_worker, daemon=True)
        self.worker.start()
        logger.info("🚀 Ses işleyici başlatıldı")
    
    def stop(self, wait: bool = True, timeout: float = 5.0):
        logger.info("⏹️ Ses işleyici durduruluyor...")
        
        if wait and not self.speech_queue.empty():
            logger.info(f"Kuyrukta {self.speech_queue.qsize()} ses var, bekleniyor...")
            try:
                self.speech_queue.join()
            except Exception:
                pass
        
        self.should_stop = True
        
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=timeout)
        
        logger.info("✓ Ses işleyici durduruldu")
    
    def clear_queue(self):
        count = 0
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
                count += 1
            except queue.Empty:
                break
        logger.info(f"🗑 Kuyruk temizlendi ({count} ses)")
    
    def get_status(self) -> dict:
        return {
            "engine": self.tts_engine,
            "is_speaking": self.is_speaking,
            "queue_size": self.speech_queue.qsize(),
            "worker_alive": self.worker.is_alive() if self.worker else False,
            "stream_mode": self.stream_mode,
            "audio_delay": self.audio_delay,
            "stats": self.stats.copy(),
            "available_engines": {
                "elevenlabs": ELEVENLABS_AVAILABLE,
                "pyttsx3": PYTTSX3_AVAILABLE,
                "gtts": GTTS_AVAILABLE
            }
        }
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


# =============================================================================
#  TEST
# =============================================================================
def test_voice_processor():
    print("=" * 60)
    print("🎙️ Ses İşleyici Test")
    print("=" * 60)
    
    print("\n📦 Kullanılabilir TTS Motorları:")
    print(f"  ElevenLabs: {'✓' if ELEVENLABS_AVAILABLE else '✗'}")
    print(f"  pyttsx3:    {'✓' if PYTTSX3_AVAILABLE else '✗'}")
    print(f"  gTTS:       {'✓' if GTTS_AVAILABLE else '✗'}")
    
    print(f"\n🎬 Stream Mode: {'AKTIF' if StreamConfig.ENABLED else 'KAPALI'}")
    
    try:
        with VoiceProcessor(tts_engine="auto") as processor:
            test_cases = [
                {"text": "Merhaba! Bu bir test mesajıdır."},
            ]
            
            print("\n🎵 Test sesleri üretiliyor...")
            for i, case in enumerate(test_cases, 1):
                processor.generate_audio(
                    text=case["text"],
                    author="Test"
                )
            
            print(f"\n🔊 Sesler oynatılıyor...")
            processor.speech_queue.join()
            
            print("\n✅ Test tamamlandı!")
            print(f"📊 İstatistikler: {processor.stats}")
        
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "stream":
            with VoiceProcessor(tts_engine="auto", stream_mode=True) as processor:
                processor.set_stream_delay(audio_delay=3.55)
                processor.generate_audio("Stream sync testi.")
                processor.speech_queue.join()
    else:
        test_voice_processor()