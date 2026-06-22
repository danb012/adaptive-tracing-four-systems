#!/bin/zsh
set -euo pipefail

cd /Users/dan

if [ ! -d quickpizza ]; then
  git clone https://github.com/grafana/quickpizza.git
fi

cd quickpizza
docker compose -f compose.grafana-local-stack.microservices.yaml up -d

echo "QuickPizza setup started."
echo "App: http://localhost:3333"
echo "Grafana: http://localhost:3000"
echo

docker compose -f compose.grafana-local-stack.microservices.yaml ps
