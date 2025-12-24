import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embodied_bt_brain.agentic_teacher import AgenticTeacherLoop
from embodied_bt_brain.agentic_teacher.agents import (
    ArchitectAgent,
    ConformanceAgent,
    IdPatchabilityAgent,
    RobustnessAgent,
    SchemaAgent,
    ScorerAgent,
    SubtreeEnablementAgent,
)
from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.primitive_library.validator import load_default_pal_spec


def main() -> None:
    pal_spec = load_default_pal_spec()
    llm_client = AzureLLMClient()

    agents = {
        "architect": ArchitectAgent(llm_client),
        "conformance": ConformanceAgent(pal_spec, llm_client=llm_client),
        "schema": SchemaAgent(llm_client=llm_client),
        "robustness": RobustnessAgent(llm_client=llm_client),
        "subtree_enablement": SubtreeEnablementAgent(llm_client=llm_client),
        "id_patchability": IdPatchabilityAgent(llm_client=llm_client),
        "scorer": ScorerAgent(llm_client=llm_client),
    }

    teacher = AgenticTeacherLoop(agents)
    result = teacher.generate_bt(
        instruction="Pick up the cup and place it on the table.",
        contact_sheet_path="N/A",
    )

    print("verdict:", result["verdict"])
    print("score:", result["score"])
    print("audit_log_len:", len(result["audit_log"]))
    print("bt_xml:", result["bt_xml"])


if __name__ == "__main__":
    main()
