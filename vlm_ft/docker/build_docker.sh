#!/bin/bash
set -e

IMAGE="battistini/oxe-vlm:cuda12.1-py23"

cd "$(dirname "$0")"/..

# Passa UID e GID al build
docker build \
  --build-arg USER_UID=$(id -u) \
  --build-arg USER_GID=$(id -g) \
  -t "$IMAGE" -f docker/Dockerfile .

echo "✅ Immagine creata: $IMAGE"
