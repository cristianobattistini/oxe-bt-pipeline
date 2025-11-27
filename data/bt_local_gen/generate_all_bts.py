#!/usr/bin/env python3
"""
Scaled BT Generation Script
Processes all episodes in dataset1, generating bt.xml and meta.json
"""
import base64
import json
import re
from pathlib import Path
from typing import Tuple, Optional
from openai import AzureOpenAI
from lxml import etree
import keys

# ============================================================================
# Configuration
# ============================================================================
DATASET_ROOT = Path("dataset3")
OVERWRITE = True  # Set to True to regenerate existing files

# ============================================================================
# Validators (adapted from validators.py)
# ============================================================================

_FENCED_ANY = re.compile(r"```([a-zA-Z0-9_-]+)?\s*\n?([\s\S]*?)\n?```", re.MULTILINE)

def split_two_code_blocks(text: str) -> Tuple[str, str]:
    """Extract XML and JSON from fenced code blocks"""
    xml_block = None
    json_block = None

    for lang, body in _FENCED_ANY.findall(text or ""):
        lang_l = (lang or "").strip().lower()
        body = (body or "").strip()
        if not body:
            continue
        if lang_l == "xml" and xml_block is None:
            xml_block = body
        elif lang_l == "json" and json_block is None:
            json_block = body
        if xml_block is not None and json_block is not None:
            break

    if xml_block is None or json_block is None:
        raise ValueError("Missing XML or JSON code blocks")
    return xml_block, json_block


def _find_balanced_segment(s: str, start_pat: str, end_pat: str) -> Optional[str]:
    """Find balanced XML segment"""
    start_re = re.compile(start_pat, re.IGNORECASE | re.DOTALL)
    end_re = re.compile(end_pat, re.IGNORECASE | re.DOTALL)

    m = start_re.search(s)
    if not m:
        return None

    start_idx = m.start()
    opens = list(start_re.finditer(s, start_idx))
    ends = list(end_re.finditer(s, start_idx))

    if not opens or not ends:
        return None

    depth = 0
    i_open, i_end = 0, 0
    pos = start_idx

    while i_open < len(opens) or i_end < len(ends):
        next_open = opens[i_open].start() if i_open < len(opens) else None
        next_end = ends[i_end].start() if i_end < len(ends) else None

        if next_end is None or (next_open is not None and next_open < next_end):
            depth += 1
            pos = opens[i_open].end()
            i_open += 1
        else:
            depth -= 1
            pos = ends[i_end].end()
            i_end += 1
            if depth == 0:
                return s[start_idx:pos]
    return None


def _extract_xml_loose(text: str) -> Optional[str]:
    """Extract XML without fences"""
    seg = _find_balanced_segment(text, r"<\s*BehaviorTree\b", r"\s*BehaviorTree\s*>")
    if not seg:
        return None
    try:
        etree.fromstring(seg.encode("utf-8"))
        return seg.strip()
    except Exception:
        return None


def _extract_first_json_loose(text: str) -> Optional[str]:
    """Extract JSON without fences"""
    n = len(text)
    i = 0
    while i < n:
        if text[i] == "{":
            depth = 0
            j = i
            while j < n:
                ch = text[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j+1]
                        try:
                            json.loads(candidate)
                            return candidate.strip()
                        except Exception:
                            break
                j += 1
        i += 1
    return None


