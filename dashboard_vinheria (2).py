import requests
import threading
import time
import paho.mqtt.client as mqtt
from flask import Flask, jsonify, render_template_string

# ── CONFIGURAÇÃO ──────────────────────────────────────────────────────────────
BASE_URL  = "http://bore.pub:40816"
ENTITY_ID = "urn:ngsi-ld:Sensor:001"
HEADERS   = {"fiware-service": "smart", "fiware-servicepath": "/"}

BROKER_MQTT = "bore.pub"
BROKER_PORT = 58233
TOPICO_CMD  = "/TEF/sensor001/cmd"

THRESHOLDS = {
    "temperature": {"min": 10,  "max": 15},
    "humidity":    {"min": 50,  "max": 70},
    "luminosity":  {"min": 0,   "max": 30},
}

# ── MQTT ──────────────────────────────────────────────────────────────────────
estado_critico_anterior = None

mqtt_client = mqtt.Client(client_id="dashboard_vinheria")
mqtt_client.connect(BROKER_MQTT, BROKER_PORT, keepalive=60)
mqtt_client.loop_start()

def avaliar_anomalias(temp, hum, lum):
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
    global estado_critico_anterior
    if cmd and cmd != estado_critico_anterior:
        mqtt_client.publish(TOPICO_CMD, f"sensor001@{cmd}|")
        print(f"[ALERTA] {descricao} → '{cmd}' publicado.")
    elif not cmd and estado_critico_anterior:
        mqtt_client.publish(TOPICO_CMD, "sensor001@estavel|")
        print("[OK] Sensores normalizados → 'estavel' publicado.")
    estado_critico_anterior = cmd

def obter_ultimo(atributo):
    dados = obter_dados(atributo, lastN=1)
    if dados:
        return float(dados[-1]["attrValue"])
    return None

def loop_alertas():
    while True:
        try:
            lum  = obter_ultimo("luminosity")
            temp = obter_ultimo("temperature")
            hum  = obter_ultimo("humidity")
            if temp is not None and hum is not None and lum is not None:
                cmd, desc = avaliar_anomalias(temp, hum, lum)
                publicar_comando(cmd, desc)
        except Exception as e:
            print(f"[loop_alertas] erro: {e}")
        time.sleep(5)

