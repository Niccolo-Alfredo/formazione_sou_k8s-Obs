from flask import Flask, jsonify, request, render_template_string
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
import os
import time
import threading
import random
import psutil

# Configurazione OpenTelemetry
resource = Resource(attributes={SERVICE_NAME: "my-flask-app"})
otlp_endpoint = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "http://otel-collector.monitoring.svc.cluster.local:4317"
)

# Riduce l'intervallo di export a 5 secondi (default è 60)
metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
    export_interval_millis=5000  # Export ogni 5 secondi
)

meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

# Crea il meter
meter = metrics.get_meter(__name__)

# Metriche contatori
http_requests_counter = meter.create_counter(
    name="app_http_requests_total",
    description="Numero totale di richieste HTTP per endpoint"
)
button_clicks_counter = meter.create_counter(
    name="app_button_clicks_total",
    description="Numero totale di click sui pulsanti"
)

# Processo monitorato con psutil
process = psutil.Process()

# Variabili globali per memorizzare i valori delle metriche
current_cpu_usage = 0.0
current_memory_usage = 0.0

# Callback per metriche osservabili - devono essere thread-safe
def cpu_callback(options):
    try:
        cpu_percent = process.cpu_percent(interval=None)
        # Aggiorna la variabile globale per debugging
        global current_cpu_usage
        current_cpu_usage = cpu_percent
        print(f"[DEBUG] CPU callback: {cpu_percent}%")
        yield metrics.Observation(cpu_percent, {})
    except Exception as e:
        print(f"[ERROR] CPU callback error: {e}")
        yield metrics.Observation(0.0, {})

def memory_callback(options):
    try:
        memory_percent = process.memory_percent()
        # Aggiorna la variabile globale per debugging
        global current_memory_usage
        current_memory_usage = memory_percent
        print(f"[DEBUG] Memory callback: {memory_percent}%")
        yield metrics.Observation(memory_percent, {})
    except Exception as e:
        print(f"[ERROR] Memory callback error: {e}")
        yield metrics.Observation(0.0, {})

# Gauge osservabili con callback
cpu_usage_gauge = meter.create_observable_gauge(
    name="app_cpu_usage_percent",
    description="Utilizzo CPU del processo Flask",
    callbacks=[cpu_callback]
)
memory_usage_gauge = meter.create_observable_gauge(
    name="app_memory_usage_percent", 
    description="Utilizzo memoria del processo Flask",
    callbacks=[memory_callback]
)

# Simulazione traffico HTTP e click
def simulate_traffic():
    while True:
        try:
            # Richieste HTTP simulate
            http_requests_counter.add(random.randint(1, 3), {"endpoint": "/"})
            # Click casuali
            if random.random() < 0.7:  # Aumenta probabilità per più dati
                color = random.choice(["green", "blue", "red"])
                button_clicks_counter.add(1, {"color": color})
            print(f"[DEBUG] Simulated traffic - CPU: {current_cpu_usage}%, Memory: {current_memory_usage}%")
        except Exception as e:
            print(f"[ERROR] Traffic simulation error: {e}")
        time.sleep(3)

# Thread per forzare la lettura delle metriche CPU
def cpu_monitor():
    """Thread dedicato per aggiornare regolarmente la CPU"""
    while True:
        try:
            # Forza la lettura della CPU con un intervallo
            process.cpu_percent(interval=1)
        except Exception as e:
            print(f"[ERROR] CPU monitor error: {e}")
        time.sleep(2)

# Flush periodico per forzare export delle metriche
def periodic_flush():
    flush_counter = 0
    while True:
        try:
            # Force flush del meter provider
            if meter_provider.force_flush(timeout_millis=5000):
                flush_counter += 1
                print(f"[DEBUG] Metrics flushed successfully #{flush_counter}")
            else:
                print("[WARNING] Metrics flush timeout")
        except Exception as e:
            print(f"[ERROR] Force flush error: {e}")
        time.sleep(10)  # Flush ogni 10 secondi

