"""Configuration dataclasses for training and inference."""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ModelConfig:
    """Model architecture and loading."""
    model_id: str = "HuggingFaceTB/SmolVLM2-2.2B-Instruct"
    use_flash_attention: bool = False  # Set to "eager" for compatibility
    trust_remote_code: bool = True

@dataclass
class LoRAConfig:
    """LoRA/QLoRA adapter configuration."""
    use_lora: bool = False
    use_qlora: bool = False
    r: int = 16
    lora_alpha: Optional[int] = None  # If None, defaults to r
    lora_dropout: float = 0.1
    target_modules: List[str] = field(default_factory=lambda: [
        'down_proj', 'o_proj', 'k_proj', 'q_proj', 'gate_proj', 'up_proj', 'v_proj'
    ])
    use_dora: bool = True  # Disabled for QLoRA
    init_lora_weights: str = "gaussian"

@dataclass
class TrainingConfig:
    """Training loop hyperparameters."""
    batch_size: int = 1
    epochs: int = 1
    lr: float = 2e-4
    gradient_accumulation_steps: int = 16
    num_workers: int = 0
    val_every: int = 1  # Validate every N epochs
    val_every_opt_steps: int = 0  # Validate every K optimizer steps (0=disabled)
    patience: int = 0  # Early stopping patience (0=disabled)
    save_every_steps: int = 0  # Save checkpoint every K optimizer steps
    save_every_epochs: int = 1
    keep_last_k: int = 3  # Keep only last K checkpoints
    dropout_ratio: float = 0.0  # Instruction dropout for robustness
    seed: int = 42
    # Paths set dynamically
    output_dir: str = "./output"
    checkpoint_dir: Optional[str] = None
    log_dir: Optional[str] = None
    resume_from: Optional[str] = None

@dataclass
class DataConfig:
    """Dataset paths and preprocessing."""
    train_jsonl: str = None
    val_jsonl: Optional[str] = None

@dataclass
class InferenceConfig:
    """Inference and generation parameters."""
    base_id: str = "HuggingFaceTB/SmolVLM2-2.2B-Instruct"
    adapter_dir: str = ""
    merged_dir: str = ""
    max_new_tokens: int = 512
    temperature: float = 1.0
    do_sample: bool = False
    system_prompt: str = (
        "You are an assistant that converts a short task description and the PROVIDED MEDIA "
        "(video frames or images) into a BehaviorTree.CPP behavior tree.\n\n"
        "Always ground your decisions in the media. If the task text conflicts with what the media "
        "shows, follow the media and ignore the conflicting part of the text.\n\n"
        "Output requirements:\n"
        "- Output only a single valid BehaviorTree.CPP XML and nothing else.\n"
        "- The outermost tag of the output must be exactly one <BehaviorTree>...</BehaviorTree>.\n"
        "- Do not wrap the tree in any additional <root> tag or other container.\n"
        "- Do not add explanations, comments, markdown or prose before or after the XML.\n"
    )