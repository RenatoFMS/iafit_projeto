import os
import threading
from gtts import gTTS

# Esconde a mensagem de boas-vindas do pygame no terminal
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

def _executar_voz(texto):
    # Cria um nome de ficheiro único para evitar conflitos se a contagem for muito rápida
    ficheiro_temp = f"temp_voz_{threading.get_ident()}.mp3" 
    
    try:
        # Pede ao Google para gerar a voz
        tts = gTTS(text=texto, lang='pt-br', slow=False)
        tts.save(ficheiro_temp)
        
        # Inicializa o misturador de áudio do Pygame e reproduz
        pygame.mixer.init()
        pygame.mixer.music.load(ficheiro_temp)
        pygame.mixer.music.play()
        
        # Aguarda até que o áudio termine de tocar
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
        # Liberta o ficheiro e desliga o misturador
        pygame.mixer.music.unload()
        pygame.mixer.quit()
        
    except Exception as e:
        print(f"Erro no módulo de voz: {e}")
    finally:
        # Limpa o ficheiro MP3 temporário do disco
        if os.path.exists(ficheiro_temp):
            try:
                os.remove(ficheiro_temp)
            except OSError:
                pass

def falar(texto):
    """Aciona a voz numa thread separada."""
    thread = threading.Thread(target=_executar_voz, args=(texto,))
    thread.start()

if __name__ == "__main__":
    print("A testar a ligação aos servidores de voz do Google com Pygame...")
    falar("Olá! Sistema IAFit conectado com sucesso.")