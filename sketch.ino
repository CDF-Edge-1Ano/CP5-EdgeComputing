#include <WiFi.h>
#include <PubSubClient.h>
#include <vector>
#include <DHT.h>
 
const char* default_SSID = "FIAP-IOT";
const char* default_PASSWORD = "F!@p25.IOT";
const char* default_BROKER_MQTT = "34.39.176.211";
const int default_BROKER_PORT = 1883;
const char* default_TOPICO_SUBSCRIBE = "/TEF/sensor001/cmd";
const char* default_TOPICO_SUBSCRIBE2 = "/TEF/sensor001/cmd/";
const char* default_TOPICO_PUBLISH_1 = "/TEF/sensor001/attrs";
const char* default_TOPICO_PUBLISH_2 = "/TEF/sensor001/attrs/l";
const char* default_TOPICO_PUBLISH_3 = "/TEF/sensor001/attrs/t";
const char* default_TOPICO_PUBLISH_4 = "/TEF/sensor001/attrs/h";
const char* default_PICO_PUBLISH_3 = "/tef/sensor";
const char* default_ID_MQTT = "fiware_001";
 
const char* topicPrefix = "sensor001";
 
#define DHTPIN 21
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);
 
char* SSID = const_cast<char*>(default_SSID);
char* PASSWORD = const_cast<char*>(default_PASSWORD);
char* BROKER_MQTT = const_cast<char*>(default_BROKER_MQTT);
int BROKER_PORT = default_BROKER_PORT;
char* TOPICO_SUBSCRIBE = const_cast<char*>(default_TOPICO_SUBSCRIBE);
char* TOPICO_PUBLISH_1 = const_cast<char*>(default_TOPICO_PUBLISH_1);
char* TOPICO_PUBLISH_2 = const_cast<char*>(default_TOPICO_PUBLISH_2);
char* TOPICO_PUBLISH_3 = const_cast<char*>(default_TOPICO_PUBLISH_3);
char* TOPICO_PUBLISH_4 = const_cast<char*>(default_TOPICO_PUBLISH_4);
char* ID_MQTT = const_cast<char*>(default_ID_MQTT);
 
const int RED_PIN   = 25;
const int GREEN_PIN = 26;
const int BLUE_PIN  = 27;
const int buzzer_pin = 14;
 
WiFiClient espClient;
PubSubClient MQTT(espClient);
char EstadoSaida = '0';
bool modoCritico = false;
unsigned long timerEndMillis = 0;
int potencia = 100;
 
// ── ANOMALIA ATIVA ────────────────────────────────────────────────────────────
// Guarda qual anomalia está ativa para que o loop() possa repetir os bipes
String anomaliaAtiva = "";
 
// Controle de repetição de bipes sem bloquear o loop
unsigned long proximoBipe = 0;
const unsigned long INTERVALO_REPETICAO = 4000; // repete a sequência a cada 4s
 
std::vector<String> nomesCores = {"ligar", "desligar", "vermelho", "azul", "verde", "amarelo"};
std::vector<String> hexaCores  = {"#FFFFFF", "#000000", "#FF0000", "#0000FF", "#00FF00", "#FFFF00"};
 
// ── PROTÓTIPOS ────────────────────────────────────────────────────────────────
void initSerial();
void initWiFi();
void initMQTT();
void reconectWiFi();
void reconnectMQTT();
void VerificaConexoesWiFIEMQTT();
void EnviaEstadoOutputMQTT();
void InitOutput();
void verificarTimer();
void handleLuminosity();
void handleEnviroment();
void setarCorPraHex(String hexColor);
void setarUsandoNome(String msg);
void adicionarNovaCor(String msg);
void entrarModoCritico();
void sairModoCritico();
void mqtt_callback(char* topic, byte* payload, unsigned int length);
 
// ── FUNÇÕES DE ANOMALIA ───────────────────────────────────────────────────────
 
