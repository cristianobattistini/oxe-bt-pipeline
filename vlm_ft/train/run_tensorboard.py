#!/usr/bin/env python3
import argparse, os, sys, subprocess

def main():
    ap = argparse.ArgumentParser(description="Avvia TensorBoard su una directory di log.")
    ap.add_argument("--logdir", required=True, help="Directory con i log di TensorBoard (SummaryWriter).")
    ap.add_argument("--port", type=int, default=6006, help="Porta di ascolto (default: 6006).")
    ap.add_argument("--host", default="0.0.0.0", help="Host da bindare (default: 0.0.0.0).")
    args = ap.parse_args()

    if not os.path.isdir(args.logdir):
        print(f"ERRORE: logdir non esiste: {args.logdir}", file=sys.stderr)
        sys.exit(1)

    # Controlla che TensorBoard sia installato
    try:
        import tensorboard  # noqa: F401
    except Exception:
        print("TensorBoard non è installato. Installo: pip install tensorboard", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tensorboard"])

    cmd = [
        sys.executable, "-m", "tensorboard.main",
        "--logdir", args.logdir,
        "--bind_all",
        "--port", str(args.port),
    ]
    print(f"Avvio TensorBoard su http://{args.host}:{args.port}  (logdir: {args.logdir})")
    os.execvp(cmd[0], cmd)

if __name__ == "__main__":
    main()
