# Vinheria Agnaldo — Monitoramento Ambiental com FIWARE
 
Sistema de monitoramento ambiental para conservação de vinhos, utilizando ESP32 (simulado no Wokwi), stack FIWARE e dashboard Python. O sistema detecta anomalias em tempo real e aciona alertas visuais e sonoros no hardware.
 
**Simulação Wokwi:** [https://wokwi.com/projects/461036532566146049](https://wokwi.com/projects/461036532566146049)
 
---
 
## Equipe
 
| Nome | RM |
|---|---|
| Felipe Menezes | 566607  |
| Gabriel Ardito | 568318  |
| João Sarracine | 567407 |
| João Gonzales | 568166 |
 
---
 
## Arquitetura
 
```
┌─────────────────────────────────────────────────────────────────┐
│                        WOKWI (Simulador)                        │
│                                                                 │
│  DHT22 ──► Temperatura / Umidade                                │
│  LDR   ──► Luminosidade                                         │
│  RGB LED ◄─ Comandos de anomalia                                │
│  Buzzer  ◄─ Alertas sonoros                                     │
│                    ESP32                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ MQTT (porta 1883)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FIWARE Stack (Docker)                       │
│                                                                 │
│  Mosquitto (1883) ──► IoT Agent UL ──► Orion Context Broker    │
│                                               │                 │
│                                               ▼                 │
│                                        STH-Comet (8666)        │
│                                        MongoDB (histórico)      │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP (porta 8666)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Dashboard Python (Flask)                     │
│                                                                 │
│  - Consulta STH-Comet (lastN=20)                                │
│  - Serve dashboard web na porta 5000                            │
│  - Avalia thresholds de anomalia                                │
│  - Publica comandos MQTT de volta ao ESP32                      │
└─────────────────────────────────────────────────────────────────┘
```
 
---
 
## Componentes
 
| Componente | Função | Porta |
|---|---|---|
| ESP32 (Wokwi) | Lê sensores e executa comandos | — |
| Mosquitto | Broker MQTT | 1883 |
| IoT Agent UL | Traduz MQTT → NGSI | 4041 |
| Orion Context Broker | Gerencia entidades e subscrições | 1026 |
| STH-Comet | Armazena histórico de séries temporais | 8666 |
| MongoDB | Banco de dados do Orion e STH | 27017 |
| Dashboard Python | Visualização e lógica de alertas | 5000 |
 
---
 
## Tópicos MQTT
 
| Tópico | Direção | Conteúdo |
|---|---|---|
| `/TEF/sensor001/attrs/l` | ESP32 → Broker | Luminosidade (0–100%) |
| `/TEF/sensor001/attrs/t` | ESP32 → Broker | Temperatura (°C) |
| `/TEF/sensor001/attrs/h` | ESP32 → Broker | Umidade (%) |
| `/TEF/sensor001/cmd` | Broker → ESP32 | Comandos de anomalia |
 
---
 
## Thresholds de Conservação de Vinho
 
Baseados nas condições ideais para armazenamento de vinhos finos.
 
| Parâmetro | Mínimo | Máximo | Consequência fora do range |
|---|---|---|---|
| Temperatura | 10 °C | 15 °C | Abaixo: amargueia o vinho. Acima: acelera oxidação e degrada taninos |
| Umidade | 50% | 70% | Abaixo: resseca rolhas (entrada de ar). Acima: proliferação de mofo |
| Luminosidade | 0% | 30% | Acima: luz UV degrada taninos e compostos aromáticos |
 
---
 
## Mapeamento de Anomalias
 
Cada anomalia gera uma resposta visual e sonora distinta no ESP32.
 
| Anomalia | Comando MQTT | Cor do LED | Tom (Hz) | Padrão de Bipes |
|---|---|---|---|---|
| Temperatura alta | `temp_alta` | Vermelho | 1500 Hz | 3 bipes curtos |
| Temperatura baixa | `temp_baixa` | Azul | 800 Hz | 3 bipes curtos |
| Umidade alta | `umidade_alta` | Ciano | 1200 Hz | 2 bipes curtos |
| Umidade baixa | `umidade_baixa` | Amarelo | 600 Hz | 2 bipes curtos |
| Luminosidade alta | `luminosidade_alta` | Magenta | 2000 Hz | 1 bipe longo |
| Normalizado | `estavel` | Verde | — | Silêncio |
 
Os bipes se repetem a cada 4 segundos enquanto a anomalia persistir.
 
**Prioridade de avaliação:** temperatura > umidade > luminosidade. Apenas uma anomalia é reportada por vez.
 
---
 
## Estrutura de Arquivos
 
```
CP5-EdgeComputing/
├── dashboard_vinheria.py                          # Dashboard Flask com lógica de alertas
├── Sketch.ino                                 # Firmware ESP32
├── diagram.json                                   # Diagrama de circuito do Wokwi
├── Vinheria FIWARE - Sensor001.postman_collection.json  # Collection Postman
├── requirements.txt                               # Dependências Python
└── README.md
```
 
---
 
## Instalação e Execução
 
### Pré-requisitos
 
- Docker com a stack FIWARE rodando
- Python 3.x
### 1. Instalar dependências Python
 
```bash
pip install -r requirements.txt
```
 
### 2. Subir a stack FIWARE
 
```bash
docker compose up -d
```
 
### 3. Provisionar o sistema (primeira vez)
 
Importe a collection Postman, configure a variável `url` com o IP do servidor FIWARE e execute os passos em ordem:
 
- **Passo 1** — Health checks (todos devem retornar 200)
- **Passo 2** — Criar service group MQTT
- **Passo 3** — Provisionar dispositivo sensor001
- **Passo 4** — Criar subscrições STH-Comet
>  As URLs de notificação das subscrições devem usar `http://fiware-sth-comet:8666/notify` (nome do container Docker), não `localhost`.
 
### 4. Configurar o IP no código
 
Em `dashboard_vinheria.py`, atualize as variáveis com o IP do servidor FIWARE:
 
```python
BASE_URL    = "http://SEU_IP:8666"
BROKER_MQTT = "SEU_IP"
BROKER_PORT = 1883
```
 
Em `Sketch.ino`, atualize o broker:
 
```cpp
const char* default_BROKER_MQTT = "SEU_IP";
const int   default_BROKER_PORT = 1883;
```
 
### 5. Iniciar a simulação no Wokwi
 
Acesse [https://wokwi.com/projects/461036532566146049](https://wokwi.com/projects/461036532566146049) e clique em Play. Verifique no monitor serial que o ESP32 conectou ao broker MQTT.
 
### 6. Rodar o dashboard
 
```bash
python3 dashboard_vinheria.py
```
 
Acesse em: [http://localhost:5000](http://localhost:5000)
 
---
 
## Fluxo de Dados
 
```
ESP32 publica sensor → Mosquitto → IoT Agent → Orion
                                                  │
                                            Subscrição
                                                  │
                                                  ▼
                                            STH-Comet (armazena)
                                                  │
                                     Python consulta (lastN=20)
                                                  │
                                         Avalia thresholds
                                                  │
                               ┌──────────────────┴──────────────────┐
                               │ Anomalia detectada                  │ Normal
                               ▼                                     ▼
                  Publica comando MQTT                   Publica "estavel"
                  (ex: temp_alta)                        se estava crítico
                               │
                               ▼
                  ESP32 recebe → LED + Buzzer
```
 
---
 
## Observações Técnicas
 
**Parser de comandos:** o IoT Agent encapsula o comando no formato `sensor001@comando|sensor001@VALOR|`. O firmware usa `lastIndexOf('@')` para extrair o valor real, ignorando o encapsulamento duplo.
 
**Controle de estado:** o dashboard só publica um novo comando MQTT quando há mudança de estado ou tipo de anomalia, evitando inundar o broker.
 
**Subscrições STH-Comet:** a URL de notificação deve referenciar o nome do container Docker (`fiware-sth-comet`), não `localhost`, pois o Orion e o STH rodam em containers distintos na mesma rede Docker.