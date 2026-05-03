# =============================================================================
# dashboard_vinheria.py
# Dashboard web para monitoramento ambiental da Vinheria Agnaldo
#
#
# Execução:
#   python3 dashboard_vinheria.py
#   Acesse: http://localhost:5000
# =============================================================================
 
import requests          # requisições HTTP ao STH-Comet
import threading         # thread separada para o loop de alertas MQTT
import time              # controle de intervalo do loop
import paho.mqtt.client as mqtt  # cliente MQTT para enviar comandos ao ESP32
from flask import Flask, jsonify, render_template_string  # servidor web
 
 
# Endereço do STH-Comet (histórico de séries temporais)
BASE_URL  = "http://34.133.148.248:8666"
 
# Identificador da entidade registrada no Orion Context Broker
ENTITY_ID = "urn:ngsi-ld:Sensor:001"
 
# Cabeçalhos obrigatórios para o FIWARE multi-tenant
HEADERS = {
    "fiware-service":     "smart",
    "fiware-servicepath": "/"
}
 
# Broker MQTT — mesmo IP do FIWARE, porta padrão 1883
BROKER_MQTT = "34.133.148.248"
BROKER_PORT = 1883
 
# Tópico de comando: o IoT Agent roteia para o ESP32 via MQTT
TOPICO_CMD = "/TEF/sensor001/cmd"
 
# =============================================================================
# THRESHOLDS — faixas ideais para conservação de vinho
#
#   Temperatura: 10–15 °C
#     Abaixo → amargueia; Acima → acelera oxidação e degrada taninos
#
#   Umidade: 50–70 %
#     Abaixo → resseca rolhas (entrada de ar); Acima → proliferação de mofo
#
#   Luminosidade: 0–30 %
#     Acima → luz UV degrada compostos aromáticos e taninos
# =============================================================================
THRESHOLDS = {
    "temperature": {"min": 10,  "max": 15},
    "humidity":    {"min": 50,  "max": 70},
    "luminosity":  {"min": 0,   "max": 30},
}
 

# CLIENTE MQTT
# Conecta ao broker na inicialização e mantém conexão em background
estado_critico_anterior = None  # rastreia a anomalia ativa para evitar publicações repetidas
 
mqtt_client = mqtt.Client(client_id="dashboard_vinheria")
mqtt_client.connect(BROKER_MQTT, BROKER_PORT, keepalive=60)
mqtt_client.loop_start()  # inicia loop MQTT em thread interna do paho
 
 
def avaliar_anomalias(temp, hum, lum):
    """
    Avalia os valores mais recentes dos sensores contra os thresholds.
    Retorna a anomalia de maior prioridade e uma descrição legível.
    Prioridade: temperatura > umidade > luminosidade.
    Retorna (None, None) quando todos os sensores estão dentro do range.
    """
    t = THRESHOLDS
    if temp > t["temperature"]["max"]:
        return "temp_alta",         f"Temperatura ALTA ({temp:.1f}°C)"
    if temp < t["temperature"]["min"]:
        return "temp_baixa",        f"Temperatura BAIXA ({temp:.1f}°C)"
    if hum > t["humidity"]["max"]:
        return "umidade_alta",      f"Umidade ALTA ({hum:.1f}%)"
    if hum < t["humidity"]["min"]:
        return "umidade_baixa",     f"Umidade BAIXA ({hum:.1f}%)"
    if lum > t["luminosity"]["max"]:
        return "luminosidade_alta", f"Luminosidade ALTA ({lum:.1f}%)"
    return None, None
 
 
def publicar_comando(cmd, descricao):
    """
    Publica o comando de anomalia no tópico MQTT do ESP32.
    Só publica quando há mudança de estado para não inundar o broker.
 
    Formato do payload: "sensor001@COMANDO|"
    O IoT Agent interpreta e encaminha ao ESP32 via MQTT.
    """
    global estado_critico_anterior
 
    if cmd and cmd != estado_critico_anterior:
        # Nova anomalia detectada — aciona LED e buzzer no ESP32
        mqtt_client.publish(TOPICO_CMD, f"sensor001@{cmd}|")
        print(f"[ALERTA] {descricao} → '{cmd}' publicado.")
 
    elif not cmd and estado_critico_anterior:
        # Sensores normalizados — desliga alerta no ESP32
        mqtt_client.publish(TOPICO_CMD, "sensor001@estavel|")
        print("[OK] Sensores normalizados → 'estavel' publicado.")
 
    estado_critico_anterior = cmd  # atualiza estado para comparação futura
 
 
