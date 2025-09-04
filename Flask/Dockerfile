# Usa Python slim come base
FROM python:3.11-slim

# Imposta working dir
WORKDIR /app

# Installa dipendenze di sistema (necessarie per psutil)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia i file dell'app
COPY app.py /app/

# Installa le dipendenze Python
RUN pip install --no-cache-dir \
    flask \
    psutil \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-flask

# Espone la porta Flask
EXPOSE 5000

# Avvia l'app
CMD ["python", "app.py"]
