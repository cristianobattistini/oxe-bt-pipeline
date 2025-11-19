"""Model and processor initialization with LoRA/QLoRA support."""
import torch
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig
from peft import LoraConfig, prepare_model_for_kbit_training, get_peft_model
import logging

logger = logging.getLogger(__name__)

# Disable FlashAttention, enable compatible SDPA backends
try:
    from torch.backends.cuda import sdp_kernel
    sdp_kernel(enable_flash=False, enable_mem_efficient=True, enable_math=True)
except Exception:
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(True)
    torch.backends.cuda.enable_math_sdp(True)


def setup_model_and_processor(
    model_config,
    lora_config,
    device="cuda"
):
    """
    Initialize processor and model with optional LoRA/QLoRA adapters.
    
    Args:
        model_config: ModelConfig dataclass
        lora_config: LoRAConfig dataclass
        device: Target device
    
    Returns:
        tuple: (processor, model)
    """
    # Load processor
    logger.info(f"Loading processor from {model_config.model_id}")
    processor = AutoProcessor.from_pretrained(
        model_config.model_id,
        trust_remote_code=model_config.trust_remote_code
    )
    
    # Configure LoRA if enabled
    use_lora = lora_config.use_lora or lora_config.use_qlora
    peft_config = None
    bnb_config = None
    
    if use_lora:
        lora_alpha = lora_config.lora_alpha if lora_config.lora_alpha is not None else lora_config.r
        
        peft_config = LoraConfig(
            r=lora_config.r,
            lora_alpha=lora_alpha,
            lora_dropout=lora_config.lora_dropout,
            target_modules=lora_config.target_modules,
            use_dora=lora_config.use_dora and not lora_config.use_qlora,  # DoRA not compatible with QLoRA
            init_lora_weights=lora_config.init_lora_weights,
        )
        peft_config.inference_mode = False
        
        logger.info(f"LoRA config: r={lora_config.r}, alpha={lora_alpha}")
    
    # Configure quantization for QLoRA
    if lora_config.use_qlora:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16
        )
        logger.info("Using 4-bit quantization (QLoRA)")
    
    # Load model
    logger.info(f"Loading model from {model_config.model_id}")
    model = AutoModelForImageTextToText.from_pretrained(
        model_config.model_id,
        quantization_config=bnb_config,
        _attn_implementation="eager",  # Compatibility mode
        device_map="auto" if use_lora else None,
        trust_remote_code=model_config.trust_remote_code,
    )
    
    # Apply LoRA adapters
    if use_lora:
        model.add_adapter(peft_config)
        model.enable_adapters()
        model = prepare_model_for_kbit_training(model)
        model = get_peft_model(model, peft_config)
        
        trainable, total = count_parameters(model)
        logger.info(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")
    else:
        # Full fine-tuning: freeze vision encoder
        model = model.to(device)
        for param in model.model.vision_model.parameters():
            param.requires_grad = False
        logger.info("Froze vision encoder for full fine-tuning")
    
    # Enable gradient checkpointing
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    
    # Log memory usage
    if torch.cuda.is_available():
        peak_mem = torch.cuda.max_memory_allocated() / 1024**3
        logger.info(f"Model loaded: {peak_mem:.2f} GB GPU RAM")
    
    return processor, model


def count_parameters(model):
    """Count trainable vs total parameters."""
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total
