import json
from pathlib import Path
from typing import Dict

GLOBAL_PREAMBLE = (
    "SYSTEM (role: senior BT engineer)\n"
    "You generate BehaviorTree.CPP v3 XML subtrees that are locally consistent with a given GLOBAL BT.\n"
    "Follow STRICT RULES. Print exactly two code blocks: (1) XML subtree, (2) JSON metadata.\n"
)

STRICT_RULES = (
    "STRICT RULES\n"
    "1) Output (1) must be BehaviorTree.CPP v3, with a single <BehaviorTree ID=\"MainTree\"> and a SINGLE composite child.\n"
    "2) Use ONLY node IDs and ports from NODE_LIBRARY; all numeric/string values MUST belong to port_value_spaces.\n"
    "3) The subtree must realize the LOCAL_ANNOTATION micro-goal and be coherent with GLOBAL_BT and GLOBAL_DESCRIPTION.\n"
    "4) Keep minimality: perceive → (approach/align) → act → verify; decorators only if they add execution semantics (Retry/Timeout).\n"
    "5) Do not invent blackboard keys not implied by NODE_LIBRARY or GLOBAL_BT.\n"
    "6) No comments, no extra tags, no prose inside XML.\n"
)

REQUIRED_OUTPUT = (
    "REQUIRED OUTPUT\n\n"
    "(1) XML subtree\n"
    "<BehaviorTree ID=\"MainTree\">\n"
    "    <Sequence>\n"
    "        <!-- minimal, binned, library-only -->\n"
    "    </Sequence>\n"
    "</BehaviorTree>\n\n"
    "(2) JSON metadata\n"
    "{\n"
    "  \"frame_index\": __FRAME_INDEX__,\n"
    "  \"local_intent\": \"\",\n"
    "  \"plugs_into\": { \"path_from_root\": [\"MainTree\"], \"mode\": \"replace-only\" },\n"
    "  \"bb_read\": [],\n"
    "  \"bb_write\": [],\n"
    "  \"assumptions\": [],\n"
    "  \"coherence_with_global\": \"\",\n"
    "  \"format_checks\": {\n"
    "    \"single_root_composite\": true,\n"
    "    \"decorators_single_child\": true,\n"
    "    \"only_known_nodes\": true,\n"
    "    \"only_binned_values\": true\n"
    "  }\n"
    "}\n"
)


def build_cached_block(node_library: Dict) -> str:
    return (
        GLOBAL_PREAMBLE
        + "\nINPUTS\n- NODE_LIBRARY (authoritative; use only these node IDs, ports, and port_value_spaces):\n"
        + json.dumps(node_library, ensure_ascii=False, indent=2)
        + "\n\n"
    )


def build_local_prompt(
    cached_block: str,
    global_bt_xml: str,
    global_description_json: Dict,
    frame_index: int,
    frame_name: str,
    local_annotation_json: Dict,
    replacement_target_json: Dict,
) -> str:
    text = []
    text.append(cached_block)
    text.append("- GLOBAL_BT (authoritative structure, do not modify here):\n" + global_bt_xml.strip() + "\n")
    text.append("- GLOBAL_DESCRIPTION (task_long_description; keep semantics consistent):\n" + json.dumps(global_description_json, ensure_ascii=False, indent=2) + "\n")
    text.append("- FRAME (single image; indexing is authoritative):\n" + f"frame_index: {frame_index}\nframe_name: \"{frame_name}\"\n\n")
    text.append("- LOCAL_ANNOTATION (authoritative for current micro-goal):\n" + json.dumps(local_annotation_json, ensure_ascii=False, indent=2) + "\n")
    text.append("- REPLACEMENT_TARGET (where the subtree will plug):\n" + json.dumps(replacement_target_json, ensure_ascii=False, indent=2) + "\n\n")
    text.append(STRICT_RULES + "\n\n" + REQUIRED_OUTPUT.replace("__FRAME_INDEX__", str(frame_index)))
    return "".join(text)