# ── STH-COMET ─────────────────────────────────────────────────────────────────
def obter_dados(atributo, lastN=20):
    url = (f"{BASE_URL}/STH/v1/contextEntities/type/Sensor/id/"
           f"{ENTITY_ID}/attributes/{atributo}?lastN={lastN}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json()["contextResponses"][0]["contextElement"]["attributes"][0]["values"]
    except:
        pass
    return []

# ── FLASK ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vinheria Agnaldo</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:          #0e0a0f;
    --surface:     #1a1020;
    --border:      #2e1f3a;
    --gold:        #c9a84c;
    --wine-bright: #c0243f;
    --text:        #e8dcc8;
    --muted:       #7a6e5e;
    --ok:          #4caf7d;
    --warn:        #e07b39;
    --chart-lum:   #c9a84c;
    --chart-tmp:   #c0243f;
    --chart-hum:   #4c8bc9;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    min-height: 100vh;
    background-image:
      radial-gradient(ellipse at 20% 0%, rgba(139,26,46,0.15) 0%, transparent 60%),
      radial-gradient(ellipse at 80% 100%, rgba(201,168,76,0.08) 0%, transparent 60%);
  }
  header {
    border-bottom: 1px solid var(--border);
    padding: 2rem 3rem;
    display: flex;
    align-items: baseline;
    gap: 1.5rem;
  }
  header h1 {
    font-family: 'Playfair Display', serif;
    font-size: 1.8rem;
    color: var(--gold);
    letter-spacing: 0.02em;
  }
  header span { font-size: 0.7rem; color: var(--muted); letter-spacing: 0.15em; text-transform: uppercase; }
  #status-bar {
    padding: 0.6rem 3rem;
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 0.8rem;
    color: var(--muted);
  }
  #status-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--ok); box-shadow: 0 0 8px var(--ok);
    animation: pulse 2s infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  #alerta-banner {
    margin: 1.5rem 3rem 0;
    padding: 0.9rem 1.4rem;
    border: 1px solid var(--wine-bright);
    border-radius: 4px;
    background: rgba(139,26,46,0.15);
    color: var(--wine-bright);
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    display: flex;
    align-items: center;
    gap: 0.8rem;
  }
  #alerta-banner.hidden { display: none; }
  .cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.2rem;
    padding: 2rem 3rem 0;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.4rem 1.6rem;
    position: relative;
    overflow: hidden;
  }
  .card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 2px; background: var(--accent);
  }
  .card.lum  { --accent: var(--chart-lum); }
  .card.temp { --accent: var(--chart-tmp); }
  .card.hum  { --accent: var(--chart-hum); }
  .card-label { font-size: 0.65rem; letter-spacing: 0.2em; text-transform: uppercase; color: var(--muted); margin-bottom: 0.5rem; }
  .card-value { font-family: 'Playfair Display', serif; font-size: 2.4rem; color: var(--text); line-height: 1; }
  .card-unit  { font-size: 0.9rem; color: var(--muted); margin-left: 0.2rem; }
  .card-range { font-size: 0.65rem; color: var(--muted); margin-top: 0.6rem; letter-spacing: 0.05em; }
  .card-status {
    position: absolute; top: 1.2rem; right: 1.2rem;
    font-size: 0.6rem; letter-spacing: 0.15em; text-transform: uppercase;
    padding: 0.2rem 0.5rem; border-radius: 2px;
  }
  .status-ok   { color: var(--ok);   background: rgba(76,175,125,0.1);  border: 1px solid rgba(76,175,125,0.3); }
  .status-warn { color: var(--warn); background: rgba(224,123,57,0.1);  border: 1px solid rgba(224,123,57,0.3); }
  .charts { display: grid; gap: 1.2rem; padding: 1.5rem 3rem 3rem; }
  .chart-wrap {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.4rem 1.6rem;
  }
  .chart-title { font-size: 0.65rem; letter-spacing: 0.2em; text-transform: uppercase; color: var(--muted); margin-bottom: 1rem; }
  canvas { width: 100% !important; height: 180px !important; }
  #last-update { font-size: 0.65rem; color: var(--muted); }
</style>
</head>
<body>

<header>
  <h1>Vinheria Agnaldo</h1>
  <span>Monitoramento Ambiental</span>
</header>

<div id="status-bar">
  <div id="status-dot"></div>
  <span>AO VIVO</span>
  <span style="margin-left:auto" id="last-update">—</span>
</div>

<div id="alerta-banner" class="hidden">
  ⚠ <span id="alerta-texto"></span>
</div>

<div class="cards">
  <div class="card lum">
    <div class="card-label">Luminosidade</div>
    <div class="card-value" id="val-lum">—<span class="card-unit">%</span></div>
    <div class="card-range">Ideal: 0 – 30%</div>
    <div class="card-status" id="st-lum">—</div>
  </div>
  <div class="card temp">
    <div class="card-label">Temperatura</div>
    <div class="card-value" id="val-temp">—<span class="card-unit">°C</span></div>
    <div class="card-range">Ideal: 10 – 15 °C</div>
    <div class="card-status" id="st-temp">—</div>
  </div>
  <div class="card hum">
    <div class="card-label">Umidade</div>
    <div class="card-value" id="val-hum">—<span class="card-unit">%</span></div>
    <div class="card-range">Ideal: 50 – 70%</div>
    <div class="card-status" id="st-hum">—</div>
  </div>
</div>

<div class="charts">
  <div class="chart-wrap">
    <div class="chart-title">Luminosidade — histórico</div>
    <canvas id="chart-lum"></canvas>
  </div>
  <div class="chart-wrap">
    <div class="chart-title">Temperatura — histórico</div>
    <canvas id="chart-temp"></canvas>
  </div>
  <div class="chart-wrap">
    <div class="chart-title">Umidade — histórico</div>
    <canvas id="chart-hum"></canvas>
  </div>
