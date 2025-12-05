# 👁️ EyeGlass - Assistente Visual Híbrido (MVP)


## Tecnologia Assistiva Inteligente com Arquitetura Híbrida (Local + Cloud)

O **EyeGlass** é um par de óculos de tecnologia assistiva projetado para oferecer autonomia a pessoas com deficiência visual. Ele captura o ambiente em tempo real, identifica obstáculos e fornece feedback sonoro com instruções de navegação (ex: _"Mesa a 3 passos, desvie para a direita"_).

Este MVP demonstra uma arquitetura robusta que alterna entre processamento local de alta precisão e processamento em nuvem para garantir disponibilidade.

---

## 📘 Sumário

- [Arquitetura do Sistema](#-Arquitetura-do-Sistema)
- [Configuração e Instalação](#-Configuração-e-Instalação)
- [Como Usar](#-Como-Usar)
- [Escalabildiade e futuro](#-Escalabilidade-e-Futuro)
- [Estrutura do Repositório](#-Estrutura-do-Repositório)


---
## 🚀 Arquitetura do Sistema

O sistema opera em três camadas interconectadas:

### 1. 📷 Os Olhos (Edge Device)

- **Hardware:** Raspberry Pi Zero 2 W + Câmera Module v2.
    
- **Função:** Captura de vídeo e transmissão sem fio de baixa latência.
    
- **Tecnologia:**
    
    - **Captura:** `libcamera` / `rpicam-vid` (para suporte a novos OS Raspberry).
        
    - **Streaming:** Servidor Flask transmitindo MJPEG via HTTP.
        
    - **Performance:** Otimizado para 640x480 a 15 FPS para economizar bateria e banda.

### 2. 🧠 O Cérebro Central (Cliente/PC)

- **Hardware:** Computador Local (Simulando o processamento de um Smartphone/Óculos Inteligente).
    
- **Função:** Orquestração, processamento de áudio e inteligência híbrida.
    
- **Tecnologia:**
    
    - **Linguagem:** Python 3.12+.
        
    - **IA Local:** **YOLOv8 Small** (Ultralytics) para detecção de alta precisão offline.
        
    - **Interface de Voz:** `SpeechRecognition` para comandos e `gTTS` para feedback falado.
        
    - **Modo Híbrido:** Decide se processa a imagem localmente ou envia para a AWS com base no comando do usuário.

### 3. ☁️ A Inteligência em Nuvem (AWS Cloud)

- **Infraestrutura:** Amazon EC2 (Instância Ubuntu).
    
- **Função:** API de inferência remota para contingência e processamento leve.
    
- **Tecnologia:**
    
    - **Servidor:** Flask API (Python).
        
    - **IA Nuvem:** **YOLOv4-tiny* ou YOLOv3* (Darknet) otimizado para CPU, rodando em ambiente com Swap Memory.
        
    - **Comunicação:** Recebe frames via HTTP POST, processa e retorna JSON com coordenadas e classes.
        

---

## 🛠️ Configuração e Instalação

### Pré-requisitos

- **Python 3.10+** instalado.
    
- **Raspberry Pi** configurada na mesma rede Wi-Fi.
    
- **Conta AWS** (opcional para o modo nuvem).
    

### 📦 1. Configurando a Raspberry Pi (Câmera)

No terminal da Raspberry Pi:

- Crie um VENV

```
python -m venv venv
source venv/bin/activate
```


```

# Instalar dependências
sudo apt update && sudo apt install python3-flask rpicam-apps

# Clonar/copiar o script da câmera (camera_pi.py)

# Rodar o servidor de streaming
python3 camera_pi.py
```

_A câmera estará disponível em: `http://[IP_DA_RASPBERRY]:5000/video_feed`_

### ☁️ 2. Configurando o Servidor AWS

Para rodar o YOLO em instâncias gratuitas (t2.micro com 1GB RAM), é **obrigatório** configurar memória virtual (Swap), caso contrário o processo será morto ("Killed") por falta de memória.

**Passo a passo na AWS:**

1. **Configuração Inicial:**
    
    - Crie uma instância EC2 (Ubuntu 22.04 ou superior).
        
    - Libere a porta **5000** no Security Group.
        
    - Conecte via SSH (`ssh -i chave.pem ubuntu@IP_PUBLICO`).
        
2. **⚡ Criar Swap Memory (Crucial para não travar):** Rode estes comandos um por um no terminal da AWS:

    ```
    # Cria um arquivo de 2GB para memória virtual
    sudo fallocate -l 2G /swapfile
    
    # Ajusta permissões de segurança
    sudo chmod 600 /swapfile
    
    # Formata como swap
    sudo mkswap /swapfile
    
    # Ativa o swap
    sudo swapon /swapfile
    
    # Verifica se funcionou (deve aparecer 2.0G na coluna Swap)
    free -h
    ```

3. **Crie um VENV**

	```
	python -m venv venv
	source venv/bin/activate
	```

4. **Instalar Dependências:**

    ```
    sudo apt update && sudo apt install libgl1
    pip install flask opencv-python-headless numpy
    ```

5. **Baixar a IA (YOLO):**

	- Para t2.micro recomendamos:
		- yolov4-tiny para respostas mais rapidas
		- yolov3 para respostas mais precisas
	- codigo abaixo segue um exemplo com yolov3

    ```
    wget https://pjreddie.com/media/files/yolov3.weights
    wget https://raw.githubusercontent.com/pjreddie/darknet/master/cfg/yolov3.cfg
    ```

6. **Iniciar o Servidor:**

    ```
    python3 server_ia.py
    ```

---
### 💻 3. Configurando o Cliente Local (PC)

No seu computador:

1. Clone este repositório e crie um venv para projeto em sua máquina.

```
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
```

2. Instale as dependências listadas:

    ```
    pip install -r requirements.txt
    ```

3. Edite o arquivo `eyeglass.py` com os IPs corretos:

    Python

    ```
    AWS_IP = "54.233.XX.XX"  # IP Público da sua EC2
    RASP_IP = "192.168.0.XX" # IP Local da Raspberry
    ```

4. Execute o sistema:

    ```
    python eyeglass.py
    ```
    

---

## 🎮 Como Usar

O sistema é controlado totalmente por voz para acessibilidade.

1. **Iniciar:** Ao abrir, o sistema toca um áudio de boas-vindas.
    
2. **Ativar:** Diga **"Ativar"** ou **"Iniciar"** para acordar o assistente.
    
3. **Comandos de Visão:**
    
    - 🗣️ _"O que tem na minha frente?"_
        
    - 🗣️ _"O que eu vejo?"_
        
    - _O sistema captura a imagem, analisa e responde: "Cadeira a 2 passos, à sua esquerda. Vire levemente à direita."_
        
4. **Troca de Modos (Híbrido):**
    
    - 🗣️ _"Modo Nuvem"_ / _"Modo AWS"_ -> Passa a processar tudo na EC2 (ideal para economizar bateria local).
        
    - 🗣️ _"Modo Local"_ / _"Modo PC"_ -> Volta a usar o YOLOv8 no computador (maior precisão).
        
5. **Encerrar:** Diga **"Sair"** ou **"Desligar"**.
    

---

## 📈 Escalabilidade e Futuro

Este MVP prova o conceito. Para transformar o EyeGlass em um produto comercial escalável para milhares de usuários, a arquitetura evoluirá para:

### 1. Alta Disponibilidade (AWS)

- **Problema Atual:** Uma única EC2 pode cair ou ficar lenta com muitos usuários.
    
- **Solução Futura:**
    
    - **Docker & ECS:** Empacotar o código da IA em containers Docker.
        
    - **Auto Scaling:** Usar AWS ECS (Fargate) para subir novos containers automaticamente quando a demanda aumentar.
        
    - **Load Balancer (ALB):** Distribuir as requisições dos óculos entre vários servidores.

### 3. App Mobile

- Substituir o código Python do PC por um **Aplicativo Android/iOS** que se comunica via Bluetooth/wifi com os óculos (Raspberry) e gerencia a conexão com a nuvem AWS.
    

---

## 📂 Estrutura do Repositório


```
/
├── eyeglass.py               # [PC] Código Principal (Cliente/Cérebro Híbrido)
├── server_ia.py              # [AWS] API Server (Flask + YOLOv3)
├── camera_pi.py              # [Raspberry] Streamer de Vídeo
├── requirements.txt          # Dependências do projeto
├── README.md                 # Documentação
└── audios                 	  # Pasta com audios personalizados para voz
```

---

## 🤝 Autor

Desenvolvido por **EYEGEN**. Projeto de MVP focado em acessibilidade, visão computacional e arquitetura de nuvem.