// Toca um bipe simples com frequência e duração definidos.
// Usa tone()/noTone() — disponível no Wokwi com ESP32.
void tocarBipe(int frequencia, int duracao) {
    tone(buzzer_pin, frequencia, duracao);
    delay(duracao);
    noTone(buzzer_pin);
    delay(80); // pausa entre bipes
}
 
// Executa a sequência de bipes correspondente à anomalia.
void executarBipes(String anomalia) {
    if (anomalia == "temp_alta") {
        // 3 bipes agudos — temperatura alta
        Serial.println(F("[ANOMALIA] Temperatura ALTA — 3 bipes 1500 Hz"));
        for (int i = 0; i < 3; i++) tocarBipe(1500, 150);
    }
    else if (anomalia == "temp_baixa") {
        // 3 bipes graves — temperatura baixa
        Serial.println(F("[ANOMALIA] Temperatura BAIXA — 3 bipes 800 Hz"));
        for (int i = 0; i < 3; i++) tocarBipe(800, 150);
    }
    else if (anomalia == "umidade_alta") {
        // 2 bipes médio-agudos — umidade alta
        Serial.println(F("[ANOMALIA] Umidade ALTA — 2 bipes 1200 Hz"));
        for (int i = 0; i < 2; i++) tocarBipe(1200, 150);
    }
    else if (anomalia == "umidade_baixa") {
        // 2 bipes graves — umidade baixa
        Serial.println(F("[ANOMALIA] Umidade BAIXA — 2 bipes 600 Hz"));
        for (int i = 0; i < 2; i++) tocarBipe(600, 150);
    }
    else if (anomalia == "luminosidade_alta") {
        // 1 bipe longo agudo — luminosidade alta
        Serial.println(F("[ANOMALIA] Luminosidade ALTA — 1 bipe longo 2000 Hz"));
        tocarBipe(2000, 600);
    }
}
 
// Ativa o LED e o buzzer conforme a anomalia recebida.
void ativarAnomalia(String anomalia) {
    anomaliaAtiva = anomalia;
    modoCritico   = true;
    EstadoSaida   = '1';
    proximoBipe   = 0; // força execução imediata no próximo loop
 
    if (anomalia == "temp_alta") {
        Serial.println(F("*** ANOMALIA: TEMPERATURA ALTA — LED vermelho ***"));
        setarCorPraHex("#FF0000");
    }
    else if (anomalia == "temp_baixa") {
        Serial.println(F("*** ANOMALIA: TEMPERATURA BAIXA — LED azul ***"));
        setarCorPraHex("#0000FF");
    }
    else if (anomalia == "umidade_alta") {
        Serial.println(F("*** ANOMALIA: UMIDADE ALTA — LED ciano ***"));
        setarCorPraHex("#00FFFF");
    }
    else if (anomalia == "umidade_baixa") {
        Serial.println(F("*** ANOMALIA: UMIDADE BAIXA — LED amarelo ***"));
        setarCorPraHex("#FFFF00");
    }
    else if (anomalia == "luminosidade_alta") {
        Serial.println(F("*** ANOMALIA: LUMINOSIDADE ALTA — LED magenta ***"));
        setarCorPraHex("#FF00FF");
    }
    else {
        // Comando "critico" genérico (compatibilidade com versão anterior)
        Serial.println(F("*** MODO CRITICO GENERICO — LED vermelho ***"));
        setarCorPraHex("#FF0000");
        digitalWrite(buzzer_pin, HIGH);
    }
}
 
// Chamada no loop() para repetir os bipes enquanto há anomalia ativa.
void gerenciarBipesAtivos() {
    if (!modoCritico || anomaliaAtiva == "") return;
 
    unsigned long agora = millis();
    if (agora >= proximoBipe) {
        executarBipes(anomaliaAtiva);
        proximoBipe = agora + INTERVALO_REPETICAO;
    }
}
 
// ── SETUP / LOOP ──────────────────────────────────────────────────────────────
 