# Avvia tutti i thread
print("[INFO] Starting background threads...")
threading.Thread(target=simulate_traffic, daemon=True).start()
threading.Thread(target=cpu_monitor, daemon=True).start()  
threading.Thread(target=periodic_flush, daemon=True).start()

# Configura Flask
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

# HTML con più funzionalità di test
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>App con Metriche OpenTelemetry</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        button { margin: 10px; padding: 10px 20px; font-size: 16px; }
        .green { background-color: #4CAF50; color: white; }
        .blue { background-color: #2196F3; color: white; }
        .red { background-color: #f44336; color: white; }
        .stats { margin-top: 20px; padding: 15px; background-color: #f0f0f0; }
    </style>
</head>
<body>
    <h1>Dashboard Demo con OpenTelemetry</h1>
    <p>Metriche reali di CPU e memoria + traffico simulato!</p>
    
    <h3>Test Button Clicks:</h3>
    <button class="green" onclick="clickButton('green')">Pulsante Verde</button>
    <button class="blue" onclick="clickButton('blue')">Pulsante Blu</button>
    <button class="red" onclick="clickButton('red')">Pulsante Rosso</button>
    
    <div class="stats">
        <h3>Status Corrente:</h3>
        <div id="status">Caricamento...</div>
        <button onclick="loadStatus()">Aggiorna Status</button>
        <button onclick="generateLoad()">Genera Carico CPU</button>
    </div>
    
    <script>
        async function clickButton(color) {
            try {
                const response = await fetch(`/click?button_color=${color}`);
                const data = await response.json();
                console.log(`Button ${color} clicked:`, data);
            } catch (error) {
                console.error('Error clicking button:', error);
            }
        }
        
        async function loadStatus() {
            try {
                const response = await fetch('/status');
                const data = await response.json();
                document.getElementById('status').innerHTML = 
                    `CPU: ${data.cpu_usage.toFixed(2)}% | Memory: ${data.memory_usage.toFixed(2)}%`;
            } catch (error) {
                document.getElementById('status').innerHTML = 'Errore nel caricamento';
                console.error('Error loading status:', error);
            }
        }
        
        async function generateLoad() {
            await fetch('/load');
            setTimeout(loadStatus, 1000);
        }
        
        // Aggiorna automaticamente lo status ogni 3 secondi
        setInterval(loadStatus, 3000);
        loadStatus(); // Carica subito
    </script>
</body>
</html>
"""

@app.route("/")
def hello_world():
    # Registra la metrica per questa richiesta
    http_requests_counter.add(1, {"endpoint": "/", "method": "GET"})
    return render_template_string(HTML_PAGE)

@app.route("/click")
def handle_click():
    color = request.args.get("button_color", "unknown")
    try:
        button_clicks_counter.add(1, {"color": color})
        print(f"[INFO] Button click registered: {color}")
        return jsonify({"status": "ok", "button_color": color})
    except Exception as e:
        print(f"[ERROR] Button click error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/status")
def status():
    try:
        cpu_usage = process.cpu_percent(interval=None)
        memory_usage = process.memory_percent()
        
        # Registra anche come counter le richieste di status
        http_requests_counter.add(1, {"endpoint": "/status", "method": "GET"})
        
        return jsonify({
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "process_id": process.pid,
            "timestamp": time.time()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/load")
def generate_load():
    """Endpoint per generare carico CPU artificiale"""
    try:
        # Genera carico CPU per 2 secondi
        start_time = time.time()
        while time.time() - start_time < 2:
            _ = sum(i * i for i in range(100000))
        
        http_requests_counter.add(1, {"endpoint": "/load", "method": "GET"})
        return jsonify({"status": "load_generated", "duration": 2})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "my-flask-app",
        "timestamp": time.time()
    })

if __name__ == "__main__":
    print("[INFO] Starting Flask app with OpenTelemetry metrics...")
    print(f"[INFO] OTLP Endpoint: {otlp_endpoint}")
    print("[INFO] Metrics will be exported every 5 seconds")
    app.run(host="0.0.0.0", port=5000, debug=False)