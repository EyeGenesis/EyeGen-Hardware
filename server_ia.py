# server_ia.py (Roda na AWS)
from flask import Flask, request, jsonify
import cv2
import numpy as np
import os

app = Flask(__name__)

# --- CONFIGURAÇÕES DA IA ---
CONFIDENCE_THRESHOLD = 0.5
NMS_THRESHOLD = 0.3
PASSO_CM = 30
ALTURA_MEDIA_HUMANO = 170

# Carrega a IA uma única vez ao iniciar o servidor
print("Carregando YOLO...")
net = cv2.dnn.readNet('yolov3.weights', 'yolov3.cfg')
with open('coco.names', 'r') as f:
    classes = [line.strip() for line in f.readlines()]
layer_names = net.getLayerNames()
if hasattr(net, 'getUnconnectedOutLayers'):
    output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers()]
else:
    output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
print("YOLO Carregado!")

def calcular_distancia(altura_pixel):
    if altura_pixel == 0: return float('inf')
    distancia_cm = (ALTURA_MEDIA_HUMANO * 480) / altura_pixel
    distancia_passos = distancia_cm / PASSO_CM
    return max(1, distancia_passos)

@app.route('/detectar', methods=['POST'])
def detectar():
    if 'image' not in request.files:
        return jsonify({"erro": "Nenhuma imagem enviada"}), 400

    # 1. Ler a imagem enviada
    file = request.files['image']
    img_bytes = file.read()
    nparr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"erro": "Imagem inválida"}), 400

    height, width = frame.shape[:2]

    # 2. Processamento YOLO
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
    net.setInput(blob)
    outputs = net.forward(output_layers)

    boxes, confidences, class_ids = [], [], []

    for output in outputs:
        for detection in output:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > CONFIDENCE_THRESHOLD:
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                x = int(center_x - w / 2)
                y = int(center_y - h / 2)
                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)

    indices = cv2.dnn.NMSBoxes(boxes, confidences, CONFIDENCE_THRESHOLD, NMS_THRESHOLD)
    
    resultados = []
    if len(indices) > 0:
        for i in indices.flatten():
            x, y, w, h = boxes[i]
            distancia = calcular_distancia(h)
            
            centro_x = x + w/2
            if centro_x < width/3: direcao = "esquerda"
            elif centro_x < 2*width/3: direcao = "centro"
            else: direcao = "direita"

            class_name = classes[class_ids[i]]
            resultados.append({
                'classe': class_name,
                'distancia': distancia,
                'direcao': direcao
            })

    # 3. Gerar a Mensagem Final (Lógica de Negócio)
    if not resultados:
        mensagem = "Caminho livre, nenhum obstáculo detectado."
    else:
        # Pega o objeto mais próximo
        resultado = min(resultados, key=lambda x: x['distancia'])
        
        # Dicionário de tradução simples
        traducao = {'person': 'pessoa', 'chair': 'cadeira', 'bottle': 'garrafa', 'laptop': 'notebook', 'cell phone': 'celular'}
        nome_pt = traducao.get(resultado['classe'], resultado['classe'])
        passos = int(resultado['distancia'])
        dir_texto = resultado['direcao']
        
        mensagem = f"{nome_pt} a {passos} passos, direção {dir_texto}."

    print(f"Resposta gerada: {mensagem}")
    return jsonify({"mensagem": mensagem})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)