void setup() {
    InitOutput();
    initSerial();
    initWiFi();
    initMQTT();
    delay(5000);
    MQTT.publish(TOPICO_PUBLISH_1, "s|on");
    dht.begin();
}
 
void loop() {
    VerificaConexoesWiFIEMQTT();
    EnviaEstadoOutputMQTT();
    handleLuminosity();
    handleEnviroment();
    verificarTimer();
    gerenciarBipesAtivos(); // <-- único acréscimo no loop
    MQTT.loop();
}
 
// ── CALLBACK MQTT ─────────────────────────────────────────────────────────────
 
void mqtt_callback(char* topic, byte* payload, unsigned int length) {
    String msgOriginal;
    for (int i = 0; i < length; i++) {
        char c = (char)payload[i];
        msgOriginal += c;
    }
 
    msgOriginal.trim();
    msgOriginal.toLowerCase();
    Serial.print("- Mensagem recebida (raw): ");
    Serial.println(msgOriginal);
 
    // Extrai o conteúdo após o último '@' — resolve o duplo encapsulamento
    // do Orion: "sensor001@comando|sensor001@temp_alta|"
    int posArroba = msgOriginal.lastIndexOf('@');
    if (posArroba != -1) {
        msgOriginal = msgOriginal.substring(posArroba + 1);
        int posPipeFinal = msgOriginal.lastIndexOf('|');
        if (posPipeFinal != -1 && posPipeFinal == (int)msgOriginal.length() - 1) {
            msgOriginal = msgOriginal.substring(0, posPipeFinal);
        }
        msgOriginal.trim();
        Serial.print("- Comando extraido: ");
        Serial.println(msgOriginal);
    }
 
    potencia = 100;
 
    String parteCor = msgOriginal;
    int timerSegundos = 0;
    int potenciaTemp = 100;
 
    int pos1 = msgOriginal.indexOf('|');
    int pos2 = msgOriginal.indexOf('|', pos1 + 1);
 
    if (pos1 != -1) {
        parteCor = msgOriginal.substring(0, pos1);
 
        if (pos2 != -1) {
            String param1 = msgOriginal.substring(pos1 + 1, pos2);
            String param2 = msgOriginal.substring(pos2 + 1);
            param1.trim(); param2.trim();
 
            if (param1.startsWith("t")) { param1.remove(0,1); timerSegundos = param1.toInt(); }
            else if (param1.startsWith("p")) { param1.remove(0,1); potenciaTemp = param1.toInt(); }
 
            if (param2.startsWith("t")) { param2.remove(0,1); timerSegundos = param2.toInt(); }
            else if (param2.startsWith("p")) { param2.remove(0,1); potenciaTemp = param2.toInt(); }
        } else {
            String param1 = msgOriginal.substring(pos1 + 1);
            param1.trim();
            if (param1.startsWith("t")) { param1.remove(0,1); timerSegundos = param1.toInt(); }
            else if (param1.startsWith("p")) { param1.remove(0,1); potenciaTemp = param1.toInt(); }
        }
    }
 
    if (potenciaTemp != 100) {
        potencia = potenciaTemp;
        Serial.print("Potencia: ");
        Serial.println(potencia);
    }
 
    // ── COMANDOS ORIGINAIS ────────────────────────────────────────────────────
    if (parteCor == "on") {
        EstadoSaida = '1';
        setarCorPraHex("#FFFFFF");
        return;
    }
    if (parteCor == "off") {
        EstadoSaida = '0';
        setarCorPraHex("#000000");
        timerEndMillis = 0;
        potencia = 100;
        return;
    }
    if (msgOriginal.startsWith("add")) {
        adicionarNovaCor(msgOriginal);
        EstadoSaida = '1';
        return;
    }
 
    // ── COMANDOS DE ANOMALIA ESPECÍFICA (novos) ───────────────────────────────
    if (parteCor == "temp_alta"        ||
        parteCor == "temp_baixa"       ||
        parteCor == "umidade_alta"     ||
        parteCor == "umidade_baixa"    ||
        parteCor == "luminosidade_alta") {
        ativarAnomalia(parteCor);
        return;
    }
 
    // ── COMANDOS GENÉRICOS (compatibilidade) ──────────────────────────────────
    if (parteCor == "critico") {
        ativarAnomalia("critico");
        return;
    }
    if (parteCor == "estavel") {
        sairModoCritico();
        return;
    }
 
    if (parteCor.startsWith("#")) {
        Serial.println("cor recebida Hex:");
        Serial.println(parteCor);
        EstadoSaida = '1';
        setarCorPraHex(parteCor);
    } else if (parteCor == "desligar" || parteCor == "#000000") {
        EstadoSaida = '0';
        setarCorPraHex("#000000");
        timerEndMillis = 0;
        potencia = 100;
        return;
    } else {
        setarUsandoNome(parteCor);
    }
 
    if (timerSegundos > 0) {
        timerEndMillis = millis() + (timerSegundos * 1000UL);
        Serial.print("Timer ativado: ");
        Serial.print(timerSegundos);
        Serial.println(" segundos");
    }
}
 
