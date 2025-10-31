#!/bin/bash
# ===============================================================
# AVVIO DEL CONTAINER (stile Toy Example, adattato a Westworld)
# ===============================================================
set -e

IMAGE="battistini/oxe-vlm:cuda12.1-py23"
NAME="battistini_vlm_ft"

# GPU e CPU prenotate (modifica se necessario)
GPU="${GPU:-all}"
CPUSET="${CPUSET:-96-111}"

# Percorsi locali (multiverse)
CODE_DIR="/home/battistini/storage/oxe-bt-pipeline"
DATA_DIR="/home/battistini/datasets/private"

docker run -d --rm -it \
  --gpus "${GPU}" \
  --cpuset-cpus "${CPUSET}" \
  --mount type=bind,source="${CODE_DIR}",target=/home/battistini/exp \
  --mount type=bind,source="${DATA_DIR}",target=/home/battistini/exp/private_datasets \
  -w /home/battistini/exp \
  -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) \
  -u $(id -u):$(id -g) \
  --name "${NAME}" "${IMAGE}"

echo "✅ Container started: ${NAME}"
echo "👉  Enter with: docker exec -it ${NAME} bash"
