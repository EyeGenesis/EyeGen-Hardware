import cv2
import numpy as np
import speech_recognition as sr
import threading
import os
import time
import queue
import requests
from collections import deque
from gtts import gTTS
import pygame
import io
from ultralytics import YOLO

# --- CONFIGURAÇÕES DE REDE ---
AWS_IP = "54.233.xx.xx"  # Seu IP da AWS
URL_API = f"http://{AWS_IP}:5000/detectar"

RASP_IP = "192.168.x.xx" # Seu IP da Raspberry
URL_CAMERA = f"http://{RASP_IP}:5000/video_feed"

# --- CONFIGURAÇÕES LOCAL YOLO ---
CONFIDENCE_THRESHOLD = 0.5
NMS_THRESHOLD = 0.3
PASSO_CM = 30
ALTURA_MEDIA_HUMANO = 170

# Filas para comunicação entre threads
fila_comandos = queue.Queue()
fila_audio = queue.Queue()

pygame.mixer.init()

class SistemaHibrido:
    def __init__(self):
        self.rodando = True
        self.sistema_ativado = False
        self.modo_nuvem = False
        self.fila_frames = deque(maxlen=10)
        self.components = self.inicializar_componentes()
        self.ultimo_comando_time = 0
        self.cooldown_comando = 2
        self.audio_lock = threading.Lock()
        
    def inicializar_componentes(self):
        components = {}
        
        # 1. Carregar YOLO Local
        print("📥 Carregando YOLO Local...")
        try:
            model = YOLO("yolov8s.pt") 
            components['model'] = model
            print("✅ YOLOv8 Local carregado")
        except Exception as e:
            print(f"❌ Erro YOLO Local: {e}")
            components['model'] = None
        
        # 2. Inicializar microfone
        try:
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 3000
            
            microphone = sr.Microphone()
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
            components['recognizer'] = recognizer
            components['microphone'] = microphone
            print("✅ Microfone pronto")
        except Exception as e:
            print(f"❌ Erro Microfone: {e}")
        
        # 3. Inicializar Câmera
        try:
            print(f"📡 Conectando na câmera: {URL_CAMERA}")
            cap = cv2.VideoCapture(URL_CAMERA)
            if not cap.isOpened():
                print("❌ Erro ao conectar na Raspberry")
                components['camera'] = None
            else:
                components['camera'] = cap
                print("✅ Câmera Conectada")
        except Exception as e:
            print(f"❌ Erro Câmera: {e}")
            components['camera'] = None
        
        return components

    def calcular_distancia(self, altura_pixel):
        if altura_pixel == 0: return float('inf')
        distancia_cm = (ALTURA_MEDIA_HUMANO * 480) / altura_pixel
        return max(1, distancia_cm / PASSO_CM)

    def obter_instrucao_desvio(self, direcao):
        """Retorna a instrução de navegação baseada na posição do objeto"""
        if direcao == "esquerda":
            return "Vire levemente à direita."
        elif direcao == "direita":
            return "Vire levemente à esquerda."
        elif direcao == "centro" or direcao == "frente":
            return "Desvie para a direita ou esquerda."
        return ""

    # --- LÓGICA LOCAL (YOLOv8 no PC) ---
    def processar_frame_local(self, frame):
        
        
        height, width = frame.shape[:2]
        results = self.components['model'](frame, verbose=False, conf=0.5)
        
        # O YOLOv8 pode detectar várias coisas, pegamos o primeiro resultado
        result = results[0]
        
        if len(result.boxes) > 0:
            # Encontrar o objeto mais próximo (maior área da caixa)
            # Box format: [x1, y1, x2, y2]
            melhor_box = None
            maior_altura = 0
            
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                h = y2 - y1
                
                if h > maior_altura:
                    maior_altura = h
                    melhor_box = box
            
            # Extrair dados do melhor objeto
            x1, y1, x2, y2 = melhor_box.xyxy[0].cpu().numpy()
            cls = int(melhor_box.cls[0])
            class_name = result.names[cls]
            
            # Cálculos de navegação
            w = x2 - x1
            h = y2 - y1
            center_x = x1 + (w / 2)
            
            distancia = self.calcular_distancia(h)
            
            if center_x < width/3: direcao = "esquerda"; txt_pos = "à sua esquerda"
            elif center_x < 2*width/3: direcao = "centro"; txt_pos = "na sua frente"
            else: direcao = "direita"; txt_pos = "à sua direita"
            
            instrucao = self.obter_instrucao_desvio(direcao)
            
            # Tradução (Você pode expandir essa lista)
            traducao = {
                'person': 'pessoa', 'chair': 'cadeira', 'bottle': 'garrafa', 
                'laptop': 'notebook', 'cell phone': 'celular', 'cup': 'copo',
                'tv': 'televisão', 'mouse': 'mouse', 'keyboard': 'teclado',
                'book': 'livro', 'table': 'mesa', 'door': 'porta'
            }
            nome_pt = traducao.get(class_name, class_name)
            
            return f"{nome_pt} a {int(distancia)} passos, {txt_pos}. {instrucao}"
            
        return "Caminho livre."
        

    # --- LÓGICA NUVEM (AWS) ---
    def consultar_aws(self, frame):
        print("☁️ Enviando para AWS...")
        _, img_encoded = cv2.imencode('.jpg', frame)
        arquivo = {'image': img_encoded.tobytes()}
        
        try:
            response = requests.post(URL_API, files=arquivo, timeout=60)
            if response.status_code == 200:
                dados = response.json()
                msg_base = dados.get("mensagem", "Erro na resposta")
                
                # AWS já retorna "direção direita/esquerda/centro" no texto
                # Vamos adicionar a instrução de desvio extraindo a direção do texto
                instrucao_extra = ""
                if "esquerda" in msg_base:
                    instrucao_extra = " Vire à direita."
                elif "direita" in msg_base:
                    instrucao_extra = " Vire à esquerda."
                elif "centro" in msg_base or "frente" in msg_base:
                    instrucao_extra = " Desvie para os lados."
                
                # Evita duplicar se a AWS já mandar a instrução
                if "Vire" not in msg_base and "Desvie" not in msg_base:
                    return f"{msg_base} {instrucao_extra}"
                else:
                    return msg_base
            else:
                return f"Erro nuvem: {response.status_code}"
        except Exception:
            return "Erro de conexão com a nuvem."

    # --- ÁUDIO ---
    def reproduzir_arquivo_audio(self, caminho_arquivo):
        with self.audio_lock:
            try:
                if os.path.exists(caminho_arquivo):
                    pygame.mixer.music.load(caminho_arquivo)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        pygame.time.Clock().tick(10)
                    return True
                return False
            except:
                return False

    def falar_com_gtts(self, texto):
        with self.audio_lock:
            try:
                print(f"🔊 Falando: {texto}")
                tts = gTTS(text=texto, lang='pt', slow=False)
                audio_buffer = io.BytesIO()
                tts.write_to_fp(audio_buffer)
                audio_buffer.seek(0)
                pygame.mixer.music.load(audio_buffer, 'mp3')
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
            except Exception as e:
                print(f"Erro gTTS: {e}")

    def processar_mensagem_audio(self, mensagem):
        if isinstance(mensagem, str) and mensagem.startswith("FILE:"):
            caminho_arquivo = mensagem[5:]
            if not self.reproduzir_arquivo_audio(caminho_arquivo):
                self.falar_com_gtts(f"Arquivo {caminho_arquivo} não encontrado")
        else:
            self.falar_com_gtts(mensagem)

    def worker_audio(self):
        while self.rodando:
            try:
                msg = fila_audio.get(timeout=0.5)
                if msg == "SAIR": break
                self.processar_mensagem_audio(msg)
            except queue.Empty: continue

    # --- COMANDOS E LOOP PRINCIPAL ---
    def worker_reconhecimento(self):
        if not self.components['recognizer']: return
        print("🎤 Ouvindo...")

        self.sistema_ativado = True
        fila_audio.put("FILE:audios/standby.mp3") if os.path.exists("audios/standby.mp3") else fila_audio.put("Sistema Iniciado")
        
        while self.rodando:
            try:
                with self.components['microphone'] as source:
                    audio = self.components['recognizer'].listen(source, timeout=3, phrase_time_limit=5)

                comando = self.components['recognizer'].recognize_google(audio, language='pt-BR').lower()
                print(f"🗣️ Comando: {comando}")
                
                agora = time.time()
                if agora - self.ultimo_comando_time < self.cooldown_comando: continue
                self.ultimo_comando_time = agora

                
                if "ativar" in comando or "iniciar" in comando:
                    self.sistema_ativado = True
                    fila_audio.put("FILE:audios/inicio.mp3") if os.path.exists("audios/inicio.mp3") else fila_audio.put("Sistema Iniciado")
                
                elif "sair" in comando:
                    self.sistema_ativado = False
                    fila_audio.put("FILE:audios/sair.mp3") if os.path.exists("audios/sair.mp3") else fila_audio.put("Sistema encerrando")
                    time.sleep(3)      
                    fila_comandos.put("SAIR")
                    break

                elif "modo nuvem" in comando or "modo aws" in comando:
                    self.modo_nuvem = True
                    fila_audio.put("Ativando modo nuvem")
                    print("☁️ MODO NUVEM")

                elif "modo local" in comando or "modo pc" in comando:
                    self.modo_nuvem = False
                    fila_audio.put("Ativando modo local")
                    print("💻 MODO LOCAL")

                elif self.sistema_ativado:
                    frases_deteccao = ["frente", "o que", "oque", "vejo", "olhe"]
                    if any(x in comando for x in frases_deteccao):
                        fila_comandos.put("DETECTAR")

            except (sr.WaitTimeoutError, sr.UnknownValueError): pass
            except Exception as e: print(f"Erro voz: {e}")

    def processar_solicitacao(self):
        if not self.fila_frames:
            fila_audio.put("Câmera sem sinal")
            return

        frame = self.fila_frames[-1]
        
        if self.modo_nuvem:
            fila_audio.put("Consultando nuvem...")
            msg = self.consultar_aws(frame)
            fila_audio.put(msg)
        else:
            msg = self.processar_frame_local(frame)
            fila_audio.put(msg)

    def executar(self):
        t_audio = threading.Thread(target=self.worker_audio, daemon=True)
        t_recon = threading.Thread(target=self.worker_reconhecimento, daemon=True)
        t_audio.start()
        t_recon.start()
        
        print("🚀 SISTEMA HÍBRIDO RODANDO")
        
        try:
            while self.rodando:
                if self.components['camera']:
                    ret, frame = self.components['camera'].read()
                    if ret:
                        self.fila_frames.append(frame.copy())
                        
                        modo_str = "AWS (NUVEM)" if self.modo_nuvem else "LOCAL (PC)"
                        cv2.putText(frame, f"MODO: {modo_str}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                        cv2.imshow('EyeGen Client', frame)

                try:
                    cmd = fila_comandos.get(timeout=0.01)
                    if cmd == "DETECTAR": self.processar_solicitacao()
                    elif cmd == "SAIR": break
                except queue.Empty: pass

                if cv2.waitKey(1) == ord('q'): break

        except KeyboardInterrupt: pass
        finally:
            self.rodando = False
            cv2.destroyAllWindows()
            if self.components['camera']: self.components['camera'].release()

if __name__ == "__main__":
    app = SistemaHibrido()
    app.executar()