// ── FUNÇÕES ORIGINAIS (inalteradas) ──────────────────────────────────────────
 
void initSerial() { Serial.begin(115200); }
 
void initWiFi() {
    delay(10);
    Serial.println("------Conexao WI-FI------");
    Serial.print("Conectando-se na rede: ");
    Serial.println(SSID);
    Serial.println("Aguarde");
    reconectWiFi();
}
 
void initMQTT() {
    MQTT.setServer(BROKER_MQTT, BROKER_PORT);
    MQTT.setCallback(mqtt_callback);
}
 
void reconectWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;
    WiFi.begin(SSID, PASSWORD);
    while (WiFi.status() != WL_CONNECTED) { delay(100); Serial.print("."); }
    Serial.println();
    Serial.println("Conectado com sucesso na rede ");
    Serial.print(SSID);
    Serial.println("IP obtido: ");
    Serial.println(WiFi.localIP());
    setarCorPraHex("#000000");
}
 
void VerificaConexoesWiFIEMQTT() {
    if (!MQTT.connected()) reconnectMQTT();
    reconectWiFi();
}
 
void EnviaEstadoOutputMQTT() {
    if (EstadoSaida == '1') Serial.println("- Led Ligado");
    if (EstadoSaida == '0') Serial.println("- Led Desligado");
    Serial.println("- Estado do LED enviado ao broker!");
    delay(1000);
}
 
void InitOutput() {
    pinMode(RED_PIN,   OUTPUT);
    pinMode(GREEN_PIN, OUTPUT);
    pinMode(BLUE_PIN,  OUTPUT);
    pinMode(buzzer_pin, OUTPUT);
}
 
void verificarTimer() {
    if (timerEndMillis > 0 && millis() >= timerEndMillis) {
        timerEndMillis = 0;
        Serial.println(F("Timer expirou - desligando LED"));
        setarCorPraHex("#000000");
        EstadoSaida = '0';
    }
}
 
void reconnectMQTT() {
    while (!MQTT.connected()) {
        Serial.print("* Tentando se conectar ao Broker MQTT: ");
        Serial.println(BROKER_MQTT);
        if (MQTT.connect(ID_MQTT)) {
            Serial.println("Conectado com sucesso ao broker MQTT!");
            MQTT.subscribe(TOPICO_SUBSCRIBE);
        } else {
            Serial.println("Falha ao reconectar no broker.");
            Serial.println("Havera nova tentativa de conexao em 2s");
            delay(2000);
        }
    }
}
 