def recover_xml_json_without_fences(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Fallback: extract XML and JSON without fences"""
    xml = _extract_xml_loose(text or "")
    jsn = _extract_first_json_loose(text or "")
    return xml, jsn


def validate_xml(xml_str: str) -> None:
    """Validate XML is well-formed"""
    try:
        etree.fromstring(xml_str.encode("utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid XML: {e}")


def validate_json(json_str: str) -> dict:
    """Validate JSON is parseable"""
    try:
        data = json.loads(json_str)
        return data
    except Exception as e:
        raise ValueError(f"Invalid JSON: {e}")


# ============================================================================
# Discovery and Processing
# ============================================================================

def discover_episodes(dataset_root: Path):
    """Discover all episodes with required files"""
    episodes = []
    episode_re = re.compile(r"^episode_\d{3}$")

    if not dataset_root.exists():
        print(f"❌ Dataset root not found: {dataset_root}")
        return episodes

    # Iterate through datasets
    for dataset_dir in sorted(dataset_root.iterdir()):
        if not dataset_dir.is_dir():
            continue

        # Iterate through episodes
        for episode_dir in sorted(dataset_dir.iterdir()):
            if not episode_dir.is_dir() or not episode_re.match(episode_dir.name):
                continue

            contact_sheet = episode_dir / "contact_sheet.jpg"
            prompt_file = episode_dir / "prompt.md"
            bt_xml = episode_dir / "bt.xml"
            meta_json = episode_dir / "meta.json"

            if not contact_sheet.exists():
                continue
            if not prompt_file.exists():
                continue

            episodes.append({
                "dataset": dataset_dir.name,
                "episode": episode_dir.name,
                "episode_dir": episode_dir,
                "contact_sheet": contact_sheet,
                "prompt_file": prompt_file,
                "bt_xml": bt_xml,
                "meta_json": meta_json,
                "has_bt": bt_xml.exists(),
                "has_meta": meta_json.exists()
            })

    return episodes


def process_episode(ep: dict, client: AzureOpenAI):
    """Process a single episode: generate BT and metadata"""
    ep_name = f"{ep['dataset']}/{ep['episode']}"

    # Check if already processed
    if ep['has_bt'] and ep['has_meta'] and not OVERWRITE:
        print(f"⏭️  {ep_name}: Already processed (use OVERWRITE=True to regenerate)")
        return {"status": "skipped", "reason": "already_exists"}

    print(f"🔄 {ep_name}: Processing...")

    try:
        # Read image and encode to base64
        with open(ep['contact_sheet'], "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Read prompt text
        with open(ep['prompt_file'], "r", encoding="utf-8") as f:
            prompt_text = f.read()

        # Call Azure OpenAI
        print(f"   ↳ Calling GPT-4o...")
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]
                }
            ]
        )

        response_text = resp.choices[0].message.content

        # Parse response
        print(f"   ↳ Parsing response...")
        try:
            xml_block, json_block = split_two_code_blocks(response_text)
        except Exception:
            # Fallback: try without fences
            xml_block, json_block = recover_xml_json_without_fences(response_text)
            if not xml_block or not json_block:
                raise ValueError("Could not extract XML and JSON from response")

        # Validate
        print(f"   ↳ Validating...")
        validate_xml(xml_block)
        json_data = validate_json(json_block)

        # Save files
        print(f"   ↳ Saving bt.xml and meta.json...")
        ep['bt_xml'].write_text(xml_block, encoding="utf-8")
        ep['meta_json'].write_text(json_block, encoding="utf-8")

        print(f"✅ {ep_name}: Success")
        return {
            "status": "success",
            "bt_xml": str(ep['bt_xml']),
            "meta_json": str(ep['meta_json'])
        }

    except Exception as e:
        print(f"❌ {ep_name}: Error - {type(e).__name__}: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# Main
# ============================================================================

def main():
    print("="*70)
    print("Behavior Tree Generation Pipeline")
    print("="*70)
    print()

    # Initialize Azure OpenAI client
    print("🔧 Initializing Azure OpenAI client...")
    client = AzureOpenAI(
        api_key=keys.azure_openai_key,
        azure_endpoint=keys.azure_openai_endpoint,
        api_version=keys.azure_openai_api_version,
    )
    print("✅ Client initialized")
    print()

    # Discover episodes
    print(f"🔍 Discovering episodes in {DATASET_ROOT}...")
    episodes = discover_episodes(DATASET_ROOT)
    print(f"✅ Found {len(episodes)} episodes with required files")
    print()

    if not episodes:
        print("⚠️  No episodes found. Exiting.")
        return

    # Process episodes
    print("🚀 Starting processing...")
    print()

    results = {
        "success": [],
        "skipped": [],
        "error": []
    }

    for i, ep in enumerate(episodes, 1):
        print(f"[{i}/{len(episodes)}]", end=" ")
        result = process_episode(ep, client)
        results[result["status"]].append(ep)

    # Summary
    print()
    print("="*70)
    print("Summary")
    print("="*70)
    print(f"✅ Success: {len(results['success'])}")
    print(f"⏭️  Skipped: {len(results['skipped'])}")
    print(f"❌ Errors:  {len(results['error'])}")
    print()

    if results['error']:
        print("Episodes with errors:")
        for ep in results['error']:
            print(f"  - {ep['dataset']}/{ep['episode']}")


if __name__ == "__main__":
    main()