</div>

<script>
const ANOMALIA_MSG = {
  temp_alta:         "Temperatura ALTA — risco de oxidação acelerada",
  temp_baixa:        "Temperatura BAIXA — risco de amargor",
  umidade_alta:      "Umidade ALTA — risco de mofo",
  umidade_baixa:     "Umidade BAIXA — rolhas ressecando",
  luminosidade_alta: "Luminosidade ALTA — degradação de taninos",
};

const THRESHOLDS = {
  luminosity:  { min: 0,  max: 30 },
  temperature: { min: 10, max: 15 },
  humidity:    { min: 50, max: 70 },
};

function makeChart(id, color) {
  return new Chart(document.getElementById(id).getContext('2d'), {
    type: 'line',
    data: { labels: [], datasets: [{ data: [], borderColor: color, borderWidth: 1.5,
      pointRadius: 2, pointBackgroundColor: color, fill: true,
      backgroundColor: color + '18', tension: 0.3 }] },
    options: {
      animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#7a6e5e', font: { family: 'DM Mono', size: 10 }, maxTicksLimit: 8 }, grid: { color: '#2e1f3a' } },
        y: { ticks: { color: '#7a6e5e', font: { family: 'DM Mono', size: 10 } }, grid: { color: '#2e1f3a' } }
      }
    }
  });
}

const charts = {
  luminosity:  makeChart('chart-lum',  '#c9a84c'),
  temperature: makeChart('chart-temp', '#c0243f'),
  humidity:    makeChart('chart-hum',  '#4c8bc9'),
};

function setCard(id, value, attr) {
  const el = document.getElementById('val-' + id);
  const unit = el.querySelector('.card-unit').outerHTML;
  el.innerHTML = (value !== null ? value.toFixed(1) : '—') + unit;
  const st = document.getElementById('st-' + id);
  if (value === null) { st.textContent = '—'; st.className = 'card-status'; return; }
  const { min, max } = THRESHOLDS[attr];
  const ok = value >= min && value <= max;
  st.textContent = ok ? 'normal' : 'anomalia';
  st.className = 'card-status ' + (ok ? 'status-ok' : 'status-warn');
}

async function atualizar() {
  try {
    const d = await fetch('/api/dados').then(r => r.json());
    const fmt = ts => new Date(ts).toLocaleTimeString('pt-BR', { hour:'2-digit', minute:'2-digit', second:'2-digit' });

    ['luminosity','temperature','humidity'].forEach(k => {
      charts[k].data.labels = d[k].times.map(fmt);
      charts[k].data.datasets[0].data = d[k].values;
      charts[k].update();
    });

    setCard('lum',  d.luminosity.values.at(-1)  ?? null, 'luminosity');
    setCard('temp', d.temperature.values.at(-1) ?? null, 'temperature');
    setCard('hum',  d.humidity.values.at(-1)    ?? null, 'humidity');

    const banner = document.getElementById('alerta-banner');
    if (d.anomalia) {
      banner.classList.remove('hidden');
      document.getElementById('alerta-texto').textContent = ANOMALIA_MSG[d.anomalia] || d.anomalia;
    } else {
      banner.classList.add('hidden');
    }

    document.getElementById('last-update').textContent = 'Atualizado: ' + new Date().toLocaleTimeString('pt-BR');
  } catch(e) { console.error(e); }
}

atualizar();
setInterval(atualizar, 5000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/dados")
def api_dados():
    lum_raw  = obter_dados("luminosity",  lastN=20)
    temp_raw = obter_dados("temperature", lastN=20)
    hum_raw  = obter_dados("humidity",    lastN=20)

    def parse(raw):
        return {
            "values": [float(e["attrValue"]) for e in raw],
            "times":  [e["recvTime"] for e in raw],
        }

    lum_p  = parse(lum_raw)
    temp_p = parse(temp_raw)
    hum_p  = parse(hum_raw)

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

if __name__ == "__main__":
    threading.Thread(target=loop_alertas, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
