"""Inference and generation utilities."""
import re
import sys
import torch
from transformers import AutoProcessor, AutoModelForImageTextToText
from peft import PeftModel
import logging

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM = (
    "You are a BehaviorTree.CPP code generator.\n"
    "CONSTRAINTS:\n"
    "- Always ground your decisions in the PROVIDED MEDIA (video frames or images) when available.\n"
    "- If the task text conflicts with the media, follow the media and ignore the conflicting text.\n"
    "- Output ONLY one valid BehaviorTree.CPP XML and nothing else.\n"
    "- The outermost tag of the output must be exactly one <BehaviorTree>...</BehaviorTree>.\n"
    "- Do NOT wrap the tree in any additional <root> tag or other container.\n"
    "- Do NOT add explanations, comments, markdown or prose before or after the XML.\n"
)


def build_messages(system_text: str, prompt_text: str, video_path: str = None, image_path: str = None):
    """
    Build message structure for processor.
    
    Args:
        system_text: System prompt
        prompt_text: User instruction
        video_path: Path to video file (mutually exclusive with image_path)
        image_path: Path to image file (mutually exclusive with video_path)
    
    Returns:
        List of messages in chat format
    """
    if video_path and image_path:
        raise ValueError("Provide only one of 'video_path' or 'image_path', not both.")
    
    content = []
    
    if system_text and system_text.strip():
        content.append({"type": "text", "text": f"SYSTEM: {system_text}"})
    
    if video_path:
        content.append({"type": "video", "path": video_path})
    elif image_path:
        content.append({"type": "image", "path": image_path})
    
    content.append({"type": "text", "text": f"INSTRUCTION: {prompt_text}"})
    
    return [{"role": "user", "content": content}]


def load_model_and_processor(config):
    """
    Load model and processor from checkpoint or base model + adapters.
    
    Args:
        config: InferenceConfig dataclass
    
    Returns:
        tuple: (device, processor, model)
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    load_path = config.merged_dir or config.adapter_dir or config.base_id
    
    # Load processor
    try:
        processor = AutoProcessor.from_pretrained(load_path, trust_remote_code=True)
    except ValueError as e:
        logger.error(f"Failed to load processor from '{load_path}': {e}")
        logger.error("Ensure the directory contains tokenizer.json, processor_config.json, etc.")
        raise SystemExit(1)
    
    # Load model
    if config.merged_dir:
        logger.info(f"Loading merged checkpoint from: {config.merged_dir}")
        model = AutoModelForImageTextToText.from_pretrained(
            config.merged_dir,
            trust_remote_code=True,
            device_map="auto",
            attn_implementation="eager"
        )
    else:
        logger.info(f"Loading base model from: {config.base_id}")
        model = AutoModelForImageTextToText.from_pretrained(
            config.base_id,
            trust_remote_code=True,
            device_map="auto",
            attn_implementation="eager"
        )
        
        # Apply adapters if provided
        if config.adapter_dir:
            logger.info(f"Applying adapters from: {config.adapter_dir}")
            try:
                model = PeftModel.from_pretrained(model, config.adapter_dir)
            except Exception as e:
                logger.error(f"Failed to load adapters from '{config.adapter_dir}': {e}")
                raise SystemExit(1)
    
    model.eval()
    model.config.use_cache = True
    logger.info(f"Model loaded on: {model.device}")
    
    return device, processor, model


def move_batch_to_device_and_cast(batch: dict, model):
    """Move tensors to device and cast pixel_values to model dtype."""
    device = next(model.parameters()).device
    
    for k, v in list(batch.items()):
        if torch.is_tensor(v):
            batch[k] = v.to(device, non_blocking=True)
    
    # Cast pixel values to model dtype
    if "pixel_values" in batch and torch.is_tensor(batch["pixel_values"]):
        model_dtype_config = getattr(model.config, "torch_dtype", torch.float32)
        
        if isinstance(model_dtype_config, str):
            dtype_map = {
                "float32": torch.float32,
                "float16": torch.float16,
                "bfloat16": torch.bfloat16
            }
            model_dtype = dtype_map.get(model_dtype_config, torch.float32)
        elif isinstance(model_dtype_config, torch.dtype):
            model_dtype = model_dtype_config
        else:
            model_dtype = torch.float32
        
        batch["pixel_values"] = batch["pixel_values"].to(model_dtype, non_blocking=True)
    
    return batch


def generate_once(
    model, processor, device, system_text, prompt_text,
    video_path=None, image_path=None,
    max_new_tokens=512, temperature=1.0, do_sample=False
):
    """
    Generate behavior tree XML from prompt and media.
    
    Returns:
        str: Generated XML or error message
    """
    try:
        messages = build_messages(system_text, prompt_text, video_path, image_path)
        batch = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_tensors="pt",
            return_dict=True
        )
    except Exception as e:
        logger.error(f"Error preparing input: {e}")
        return "[ERRORE TEMPLATE]"
    
    batch = move_batch_to_device_and_cast(batch, model)
    
    with torch.inference_mode():
        eos_id = getattr(processor.tokenizer, "eos_token_id", None)
        pad_id = getattr(processor.tokenizer, "pad_token_id", eos_id)
        
        generation_kwargs = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
            "temperature": temperature if do_sample and temperature > 0 else 1.0,
            "top_p": 0.9 if do_sample else None,
            "repetition_penalty": 1.05,
            "eos_token_id": eos_id,
            "pad_token_id": pad_id,
            "return_dict_in_generate": True,
            "output_scores": False,
        }
        
        try:
            out = model.generate(**batch, **{k: v for k, v in generation_kwargs.items() if v is not None})
        except Exception as e:
            logger.error(f"Generation error: {e}")
            if "CUDA out of memory" in str(e):
                logger.error("GPU out of memory. Reduce max_new_tokens or disable sampling.")
            return "[ERRORE GENERAZIONE]"
    
    gen_ids = out.sequences
    prompt_len = batch["input_ids"].shape[1]
    assistant_ids = gen_ids[0][prompt_len:]
    
    if assistant_ids.numel() == 0:
        return "[OUTPUT VUOTO]"
    
    text = processor.tokenizer.decode(assistant_ids, skip_special_tokens=True)
    
    # Extract BehaviorTree XML (no <root> wrapper, only the BehaviorTree block)
    m = re.search(r"<BehaviorTree\b[\s\S]*?</BehaviorTree>", text, re.IGNORECASE | re.DOTALL)
    return (m.group(0) if m else text).strip()