void handleLuminosity() {
    const int potPin = 34;
    int sensorValue = analogRead(potPin);
    int luminosity = map(sensorValue, 4095, 0, 0, 100);
    String mensagem = String(luminosity);
    Serial.print(F("Valor da luminosidade: "));
    Serial.println(mensagem.c_str());
    MQTT.publish(TOPICO_PUBLISH_2, mensagem.c_str());
}
 
void handleEnviroment() {
    int h_raw = (int)dht.readHumidity();
    int t_raw = (int)dht.readTemperature();
 
    if (isnan(h_raw) || isnan(t_raw)) {
        Serial.println(F("o sensor dht11 nao ta lendo"));
        return;
    }
 
    int h = (int)h_raw;
    int t = (int)t_raw;
    int tPercent = t;
 
    MQTT.publish(TOPICO_PUBLISH_3, String(tPercent).c_str());
    MQTT.publish(TOPICO_PUBLISH_4, String(h).c_str());
 
    Serial.print(F("T: ")); Serial.print(tPercent); Serial.print(F("C | "));
    Serial.print(F("U: ")); Serial.print(h); Serial.println(F("%"));
}
 
void setarCorPraHex(String hexColor) {
    if (hexColor.startsWith("#")) hexColor.remove(0, 1);
    long number = strtol(hexColor.c_str(), NULL, 16);
    int r = number >> 16;
    int g = (number >> 8) & 0xFF;
    int b = number & 0xFF;
    float fator = potencia / 100.0;
    r = (int)(r * fator);
    g = (int)(g * fator);
    b = (int)(b * fator);
    analogWrite(RED_PIN,   r);
    analogWrite(GREEN_PIN, g);
    analogWrite(BLUE_PIN,  b);
    Serial.print(F("RGB -> ")); Serial.print(r); Serial.print(",");
    Serial.print(g); Serial.print(","); Serial.println(b);
}
 
void setarUsandoNome(String msg) {
    msg.trim();
    msg.toLowerCase();
    int total = nomesCores.size();
    for (int i = 0; i < total; i++) {
        if (msg == nomesCores[i]) {
            Serial.print("Sucesso! Nome: "); Serial.print(nomesCores[i]);
            Serial.print(F(" -> Hex: ")); Serial.println(hexaCores[i]);
            EstadoSaida = '1';
            setarCorPraHex(hexaCores[i]);
            return;
        }
    }
    Serial.println("Cor nao encontrada na lista.");
    EstadoSaida = '0';
}
 
void adicionarNovaCor(String msg) {
    int pos1 = msg.indexOf('|');
    int pos2 = msg.indexOf('|', pos1 + 1);
    if (pos1 != -1 && pos2 != -1) {
        String nomeCor = msg.substring(pos1 + 1, pos2);
        String hexaCor = msg.substring(pos2 + 1);
        nomeCor.trim(); hexaCor.trim();
        int posHex = hexaCor.indexOf('|');
        if (posHex != -1) hexaCor = hexaCor.substring(0, posHex);
        hexaCor.trim();
        nomesCores.push_back(nomeCor);
        hexaCores.push_back(hexaCor);
        Serial.print(F("Nova cor cadastrada: ")); Serial.println(nomeCor);
        EstadoSaida = '1';
        setarCorPraHex(hexaCor);
    } else {
        Serial.println(F("Erro no formato! Use: add|nome|#hexa"));
    }
}
 
void entrarModoCritico() {
    modoCritico = true;
    EstadoSaida = '1';
    Serial.println(F("*** MODO CRITICO ATIVADO ***"));
    setarCorPraHex("#FF0000");
    digitalWrite(buzzer_pin, HIGH);
}
 
void sairModoCritico() {
    modoCritico   = false;
    anomaliaAtiva = "";
    proximoBipe   = 0;
    noTone(buzzer_pin);
    digitalWrite(buzzer_pin, LOW);
    Serial.println(F("*** MODO ESTAVEL - Alerta encerrado ***"));
    setarCorPraHex("#00FF00");
    EstadoSaida = '1';
}
 