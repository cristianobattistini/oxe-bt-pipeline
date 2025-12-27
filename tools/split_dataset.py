import json
import os
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

# Configurazione percorsi default
DEFAULT_INPUT = "dataset_distillation_v1/train/data.jsonl"
DEFAULT_OUTPUT = "dataset_distillation_v1_split"
PROMPTS_DIR = Path("prompts/inference")
PAL_SPEC_PATH = Path("embodied_bt_brain/primitive_library/pal_v1.json")

def load_template(name):
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing prompt template: {path}. "
            "Expected files: prompts/inference/adapter_vision.md, adapter_logic.md, adapter_repair.md."
        )
    return path.read_text(encoding="utf-8")

def render_template(template: str, **values: str) -> str:
    """
    Safe template rendering for our simple {key} placeholders.
    Avoids str.format() issues when values contain braces (e.g., XML with {target}).
    """
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", value)
    return out

def load_pal_spec():
    with open(PAL_SPEC_PATH, "r") as f:
        return json.load(f)["primitives"]

def extract_used_actions(xml_string, pal_primitives):
    """Estrae le action ID usate nell'XML e le formatta come NAME(params)."""
    try:
        root = ET.fromstring(xml_string)
        used_ids = set()
        for action in root.findall(".//Action"):
            action_id = action.get("ID")
            if action_id:
                used_ids.add(action_id)
        
        formatted_actions = []
        for aid in sorted(list(used_ids)):
            if aid in pal_primitives:
                params = list(pal_primitives[aid].get("params", {}).keys())
                params_str = ", ".join(params)
                formatted_actions.append(f"{aid}({params_str})")
            else:
                # Se non è nel PAL, lo mettiamo senza parametri
                formatted_actions.append(f"{aid}()")
        
        return "[" + ", ".join(formatted_actions) + "]"
    except Exception as e:
        print(f"Error parsing XML: {e}")
        return "[]"

def split_dataset(input_file, output_dir):
    input_path = Path(input_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Caricamento template e PAL spec
    tmpl_vision = load_template("adapter_vision")
    tmpl_logic = load_template("adapter_logic")
    tmpl_repair = load_template("adapter_repair")
    pal_primitives = load_pal_spec()

    vision_data = []
    logic_data = []
    repair_data = []

    print(f"Reading {input_path}...")
    
    if not input_path.exists():
        print(f"Error: Input file {input_path} not found.")
        return

    with open(input_path, "r") as f:
        for line in f:
            if not line.strip(): continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            if record.get("verdict") != "ACCEPT":
                continue
                
            instruction = record["instruction"]
            img_path = record["student_image_path"]
            trace = record.get("trace", {})
            
            semantic_state = trace.get("semantic_state", "")
            naive_xml = trace.get("naive_xml", "")
            final_xml = trace.get("final_xml", "")
            
            # Estrazione dinamica delle action usate
            used_actions_str = extract_used_actions(final_xml, pal_primitives)
            
            # 1. Vision Adapter Dataset
            vision_data.append({
                "image": img_path,
                "prompt": render_template(tmpl_vision, instruction=instruction),
                "target": semantic_state
            })
            
            # 2. Logic Adapter Dataset
            logic_data.append({
                "image": img_path,
                "prompt": render_template(
                    tmpl_logic,
                    instruction=instruction,
                    semantic_state=semantic_state,
                    actions=used_actions_str,
                ),
                "target": final_xml
            })
            
            # 3. Repair Adapter Dataset
            if naive_xml and final_xml and naive_xml != final_xml:
                repair_data.append({
                    "image": img_path,
                    "prompt": render_template(tmpl_repair, instruction=instruction, naive_xml=naive_xml),
                    "target": final_xml
                })

    def save_jsonl(data, filename):
        path = output_path / filename
        with open(path, "w") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
        print(f"Saved {len(data)} samples to {path}")

    save_jsonl(vision_data, "train_vision.jsonl")
    save_jsonl(logic_data, "train_logic.jsonl")
    save_jsonl(repair_data, "train_repair.jsonl")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Split Mega-JSONL into Adapter datasets.")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to input .jsonl file")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output directory")
    args = parser.parse_args()
    
    split_dataset(args.input, args.output)