def obter_dados(atributo, lastN=20):
    """
    Consulta o STH-Comet pela API REST e retorna os últimos N registros
    de um atributo do sensor (luminosity, temperature ou humidity).
    Retorna lista vazia em caso de falha.
    """
    url = (
        f"{BASE_URL}/STH/v1/contextEntities/type/Sensor/id/"
        f"{ENTITY_ID}/attributes/{atributo}?lastN={lastN}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json()["contextResponses"][0]["contextElement"]["attributes"][0]["values"]
    except Exception:
        pass
    return []
 
 
def obter_ultimo(atributo):
    """Retorna somente o valor mais recente de um atributo."""
    dados = obter_dados(atributo, lastN=1)
    if dados:
        return float(dados[-1]["attrValue"])
    return None
 
 
def loop_alertas():
    """
    Loop executado em thread separada a cada 5 segundos.
    Lê o valor mais recente de cada sensor, avalia anomalias
    e publica o comando adequado no ESP32 via MQTT.
    """
    while True:
        try:
            lum  = obter_ultimo("luminosity")
            temp = obter_ultimo("temperature")
            hum  = obter_ultimo("humidity")
            if None not in (lum, temp, hum):
                cmd, desc = avaliar_anomalias(temp, hum, lum)
                publicar_comando(cmd, desc)
        except Exception as e:
            print(f"[loop_alertas] erro: {e}")
        time.sleep(5)
 
# FLASK — servidor web na porta 5000

app = Flask(__name__)
 
# HTML + CSS + JS do dashboard (template inline)
# Serve como single-page application: o frontend chama /api/dados a cada 5s
HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vinheria Agnaldo</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=Tenor+Sans&display=swap" rel="stylesheet">
<style>
  /* ── Paleta editorial enológica ── */
  :root {
    --bg:       #f5f0e8;       /* pergaminho envelhecido */
    --ink:      #1c1610;       /* tinta de impressão */
    --rule:     #c8b89a;       /* linha de régua tipográfica */
    --muted:    #8a7a68;       /* texto secundário */
    --wine:     #6b1d2a;       /* vinho tinto profundo */
    --gold:     #9a7c3f;       /* dourado envelhecido */
    --ok:       #2d5a3d;       /* verde musgo */
    --warn:     #8b3a1a;       /* terracota de alerta */
    --lum-c:    #9a7c3f;
    --tmp-c:    #6b1d2a;
    --hum-c:    #2a4a6b;
  }
 
  * { box-sizing: border-box; margin: 0; padding: 0; }
 
  body {
    background: var(--bg);
    color: var(--ink);
    font-family: 'Tenor Sans', sans-serif;
    min-height: 100vh;
    /* textura de papel sutil via noise SVG */
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
  }
 

  header {
    padding: 3rem 4rem 0;
    border-bottom: 2px solid var(--ink);
  }
 
  .header-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    padding-bottom: 0.6rem;
    font-size: 0.65rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--muted);
  }
 
  header h1 {
    font-family: 'Cormorant Garamond', serif;
    font-size: 3.8rem;
    font-weight: 300;
    letter-spacing: -0.01em;
    line-height: 1;
    color: var(--ink);
    padding-bottom: 0.5rem;
  }
 
  header h1 em {
    font-style: italic;
    color: var(--wine);
  }
 
  #status-bar {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 4rem;
    font-size: 0.62rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--muted);
    border-bottom: 1px solid var(--rule);
  }
 
  #status-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--ok);
    animation: blink 2.5s ease-in-out infinite;
  }
 
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.25} }
 
  #alerta-banner {
    margin: 1.2rem 4rem;
    padding: 0.7rem 1.2rem;
    border-left: 3px solid var(--wine);
    background: rgba(107,29,42,0.06);
    font-family: 'Cormorant Garamond', serif;
    font-size: 1rem;
    font-style: italic;
    color: var(--wine);
    letter-spacing: 0.02em;
  }
  #alerta-banner.hidden { display: none; }
 
  .readings {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    border-top: 1px solid var(--rule);
    border-bottom: 1px solid var(--rule);
    margin: 1.5rem 4rem 0;
  }
 
  .reading {
    padding: 1.8rem 0;
    text-align: center;
    position: relative;
  }
 
  .reading + .reading::before {
    content: '';
    position: absolute;
    left: 0; top: 20%; bottom: 20%;
    width: 1px;
    background: var(--rule);
  }
 
  .reading-label {
    font-size: 0.6rem;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.4rem;
  }
 
  .reading-value {
    font-family: 'Cormorant Garamond', serif;
    font-size: 3.2rem;
    font-weight: 300;
    line-height: 1;
    color: var(--ink);
  }
 
  .reading-unit {
    font-size: 1rem;
    color: var(--muted);
    margin-left: 0.15rem;
    font-weight: 300;
  }
 
  .reading-range {
    font-size: 0.58rem;
    letter-spacing: 0.1em;
    color: var(--muted);
    margin-top: 0.4rem;
    text-transform: uppercase;
  }
 
  .reading-status {
    display: inline-block;
    margin-top: 0.5rem;
    font-size: 0.55rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    padding: 0.15rem 0.5rem;
    border: 1px solid currentColor;
  }
 
  .st-ok   { color: var(--ok); }
  .st-warn { color: var(--warn); }
 
  /* ── Seção de gráficos ── */
  .charts-section {
    padding: 2rem 4rem 4rem;
  }
 
  .section-rule {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
 
  .section-rule span {
    font-size: 0.6rem;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: var(--muted);
    white-space: nowrap;
  }
 
  .section-rule::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--rule);
  }
 
  .chart-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 2rem;
  }
 
  .chart-block {}
 
  .chart-label {
    font-size: 0.58rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--rule);
  }
 
  .chart-container { position: relative; height: 220px; }
 
  /* ── Rodapé ── */
  footer {
    border-top: 2px solid var(--ink);
    padding: 1rem 4rem;
    display: flex;
    justify-content: space-between;
    font-size: 0.58rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
  }
