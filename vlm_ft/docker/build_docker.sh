#!/bin/bash
set -e

IMAGE="battistini/oxe-vlm:cuda12.1-py23"

# usa la cartella del Dockerfile come contesto
cd "$(dirname "$0")"   # ora sei in vlm_ft/docker

docker build \
  --build-arg USER_UID=$(id -u) \
  --build-arg USER_GID=$(id -g) \
  -t "$IMAGE" \
  -f Dockerfile \
  .

echo "✅ Immagine creata: $IMAGE"
