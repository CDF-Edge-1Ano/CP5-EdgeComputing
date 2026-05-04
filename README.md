# APAP - Monitoramento IoT com FIWARE, MQTT e Dashboard Web

## Desenvolvedores
| Nome | Função |
|------|--------|
| Gabriel Ardito | Dsenvolveimento |
| Felipe Menezes | Desenvolvimento |
| João Sarracine | Desenvolvimento |
| João Gonzales  | Desenvolvimento |

---

## Descrição

O APAP é um sistema de monitoramento IoT que coleta, processa e visualiza dados ambientais em tempo real. O projeto integra sensores (via FIWARE), comunicação MQTT e um dashboard web interativo para acompanhamento de métricas como temperatura, umidade e luminosidade.

Além da visualização, o sistema realiza detecção de anomalias e envia comandos automaticamente via MQTT quando condições críticas são identificadas.

---

## Arquitetura do Projeto

O sistema é composto por três principais camadas:

### 1. Backend (Flask)
Responsável por:
- Buscar dados do FIWARE
- Processar e detectar anomalias
- Expor API (/dados)
- Enviar comandos via MQTT

Arquivo principal: app.py

---

### 2. Frontend (Dashboard)
Interface web que:
- Exibe gráficos em tempo real
- Mostra estado atual do sistema
- Atualiza automaticamente a cada 2 segundos

Arquivos:
- HTML: index.html  
- CSS: style.css  
- JS: script.js  

---

### 3. Integração com IoT
- Dados consumidos via FIWARE (STH-Comet)
- Comunicação com dispositivos via MQTT
- Broker MQTT configurado no backend

---

## Funcionalidades

- Monitoramento em tempo real de:
  - Temperatura
  - Umidade
  - Luminosidade

- Visualização com gráficos dinâmicos (Chart.js)

- Detecção automática de anomalias:
  - Temperatura alta ou baixa
  - Umidade alta ou baixa
  - Luminosidade elevada

- Envio automático de comandos MQTT quando ocorre mudança de estado

- Atualização contínua da interface

---

## Regras de Anomalia

| Condição | Estado |
|--------|--------|
| Temp ≥ 30°C | temp_alta |
| Temp ≤ 0°C | temp_baixa |
| Umidade ≥ 70% | umidade_alta |
| Umidade ≤ 20% | umidade_baixa |
| Luminosidade ≥ 90% | luminosidade_alta |
| Caso contrário | estavel |

---

## Tecnologias Utilizadas

### Backend
- Python
- Flask
- Requests
- Paho MQTT

### Frontend
- HTML5
- CSS3
- JavaScript
- Chart.js

### IoT / Middleware
- FIWARE (STH-Comet)
- MQTT

---

## Estrutura do Projeto

```
.
├── client/
│   ├── app.py
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── style/
│       │   └── style.css
│       └── script/
│           └── script.js
├── diagram.json
├── README.md
├── requirements.txt
├── sketch.ino
└── Vinheria FIWARE - Sensor001.postman_collection.json
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

## Funcionamento do Fluxo

1. O frontend faz requisições periódicas para /dados
2. O backend consulta o FIWARE
3. Os dados são processados
4. O sistema verifica anomalias
5. Se houver mudança de estado:
   - Um comando MQTT é enviado
6. Os dados são retornados ao frontend
7. Os gráficos e estado são atualizados

---

## Melhorias Futuras

- Implementação de detecção de anomalias com machine learning
- Histórico persistente em banco de dados
- Sistema de alertas (email, SMS, push)
- Interface mais avançada com filtros de tempo
- Controle manual via dashboard
- Autenticação de usuários

---

## Observações

- O sistema depende de um broker MQTT ativo
- O endpoint FIWARE deve estar acessível
- O estado é baseado apenas na última leitura recebida
