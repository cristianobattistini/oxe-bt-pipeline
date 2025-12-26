# OXE‑BT Pipeline

Pipeline per trasformare episodi **Open‑X‑Embodiment (OXE)** in un dataset composto da **istruzione + evidenza visiva + Behavior Tree (BehaviorTree.CPP XML)**, usato per fine‑tuning LoRA di piccoli **Vision‑Language Model** (proposer) e per sperimentazione in simulazione (BEHAVIOR‑1K / OmniGibson).

Documentazione completa (cartelle `nb/`, `processing/`, `data/`, `data/dataset/`, `data/library/` + integrazione BEHAVIOR‑1K): `DOCUMENTAZIONE.md`.

## Struttura (essenziale)

- `processing/`: export OXE (TFDS/RLDS), selezione frame, costruzione struttura dataset, video/contact sheet
- `data/dataset/`: dataset episodio‑level (prompt + frames + bt.xml + meta.json + locals)
- `data/library/`: node library (vocabolario BT: nodi, porte, value bins)
- `nb/`: notebook Colab per fine‑tuning LoRA (SmolVLM2, Gemma3, Qwen2.5‑VL, Qwen3‑VL) + eval/push
- `dataset_oxe.zip` / `dataset_oxe/`: dataset JSONL + immagini usato nei notebook

## Quickstart (minimo)

- Export episodi OXE: `python processing/main.py` (config in `processing/utils/config.py`; setup WSL: `SETUP_WINDOWS_WSL_DOCKER.md`)
- Costruzione dataset episode‑level: `python processing/generate_folders.py --mode init ...`
- Fine‑tuning: apri i notebook in `nb/` e usa `dataset_oxe.zip`


