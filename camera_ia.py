import time
import io
import threading
from flask import Flask, Response
import subprocess
import shutil

app = Flask(__name__)

# Variável global para armazenar o último frame
global_frame = None

def get_camera_command():
    """Descobre qual comando de câmera está disponível no sistema"""
    if shutil.which("rpicam-vid"):
        return "rpicam-vid"
    elif shutil.which("libcamera-vid"):
        return "libcamera-vid"
    elif shutil.which("raspivid"):
        return "raspivid"
    else:
        return None

def capture_thread():
    global global_frame
    
    cmd_name = get_camera_command()
    if not cmd_name:
        print("ERRO CRÍTICO: Nenhum comando de câmera (rpicam-vid, libcamera-vid, raspivid) encontrado!")
        return

    print(f"Iniciando captura usando: {cmd_name}")

    # Configuração do comando para streaming MJPEG
    cmd = [
        cmd_name,
        "-t", "0",              # Tempo infinito
        "--inline",             # Headers em linha
        "--width", "640",       # Resolução leve
        "--height", "480",
        "--framerate", "15",    # 15 FPS
        "--codec", "mjpeg",     # Formato MJPEG
        "-o", "-"               # Saída para stdout
    ]

    # Se for o comando antigo (raspivid), a sintaxe muda um pouco
    if cmd_name == "raspivid":
        cmd = ["raspivid", "-t", "0", "-w", "640", "-h", "480", "-fps", "15", "-cd", "MJPEG", "-o", "-"]

    # Inicia o processo
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)

    stream = io.BytesIO()
    
    while True:
        # Lê pedaços do stream
        data = process.stdout.read(1024)
        if not data:
            break
        
        stream.write(data)
        
        # Procura pelo fim de frame JPEG (0xFF 0xD9)
        stream.seek(0)
        bytes_data = stream.read()
        
        a = bytes_data.find(b'\xff\xd8') # Início
        b = bytes_data.find(b'\xff\xd9') # Fim
        
        if a != -1 and b != -1:
            # Temos um frame completo
            jpg = bytes_data[a:b+2]
            
            global_frame = jpg
            
            # Limpa o buffer mantendo o restante
            stream.seek(0)
            stream.truncate()
            stream.write(bytes_data[b+2:])

# Inicia a captura em background
t = threading.Thread(target=capture_thread)
t.daemon = True
t.start()

def gerar_frames():
    global global_frame
    while True:
        if global_frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + global_frame + b'\r\n')
        else:
            time.sleep(0.1) # Espera frame chegar

# Rota para o seu código Python e Navegador
@app.route('/video_feed')
def video_feed():
    return Response(gerar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Rota raiz para teste fácil
@app.route('/')
def index():
    return Response(gerar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Permite acesso externo
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)