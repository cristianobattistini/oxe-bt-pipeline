"""Training loop with validation, checkpointing, and early stopping."""
import torch
from torch.optim import AdamW
from transformers import get_linear_schedule_with_warmup
from tqdm import tqdm
from torch.utils.tensorboard import SummaryWriter
import wandb
import os
from pathlib import Path
import logging

# FIXED: Absolute imports instead of relative
from utils import move_to_device, save_checkpoint, rotate_checkpoints

logger = logging.getLogger(__name__)


@torch.no_grad()
def evaluate(model, val_loader, device, writer=None, log_step=None, log_key="loss/val_epoch"):
    """
    Run validation and return average loss.
    
    Args:
        model: Model to evaluate
        val_loader: Validation data loader
        device: Device to run on
        writer: TensorBoard writer (optional)
        log_step: Step number for logging (optional)
        log_key: Key name for logging (default: "loss/val_epoch")
    
    Returns:
        float: Average validation loss, or None if val_loader is None
    """
    if val_loader is None:
        return None
    
    model.eval()
    total_loss, total_steps = 0.0, 0
    pbar_val = tqdm(val_loader, desc="Validating", dynamic_ncols=True, leave=False)
    
    for batch in pbar_val:
        batch = move_to_device(batch, device)
        
        # Cast pixel values to float32
        if "pixel_values" in batch and torch.is_tensor(batch["pixel_values"]):
            batch["pixel_values"] = batch["pixel_values"].to(torch.float32, non_blocking=True)
        
        outputs = model(**batch)
        loss = outputs.loss
        total_loss += loss.item()
        total_steps += 1
        
        pbar_val.set_postfix(val_loss=f"{loss.item():.4f}")
    
    val_loss = total_loss / max(1, total_steps)
    
    # Log to TensorBoard and W&B
    if log_step is not None:
        if writer is not None:
            writer.add_scalar(log_key, val_loss, log_step)
        
        wandb_step_key = "epoch" if "epoch" in log_key else "step"
        wandb.log({log_key: val_loss, wandb_step_key: log_step})
    
    model.train()
    return val_loss


