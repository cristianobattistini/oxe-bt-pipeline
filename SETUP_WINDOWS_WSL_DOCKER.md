# Setup su Windows con WSL2 + Ubuntu (senza Docker) per `/processing`

Obiettivo: far girare `processing/main.py` (download/conversione dataset OXE/RLDS) su Windows usando solo WSL2+Ubuntu. GPU **non** richiesta.

## Prerequisiti (host Windows)
- Windows 10/11, virtualizzazione attiva nel BIOS.
- Diritti admin.
- Spazio disco: molte decine di GB per TFDS/HF cache (consigliato in Documents).

## 1) Abilita WSL2 e installa Ubuntu
PowerShell come amministratore:
```powershell
wsl --install -d Ubuntu
wsl --set-default-version 2
```
Riavvia se richiesto. Apri Ubuntu, crea utente/password, poi aggiorna:
```bash
sudo apt update && sudo apt upgrade -y
```
Verifica WSL v2:
```powershell
wsl -l -v   # deve mostrare "Ubuntu" versione 2
```

## 2) Prepara le cartelle dati su Windows (host)
Scegli dove tenere dataset e cache, ad esempio:
```
C:\Users\<USER>\Documents\tensorflow_datasets
C:\Users\<USER>\Documents\hf_cache
```
Se hai già i dataset OXE, copiali in `C:\Users\<USER>\Documents\tensorflow_datasets`.

## 3) Installa dipendenze di sistema in Ubuntu (WSL)
```bash
sudo apt update && sudo apt install -y \
  ffmpeg libsm6 libxext6 libgl1 libglib2.0-0
```

## 4) Installa micromamba (oppure usa conda/mambaforge)
Micromamba stand-alone:
```bash
cd /tmp
curl -L https://micromamba.snakepit.net/api/micromamba/linux-64/latest | sudo tar -xj -C /usr/local/bin --strip-components=1 bin/micromamba
micromamba --help   # verifica che sia nel PATH
```

## 5) Clona il repo in Ubuntu (WSL)
```bash
cd ~
git clone /percorso/del/repo oxe-bt-pipeline   # o da HTTPS
cd oxe-bt-pipeline
```

## 6) Crea l’ambiente Python e installa le dipendenze
```bash
micromamba create -y -n oxe-bt-pipeline python=3.10 pip
micromamba run -n oxe-bt-pipeline pip install --no-cache-dir -r requirement.txt
# In alternativa: micromamba env create -n oxe-bt-pipeline -f environment.yml
```

## 7) Imposta le variabili d’ambiente (path dati/cache)
Adatta `<USER>` con il tuo utente Windows:
```bash
export TFDS_DATA_DIR=/mnt/c/Users/<USER>/Documents/tensorflow_datasets
export HF_HOME=/mnt/c/Users/<USER>/Documents/hf_cache
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
export TRANSFORMERS_CACHE=$HF_HOME/transformers
```
Suggerito: aggiungi queste righe a `~/.bashrc` per renderle permanenti.

## 8) Esegui la pipeline
```bash
cd ~/oxe-bt-pipeline
micromamba run -n oxe-bt-pipeline python processing/main.py
```
Nota: `processing/utils/config.py` legge `TFDS_DATA_DIR` e ha default esemplificativo `/mnt/c/Users/<USER>/Documents/tensorflow_datasets`. Se l’hai esportata, non devi toccare il file.

## 9) Run successivi
Ogni volta:
```bash
cd ~/oxe-bt-pipeline
micromamba run -n oxe-bt-pipeline python processing/main.py
```
(Se hai messo le variabili in `~/.bashrc`, non devi riesportarle.)

## Aprire il progetto con VS Code (Windows)
- Installa VS Code su Windows e l’estensione “Remote - WSL”.
- Apri VS Code → `Ctrl+Shift+P` → “WSL: Connect to WSL” → “Open Folder” → scegli `\\wsl$\\Ubuntu\\home\\<il_tuo_utente>\\oxe-bt-pipeline`.
- Così lavori sul codice che sta in WSL (più veloce), con tutte le estensioni (Python, Pylance, ecc.).

## Dove salvare e trovare gli output
- L’output è controllato da `out_root` in `processing/utils/config.py` (default: `out_temp` dentro al repo).
- Se vuoi che gli output siano subito visibili da Windows senza copiare, imposta `out_root` a un percorso Windows montato in WSL, es.:
  ```python
  out_root = "/mnt/c/Users/<USER>/Documents/oxe_outputs"
  ```
  Sostituisci `<USER>` e crea la cartella se non esiste.
- In alternativa, lascia `out_temp` in WSL e, quando finito, copia dove serve:
  ```bash
  cp -r ~/oxe-bt-pipeline/out_temp /mnt/c/Users/<USER>/Documents/oxe_outputs
  ```
  oppure usa VS Code/Explorer su `\\wsl$` per trascinare la cartella.

## Troubleshooting rapido
- **Path TFDS errato**: controlla `echo $TFDS_DATA_DIR` e che esista in `/mnt/c/...`.
- **Dipendenze mancanti**: riesegui `micromamba run -n oxe-bt-pipeline pip install -r requirement.txt`.
- **Permessi su cache**: usa l’utente normale (non root) in WSL; le cartelle Windows montate su `/mnt/c/...` sono già accessibili.
