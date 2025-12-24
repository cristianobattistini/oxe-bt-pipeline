FROM mambaorg/micromamba:1.5.8-bullseye

USER root

# Dipendenze di sistema minime per OpenCV/ffmpeg e runtime ML CPU
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libsm6 \
        libxext6 \
        libgl1 \
        libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Crea la cartella dati (verrà montata da host) e assegna permessi all'utente non-root
RUN mkdir -p /data /workspace && chown -R 1000:1000 /data /workspace

# Attiva l'env micromamba dentro i RUN e crea l'ambiente con python+pip, poi installa requirement.txt
ENV MAMBA_DOCKERFILE_ACTIVATE=1
COPY requirement.txt /tmp/requirements.txt
RUN micromamba create -y -n oxe-bt-pipeline python=3.10 pip && \
    micromamba run -n oxe-bt-pipeline pip install --no-cache-dir -r /tmp/requirements.txt && \
    micromamba clean -a -y

# Variabili d'ambiente utili per cache e TFDS (modificabili al run)
ENV PATH="/opt/conda/envs/oxe-bt-pipeline/bin:${PATH}" \
    CONDA_DEFAULT_ENV=oxe-bt-pipeline \
    TFDS_DATA_DIR=/data/tensorflow_datasets \
    HF_HOME=/data/hf \
    HUGGINGFACE_HUB_CACHE=/data/hf/hub \
    TRANSFORMERS_CACHE=/data/hf/transformers \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace
USER mambauser

CMD ["bash"]