class VLMTrainer:
    """
    Custom trainer for vision-language models with comprehensive features:
    - Gradient accumulation
    - Learning rate scheduling with warmup
    - Validation per epoch or per optimizer step
    - Early stopping
    - Checkpoint rotation
    - TensorBoard & W&B logging
    """
    
    def __init__(self, model, processor, train_loader, val_loader, train_config, lora_config, device="cuda"):
        self.model = model
        self.processor = processor
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.config = train_config
        self.lora_config = lora_config
        self.device = device
        
        # Setup directories (PLATFORM-AGNOSTIC)
        self.ckpt_dir = Path(train_config.checkpoint_dir or Path(train_config.output_dir) / "ckpts")
        self.best_dir = Path(train_config.output_dir) / "best"
        self.ckpt_dir.mkdir(parents=True, exist_ok=True)
        self.best_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup optimizer and scheduler
        self.optimizer = AdamW(model.parameters(), lr=train_config.lr)
        num_training_steps = len(train_loader) * train_config.epochs
        self.scheduler = get_linear_schedule_with_warmup(
            self.optimizer,
            num_warmup_steps=max(1, num_training_steps // 100),
            num_training_steps=num_training_steps,
        )
        
        # Setup logging
        log_dir = Path(train_config.log_dir or Path(train_config.output_dir) / "tblogs")
        log_dir.mkdir(parents=True, exist_ok=True)
        self.writer = SummaryWriter(log_dir=str(log_dir))
        
        # Training state
        self.global_step = 0
        self.optimizer_step = 0
        self.start_epoch = 0
        self.best_val = float("inf")
        self.bad_validations = 0
        self.use_lora = bool(lora_config.use_lora or lora_config.use_qlora)
        
        # Resume from checkpoint if specified
        if train_config.resume_from:
            self.resume_from_checkpoint(train_config.resume_from)
    
    def train_one_epoch(self, epoch: int):
        """
        Perform one complete training epoch through the entire training dataset.
        
        Args:
            epoch: Current epoch number (0-indexed)
        
        Returns:
            tuple: (average_loss, should_stop)
                - average_loss: Mean loss across all batches in the epoch
                - should_stop: Boolean indicating if training should stop (early stopping triggered)
        """
        self.model.train()
        epoch_loss_sum, epoch_steps = 0.0, 0
        stop_training = False
        
        pbar = tqdm(self.train_loader, dynamic_ncols=True, desc=f"Epoch {epoch+1}/{self.config.epochs}")
        
        for batch in pbar:
            batch = move_to_device(batch, self.device)
            
            # Cast pixel values to float32
            if "pixel_values" in batch and torch.is_tensor(batch["pixel_values"]):
                batch["pixel_values"] = batch["pixel_values"].to(torch.float32, non_blocking=True)
            
            # Forward pass
            outputs = self.model(**batch)
            loss = outputs.loss
            
            # Scale loss for gradient accumulation
            loss = loss / self.config.gradient_accumulation_steps
            loss.backward()
            
            # Accumulate metrics
            epoch_loss_sum += loss.item() * self.config.gradient_accumulation_steps
            epoch_steps += 1
            
            # Log batch loss
            actual_loss = loss.item() * self.config.gradient_accumulation_steps
            self.writer.add_scalar("loss/train_step", actual_loss, self.global_step)
            wandb.log({"loss/train_step": actual_loss, "step": self.global_step})
            
            # Update progress bar
            if self.global_step % 10 == 0:
                pbar.set_postfix(loss=f"{actual_loss:.4f}", opt_step=self.optimizer_step)
            
            # Optimizer step with gradient accumulation
            do_step = (self.global_step + 1) % self.config.gradient_accumulation_steps == 0
            if do_step:
                # Gradient clipping and optimizer update
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                self.optimizer.step()
                self.scheduler.step()
                self.optimizer.zero_grad(set_to_none=True)
                self.optimizer_step += 1
                
                # Log learning rate
                current_lr = self.scheduler.get_last_lr()[0]
                self.writer.add_scalar("lr", current_lr, self.optimizer_step)
                wandb.log({"lr": current_lr, "step": self.optimizer_step})
                
                # Checkpoint per optimizer steps
                if self.config.save_every_steps > 0 and self.optimizer_step % self.config.save_every_steps == 0:
                    self.save_checkpoint(f"step{self.optimizer_step:08d}", epoch)
                
                # Validation per optimizer steps (if configured)
                if self.should_validate_on_step():
                    stop_training = self.validate_and_check_early_stop(
                        log_step=self.optimizer_step,
                        log_key="loss/val_opt_step",
                        epoch=epoch
                    )
                    if stop_training:
                        break
            
            self.global_step += 1
        
        # Flush any remaining gradients (incomplete accumulation at end of epoch)
        if self.global_step % self.config.gradient_accumulation_steps != 0:
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()
            self.scheduler.step()
            self.optimizer.zero_grad(set_to_none=True)
            self.optimizer_step += 1
            logger.info("Flushed remaining gradients at end of epoch")
        
        # Calculate epoch metrics
        epoch_loss = epoch_loss_sum / max(1, epoch_steps)
        return epoch_loss, stop_training
    
    def validate_one_epoch(self, epoch: int):
        """
        Perform one complete validation epoch through the entire validation dataset.
        
        Args:
            epoch: Current epoch number (0-indexed)
        
        Returns:
            float: Average validation loss, or None if no validation set
        """
        if self.val_loader is None:
            return None
        
        logger.info(f"VAL: Running validation at epoch {epoch+1}")
        val_loss = evaluate(
            self.model,
            self.val_loader,
            self.device,
            self.writer,
            log_step=epoch + 1,
            log_key="loss/val_epoch"
        )
        logger.info(f"VAL: Epoch {epoch+1} | val_loss={val_loss:.4f}")
        return val_loss
    
    def fit(self):
        """
        Main training loop that orchestrates training, validation, checkpointing, and early stopping.
        
        This method:
        - Iterates through epochs
        - Calls train_one_epoch() for each epoch
        - Validates at configured intervals
        - Handles early stopping based on validation loss
        - Saves checkpoints and best model
        - Logs metrics to TensorBoard and W&B
        
        Returns:
            None (model is trained in-place)
        """
        # Initialize model for training
        self.model.config.use_cache = False
        self.model.gradient_checkpointing_enable()
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True)
        
        logger.info(f"Starting training for {self.config.epochs} epochs")
        logger.info(f"Total batches per epoch: {len(self.train_loader)}")
        logger.info(f"Gradient accumulation steps: {self.config.gradient_accumulation_steps}")
        logger.info(f"Effective batch size: {self.config.batch_size * self.config.gradient_accumulation_steps}")
        
        # Main training loop
        for epoch in range(self.start_epoch, self.config.epochs):
            logger.info("=" * 60)
            logger.info(f"Epoch {epoch+1}/{self.config.epochs}")
            logger.info("=" * 60)
            
            # Train for one epoch
            epoch_loss, should_stop = self.train_one_epoch(epoch)
            
            # Log epoch metrics
            self.writer.add_scalar("loss/train_epoch", epoch_loss, epoch)
            wandb.log({"loss/train_epoch": epoch_loss, "epoch": epoch})
            logger.info(f"Epoch {epoch+1} complete | avg_loss={epoch_loss:.4f}")
            
            # Early stop triggered during training (from step-level validation)
            if should_stop:
                logger.info("Early stopping triggered during epoch")
                break
            
            # Epoch-level validation (if configured)
            if self.should_validate_on_epoch(epoch):
                val_loss = self.validate_one_epoch(epoch)
                if val_loss is not None:
                    should_stop = self.check_early_stopping(val_loss, epoch)
                    if should_stop:
                        logger.info(f"Early stopping triggered after epoch {epoch+1}")
                        tag = f"epoch{epoch+1:03d}_early_stop"
                        self.save_checkpoint(tag, epoch + 1)
                        break
            
            # Checkpoint per epoch (if configured)
            if self.should_checkpoint_on_epoch(epoch):
                self.save_checkpoint(f"epoch{epoch+1:03d}", epoch + 1)
        
        # Final save
        logger.info("Training complete. Saving final model...")
        self.model.save_pretrained(str(self.config.output_dir))
        self.processor.save_pretrained(str(self.config.output_dir))
        
        # Cleanup
        self.writer.close()
        wandb.finish()
        logger.info(f"✓ Final model saved to {self.config.output_dir}")
        logger.info(f"✓ Best model saved to {self.best_dir} | val_loss={self.best_val:.4f}")
    
    def should_validate_on_step(self) -> bool:
        """Check if validation should run at this optimizer step."""
        return (self.val_loader is not None and
                self.config.val_every_opt_steps > 0 and
                self.optimizer_step % self.config.val_every_opt_steps == 0)
    
    def should_validate_on_epoch(self, epoch: int) -> bool:
        """Check if validation should run at this epoch."""
        return (self.val_loader is not None and
                self.config.val_every_opt_steps == 0 and  # Only if step-level validation is disabled
                (epoch + 1) % self.config.val_every == 0)
    
    def should_checkpoint_on_epoch(self, epoch: int) -> bool:
        """Check if checkpoint should be saved at this epoch."""
        return (self.config.save_every_epochs > 0 and
                (epoch + 1) % self.config.save_every_epochs == 0)
    
    def validate_and_check_early_stop(self, log_step: int, log_key: str, epoch: int) -> bool:
        """
        Run validation and check early stopping condition.
        
        Args:
            log_step: Step number for logging
            log_key: Logging key (e.g., "loss/val_opt_step")
            epoch: Current epoch number
        
        Returns:
            bool: True if training should stop, False otherwise
        """
        logger.info(f"VAL: Running validation at {log_key.split('/')[-1]} {log_step}")
        val_loss = evaluate(
            self.model,
            self.val_loader,
            self.device,
            self.writer,
            log_step,
            log_key
        )
        logger.info(f"VAL: {log_key.split('/')[-1]} {log_step} | val_loss={val_loss:.4f}")
        return self.check_early_stopping(val_loss, epoch)
    
    def check_early_stopping(self, val_loss: float, epoch: int) -> bool:
        """
        Check early stopping condition and save best model if improved.
        
        Args:
            val_loss: Current validation loss
            epoch: Current epoch number
        
        Returns:
            bool: True if early stopping is triggered, False otherwise
        """
        if val_loss < self.best_val:
            # New best model
            self.best_val = val_loss
            self.bad_validations = 0
            
            # Save best model
            self.model.save_pretrained(str(self.best_dir))
            self.processor.save_pretrained(str(self.best_dir))
            logger.info(f"✓ New best model saved | val_loss={self.best_val:.4f}")
            return False  # Continue training
        else:
            # No improvement
            self.bad_validations += 1
            logger.info(f"No improvement. Patience: {self.bad_validations}/{self.config.patience}")
            
            # Check if patience exhausted
            if self.config.patience > 0 and self.bad_validations >= self.config.patience:
                logger.warning(f"⚠ Early stopping triggered after {self.bad_validations} validations without improvement")
                return True  # Stop training
            
            return False  # Continue training
    
    def save_checkpoint(self, tag: str, epoch: int):
        """
        Save checkpoint and rotate old ones.
        
        Args:
            tag: Checkpoint name/tag
            epoch: Current epoch number
        """
        save_checkpoint(
            tag,
            self.model,
            self.processor,
            self.optimizer,
            self.scheduler,
            self.global_step,
            epoch,
            str(self.ckpt_dir),
            self.use_lora
        )
        rotate_checkpoints(str(self.ckpt_dir), self.config.keep_last_k)
    
    def resume_from_checkpoint(self, resume_path: str):
        """
        Load training state from checkpoint to resume training.
        
        Args:
            resume_path: Path to checkpoint directory
        """
        from utils import load_checkpoint_if_any
        
        logger.info(f"Attempting to resume from: {resume_path}")
        
        # Load model, optimizer, scheduler states
        _, self.optimizer, self.scheduler, loaded_step, loaded_epoch = load_checkpoint_if_any(
            self.model,
            resume_path,
            self.optimizer,
            self.scheduler,
            self.device,
            self.use_lora
        )
        
        # Update training state
        self.optimizer_step = loaded_step
        self.start_epoch = loaded_epoch
        self.global_step = loaded_step * self.config.gradient_accumulation_steps
        
        logger.info(f"✓ Resumed | epoch={loaded_epoch}, optimizer_step={loaded_step}, global_step={self.global_step}")
