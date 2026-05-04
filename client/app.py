import requests

#Cria a plotagem do gráfico
from flask import Flask, jsonify, render_template

#Cria o Mqtt
import paho.mqtt.client as mqtt

#para o estado atual
estado_atual = "estavel"

app = Flask(__name__)

BROKER = "34.39.176.211"
PORT = 1883
TOPIC_CMD = "/TEF/sensor001/cmd"

def enviar_comando(comando):
    print(f"Enviando comando: {comando}")
    mqtt_client.publish(TOPIC_CMD, comando)

ultimo_estado = None
estado_atual = "estavel"

def verificar_anomalia(temp_data, hum_data, lum_data):
    global ultimo_estado, estado_atual

    if not temp_data or not hum_data or not lum_data:
        return

    temp = float(temp_data[-1]['attrValue'])
    hum = float(hum_data[-1]['attrValue'])
    lum = float(lum_data[-1]['attrValue'])

    print(f"T={temp} | H={hum} | L={lum}")

    estado = "estavel"

    if temp >= 30:
        estado = "temp_alta"
    elif temp <= 0:
        estado = "temp_baixa"
    elif hum >= 70:
        estado = "umidade_alta"
    elif hum <= 20:
        estado = "umidade_baixa"
    elif lum >= 90:
        estado = "luminosidade_alta"

    estado_atual = estado  

    if estado != ultimo_estado:
        print(f"Novo estado: {estado}")
        enviar_comando(estado)
        ultimo_estado = estado

    if estado != ultimo_estado:
        enviar_comando(estado)
        ultimo_estado = estado

mqtt_client = mqtt.Client()
mqtt_client.connect(BROKER, PORT, 60)

@app.route("/")
def index():
    return render_template("index.html")

BASE_URL = "http://34.39.176.211:8666"
ENTITY_ID = "urn:ngsi-ld:Sensor:001"

headers = {
    'fiware-service': 'smart',
    'fiware-servicepath': '/'
}

def obter_dados(atributo, lastN=30):
    url = f"{BASE_URL}/STH/v1/contextEntities/type/Sensor/id/{ENTITY_ID}/attributes/{atributo}?lastN={lastN}"
    
    try:
        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code == 200:
            data = response.json()
            valores = data['contextResponses'][0]['contextElement']['attributes'][0]['values']
            return valores
        else:
            return []
    except:
        return []

@app.route("/dados")
def dados():
    luminosity = obter_dados("luminosity")
    temperature = obter_dados("temperature")
    humidity = obter_dados("humidity")

    verificar_anomalia(temperature, humidity, luminosity)

    return jsonify({
        "luminosity": luminosity,
        "temperature": temperature,
        "humidity": humidity,
        "estado": estado_atual
    })

if __name__ == "__main__":
    app.run(port=5000, debug=True)