</style>
</head>
<body>
 
<header>
  <div class="header-top">
    <span>Sistema de Monitoramento Ambiental</span>
    <span id="last-update">—</span>
  </div>
  <h1>Vinheria <em>Agnaldo</em></h1>
</header>
 
<div id="status-bar">
  <div id="status-dot"></div>
  <span>Ao vivo</span>
</div>
 
<div id="alerta-banner" class="hidden">
  ⚑ <span id="alerta-texto"></span>
</div>
 
<div class="readings">
  <div class="reading">
    <div class="reading-label">Luminosidade</div>
    <div class="reading-value" id="val-lum">—<span class="reading-unit">%</span></div>
    <div class="reading-range">Ideal 0 – 30 %</div>
    <div class="reading-status st-ok" id="st-lum">—</div>
  </div>
  <div class="reading">
    <div class="reading-label">Temperatura</div>
    <div class="reading-value" id="val-temp">—<span class="reading-unit">°C</span></div>
    <div class="reading-range">Ideal 10 – 15 °C</div>
    <div class="reading-status st-ok" id="st-temp">—</div>
  </div>
  <div class="reading">
    <div class="reading-label">Umidade</div>
    <div class="reading-value" id="val-hum">—<span class="reading-unit">%</span></div>
    <div class="reading-range">Ideal 50 – 70 %</div>
    <div class="reading-status st-ok" id="st-hum">—</div>
  </div>
</div>
 
<div class="charts-section">
  <div class="section-rule"><span>Histórico de leituras</span></div>
  <div class="chart-row">
    <div class="chart-block">
      <div class="chart-label">Luminosidade</div>
      <div class="chart-container"><canvas id="chart-lum"></canvas></div>
    </div>
    <div class="chart-block">
      <div class="chart-label">Temperatura</div>
      <div class="chart-container"><canvas id="chart-temp"></canvas></div>
    </div>
    <div class="chart-block">
      <div class="chart-label">Umidade</div>
      <div class="chart-container"><canvas id="chart-hum"></canvas></div>
    </div>
  </div>
</div>
 
<footer>
  <span>Vinheria Agnaldo — CP5 Edge Computing</span>
  <span>FIWARE STH-Comet · sensor001</span>
</footer>
 
<script>
// Mensagens de anomalia exibidas no banner
const ANOMALIA_MSG = {
  temp_alta:         "Temperatura elevada — risco de oxidação acelerada do vinho",
  temp_baixa:        "Temperatura baixa — risco de amargor",
  umidade_alta:      "Umidade elevada — risco de proliferação de mofo",
  umidade_baixa:     "Umidade baixa — rolhas podem ressecar",
  luminosidade_alta: "Luminosidade elevada — degradação de taninos por UV",
};
 
// Faixas ideais para colorir os status dos cards
const THRESHOLDS = {
  luminosity:  { min: 0,  max: 30 },
  temperature: { min: 10, max: 15 },
  humidity:    { min: 50, max: 70 },
};
 
// Cria um gráfico de linha minimalista para cada sensor
function makeChart(id, color) {
  return new Chart(document.getElementById(id).getContext('2d'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        data: [],
        borderColor: color,
        borderWidth: 1.5,
        pointRadius: 2,
        pointBackgroundColor: color,
        fill: true,
        // gradiente sutil abaixo da linha
        backgroundColor: color + '18',
        tension: 0.35
      }]
    },
    options: {
      animation: false,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: '#8a7a68', font: { size: 9 }, maxTicksLimit: 6 },
          grid:  { color: '#ddd4c0' }
        },
        y: {
          ticks: { color: '#8a7a68', font: { size: 9 } },
          grid:  { color: '#ddd4c0' }
        }
      }
    }
  });
}
 
