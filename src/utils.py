"""Utility functions for checkpointing, logging, device management."""
import os
import shutil
import random
import logging
from pathlib import Path
import torch

logger = logging.getLogger(__name__)

def set_seeds(seed: int = 42):
    """Set all random seeds for reproducibility."""
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    logger.info(f"Set random seed to {seed}")

def setup_logging(log_file: str = None, level=logging.INFO):
    """Configure logging to console and optionally to file."""
    handlers = [logging.StreamHandler()]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )

def safe_makedirs(path: str):
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)

def move_to_device(batch, device):
    """Recursively move tensors to device."""
    if torch.is_tensor(batch):
        return batch.to(device, non_blocking=True)
    if isinstance(batch, dict):
        return {k: move_to_device(v, device) for k, v in batch.items()}
    if isinstance(batch, (list, tuple)):
        return type(batch)(move_to_device(x, device) for x in batch)
    return batch

def rotate_checkpoints(ckpt_dir: str, keep_last_k: int):
    """Remove old checkpoints, keeping only the most recent K."""
    if keep_last_k <= 0 or not os.path.isdir(ckpt_dir):
        return
    
    subdirs = sorted(
        [d for d in os.listdir(ckpt_dir) if os.path.isdir(os.path.join(ckpt_dir, d))],
        key=lambda x: os.path.getmtime(os.path.join(ckpt_dir, x))
    )
    
    if len(subdirs) <= keep_last_k:
        return
    
    for d in subdirs[:-keep_last_k]:
        try:
            shutil.rmtree(os.path.join(ckpt_dir, d), ignore_errors=True)
            logger.info(f"Removed old checkpoint: {d}")
        except Exception as e:
            logger.warning(f"Failed to remove {d}: {e}")

def save_checkpoint(
    tag: str, model, processor, optimizer, scheduler,
    global_step: int, epoch: int, ckpt_dir: str, use_lora: bool
):
    """Save model checkpoint with training state."""
    path = os.path.join(ckpt_dir, tag)
    safe_makedirs(path)
    
    # Save model weights/adapters
    model.save_pretrained(path)
    processor.save_pretrained(path)
    
    # Save trainer state
    state = {
        "global_step": int(global_step),
        "epoch": int(epoch),
        "optimizer": optimizer.state_dict() if optimizer is not None else None,
        "scheduler": scheduler.state_dict() if scheduler is not None else None,
        "rng": torch.get_rng_state(),
    }
    
    if torch.cuda.is_available():
        state["cuda_rng"] = torch.cuda.get_rng_state_all()
    
    torch.save(state, os.path.join(path, "trainer_state.pt"))
    
    # Create 'latest' symlink
    latest = os.path.join(ckpt_dir, "latest")
    try:
        if os.path.islink(latest) or os.path.exists(latest):
            if os.path.islink(latest):
                os.unlink(latest)
            elif os.path.isdir(latest):
                shutil.rmtree(latest)
            else:
                os.remove(latest)
        os.symlink(path, latest, target_is_directory=True)
    except Exception as e:
        logger.warning(f"Failed to create symlink: {e}")
    
    logger.info(f"Saved checkpoint: {tag}")

def load_checkpoint_if_any(
    model, resume_path: str, optimizer=None, scheduler=None,
    device="cuda", use_lora=True
):
    """Load checkpoint and restore training state."""
    if resume_path is None:
        return model, optimizer, scheduler, 0, 0
    
    # Load model weights/adapters
    if use_lora:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, resume_path, is_trainable=True)
    else:
        sd = torch.load(os.path.join(resume_path, "pytorch_model.bin"), map_location=device)
        model.load_state_dict(sd, strict=False)
    
    # Load trainer state
    trainer_state_path = os.path.join(resume_path, "trainer_state.pt")
    start_step, start_epoch = 0, 0
    
    if os.path.exists(trainer_state_path):
        st = torch.load(trainer_state_path, map_location=device)
        start_step = int(st.get("global_step", 0))
        start_epoch = int(st.get("epoch", 0))
        
        if optimizer is not None and st.get("optimizer") is not None:
            optimizer.load_state_dict(st["optimizer"])
        
        if scheduler is not None and st.get("scheduler") is not None:
            scheduler.load_state_dict(st["scheduler"])
        
        try:
            torch.set_rng_state(st["rng"])
            if torch.cuda.is_available() and "cuda_rng" in st:
                torch.cuda.set_rng_state_all(st["cuda_rng"])
        except Exception as e:
            logger.warning(f"Failed to restore RNG state: {e}")
    
    logger.info(f"Resumed from {resume_path} (epoch={start_epoch}, step={start_step})")
    return model, optimizer, scheduler, start_step, start_epoch
