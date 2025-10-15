#!/bin/bash
set -euo pipefail

IMAGE="battistini/oxe-vlm:dev"

# posizionati nella cartella del Dockerfile
cd "$(dirname "$0")"   # -> vlm_ft/docker

docker build \
  --build-arg USER_UID="$(id -u)" \
  --build-arg USER_GID="$(id -g)" \
  -t "$IMAGE" \
  -f Dockerfile \
  .

echo "✅ Immagine creata: $IMAGE"