// Instancia os três gráficos
const charts = {
  luminosity:  makeChart('chart-lum',  '#9a7c3f'),
  temperature: makeChart('chart-temp', '#6b1d2a'),
  humidity:    makeChart('chart-hum',  '#2a4a6b'),
};
 
// Atualiza o card de leitura atual e o badge de status
function setReading(id, value, attr) {
  const el   = document.getElementById('val-' + id);
  const unit = el.querySelector('.reading-unit').outerHTML;
  el.innerHTML = (value !== null ? value.toFixed(1) : '—') + unit;
 
  const st = document.getElementById('st-' + id);
  if (value === null) { st.textContent = '—'; return; }
 
  const { min, max } = THRESHOLDS[attr];
  const ok = value >= min && value <= max;
  st.textContent  = ok ? 'Normal' : 'Anomalia';
  st.className    = 'reading-status ' + (ok ? 'st-ok' : 'st-warn');
}
 
// Busca dados da API Flask e atualiza toda a interface
async function atualizar() {
  try {
    const d   = await fetch('/api/dados').then(r => r.json());
    const fmt = ts => new Date(ts).toLocaleTimeString('pt-BR', {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
 
    // Atualiza gráficos
    ['luminosity', 'temperature', 'humidity'].forEach(k => {
      charts[k].data.labels              = d[k].times.map(fmt);
      charts[k].data.datasets[0].data   = d[k].values;
      charts[k].update();
    });
 
    // Atualiza cards de leitura
    setReading('lum',  d.luminosity.values.at(-1)  ?? null, 'luminosity');
    setReading('temp', d.temperature.values.at(-1) ?? null, 'temperature');
    setReading('hum',  d.humidity.values.at(-1)    ?? null, 'humidity');
 
    // Exibe ou oculta o banner de alerta
    const banner = document.getElementById('alerta-banner');
    if (d.anomalia) {
      banner.classList.remove('hidden');
      document.getElementById('alerta-texto').textContent =
        ANOMALIA_MSG[d.anomalia] || d.anomalia;
    } else {
      banner.classList.add('hidden');
    }
 
    // Timestamp da última atualização
    document.getElementById('last-update').textContent =
      new Date().toLocaleTimeString('pt-BR');
 
  } catch (e) {
    console.error('Erro ao buscar dados:', e);
  }
}
 
// Atualiza imediatamente e depois a cada 5 segundos
atualizar();
setInterval(atualizar, 5000);
</script>
</body>
</html>"""
 
 
@app.route("/")
def index():
    """Serve o dashboard HTML."""
    return render_template_string(HTML)
 
 
@app.route("/api/dados")
def api_dados():
    """
    API REST consumida pelo frontend a cada 5 segundos.
    Retorna JSON com histórico e anomalia atual:
    {
      "luminosity":  { "values": [...], "times": [...] },
      "temperature": { "values": [...], "times": [...] },
      "humidity":    { "values": [...], "times": [...] },
      "anomalia":    "temp_alta" | null,
      "thresholds":  { ... }
    }
    """
    def parse(raw):
        return {
            "values": [float(e["attrValue"]) for e in raw],
            "times":  [e["recvTime"] for e in raw],
        }
 
    lum_p  = parse(obter_dados("luminosity",  lastN=20))
    temp_p = parse(obter_dados("temperature", lastN=20))
    hum_p  = parse(obter_dados("humidity",    lastN=20))
 
    # Pega o último valor de cada sensor para avaliar anomalias
    last_temp = temp_p["values"][-1] if temp_p["values"] else None
    last_hum  = hum_p["values"][-1]  if hum_p["values"]  else None
    last_lum  = lum_p["values"][-1]  if lum_p["values"]  else None
 
    anomalia = None
    if None not in (last_temp, last_hum, last_lum):
        anomalia, _ = avaliar_anomalias(last_temp, last_hum, last_lum)
 
    return jsonify({
        "luminosity":  lum_p,
        "temperature": temp_p,
        "humidity":    hum_p,
        "anomalia":    anomalia,
        "thresholds":  THRESHOLDS,
    })
 
 
# =============================================================================
# INICIALIZAÇÃO
# Sobe a thread de alertas MQTT em background e inicia o servidor Flask
# =============================================================================
if __name__ == "__main__":
    # Thread daemon: encerra automaticamente quando o processo principal termina
    threading.Thread(target=loop_alertas, daemon=True).start()
 
    # debug=False obrigatório em produção (não recarrega automaticamente)
    app.run(host="0.0.0.0", port=5000, debug=False)