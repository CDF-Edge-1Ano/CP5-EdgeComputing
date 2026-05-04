async function carregarDados() {
    const response = await fetch('/dados');
    const data = await response.json();

    atualizarEstado(data);

    const tempos = data.temperature.map(e => e.recvTime);
    const temperaturas = data.temperature.map(e => e.attrValue);
    const umidades = data.humidity.map(e => e.attrValue);
    const luminosidade = data.luminosity.map(e => e.attrValue);

    atualizarGrafico(tempChart, tempos, temperaturas);
    atualizarGrafico(humChart, tempos, umidades);
    atualizarGrafico(lumChart, tempos, luminosidade);
}

function criarGrafico(ctx, label) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: []
            }]
        }
    });
}

function atualizarGrafico(chart, labels, dados, label) {
    chart.data.labels = labels;
    chart.data.datasets[0].data = dados;
    chart.update();
}

const tempChart = criarGrafico(document.getElementById('tempChart'), 'Temperatura');
const humChart = criarGrafico(document.getElementById('humChart'), 'Umidade');
const lumChart = criarGrafico(document.getElementById('lumChart'), 'Luminosidade');

setInterval(carregarDados, 2000); 

function atualizarEstado(data) {
    const div = document.getElementById("estadoAtual");

    const temp = data.temperature.at(-1)?.attrValue;
    const hum = data.humidity.at(-1)?.attrValue;
    const lum = data.luminosity.at(-1)?.attrValue;
    const estado = data.estado;

    let cor = "green";
    let texto = "ESTÁVEL";

    if (estado !== "estavel") {
        cor = "red";
        texto = "CRÍTICO ";
    }

   div.innerHTML = `
    <h3 style="color:${cor}">${texto}</h3>
    <div class="metricas">
        <p> Temp: ${temp}°C</p>
        <p> Umidade: ${hum}%</p>
        <p> Luminosidade: ${lum}%</p>
    </div>`;
}