#!/bin/bash

# Uscita immediata se un comando fallisce
set -e

# --- 1. Distruzione e Pulizia ---

echo "Distruzione del cluster Kind esistente e pulizia dei file di configurazione..."
kind delete cluster --name obs-cluster || true
rm -f config ~/.kube/config

# --- 2. Ricreazione del Cluster e Configurazione Base ---

echo "Ricreazione del cluster Kind da kind-config.yaml..."
kind create cluster --config kind-config.yaml

echo "Generazione e configurazione di kubeconfig per l'utente admin..."
# Salva il kubeconfig originale in una directory temporanea
KIND_CONFIG=$(kind get kubeconfig --name obs-cluster)

echo "${KIND_CONFIG}" > ~/.kube/config

# Crea una copia del kubeconfig originale e sostituisci 0.0.0.0 con 10.0.0.2
echo "${KIND_CONFIG}" | sed 's/0.0.0.0/10.0.0.2/' > config

echo "Il file di configurazione per l'admin è stato creato: config"
echo "-------------------------------------------------------------------------"

# --- 3. Installazione e Configurazione di NGINX Ingress Controller ---

echo "Installazione di NGINX Ingress Controller..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/kind/deploy.yaml

echo "Etichettatura del nodo 'control-plane' per lo scheduling di ingress..."
kubectl label nodes obs-cluster-control-plane ingress-ready=true

# Attendi che il pod dell'ingress controller sia pronto
echo "Attendo che il pod 'ingress-nginx-controller' sia in stato Running..."
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

echo "-------------------------------------------------------------------------"

# --- 4. Definizione Prometheus/Grafana ---

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace
kubectl apply -f prometheus-ingress.yaml
kubectl apply -f grafana-ingress.yaml

kubectl get secret --namespace monitoring prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo

# Credeziali di default Username: admin / Password: prom-operator

echo "-------------------------------------------------------------------------"

echo "# https://prometheus.example.com"
echo "# https://grafana.example.com"

echo "-------------------------------------------------------------------------"

# --- 5. Deploy di OpenTelemetry Collector, Operator-prom, Web App Flask ---

kubectl apply -f otel-collector-final.yaml
kubectl apply -f operator-prom.yaml
kubectl apply -f app.yaml