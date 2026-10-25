import os
import threading
from gtts import gTTS

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

try:
    pygame.mixer.init()
except Exception:
    pass

def _executar_voz(texto):
    ficheiro_temp = f"temp_voz_{threading.get_ident()}.mp3" 
    try:
        tts = gTTS(text=texto, lang='pt-br', slow=False)
        tts.save(ficheiro_temp)
        
        pygame.mixer.music.load(ficheiro_temp)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
        pygame.mixer.music.unload()
        # Removido o pygame.mixer.quit() daqui para não fechar a placa de som
        
    except Exception as e:
        print(f"Erro no módulo de voz: {e}")
    finally:
        if os.path.exists(ficheiro_temp):
            try:
                os.remove(ficheiro_temp)
            except OSError:
                pass

def falar(texto):
    thread = threading.Thread(target=_executar_voz, args=(texto,))
    thread.start()