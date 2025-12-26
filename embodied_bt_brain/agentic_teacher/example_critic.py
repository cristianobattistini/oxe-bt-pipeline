"""
Example: Using the Critic Agent in the pipeline

This shows how to enable the Socratic Critic Agent to improve
Architect's BT designs through iterative dialogue.
"""

from embodied_bt_brain.agentic_teacher import AgenticTeacherLoop
from embodied_bt_brain.agentic_teacher.agents import (
    ArchitectAgent,
    ConformanceAgent,
    CriticAgent,
    FeasibilityAgent,
    RobustnessAgent,
    SceneAnalysisAgent,
    ScorerAgent,
    SubtreeEnablementAgent,
)
from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.primitive_library.validator import load_default_pal_spec


def main():
    """Example: Pipeline with Critic Agent."""

    pal_spec = load_default_pal_spec()
    llm_client = AzureLLMClient()

    # Build agents
    agents = {
        # Phase 1: Feasibility & Understanding
        "feasibility": FeasibilityAgent(llm_client),
        "scene_analysis": SceneAnalysisAgent(llm_client),

        # Phase 2: Creative Generation
        "architect": ArchitectAgent(llm_client),

        # Phase 2.5: Socratic Critique (NEW!)
        "critic": CriticAgent(
            llm_client,
            max_iterations=2,      # Max 2 rounds of dialogue
            strict_mode=True,      # REJECT verdict blocks episode
        ),

        # Phase 3: Refinement
        "robustness": RobustnessAgent(llm_client=llm_client),
        "subtree_enablement": SubtreeEnablementAgent(llm_client=llm_client),

        # Phase 4: Validation
        "conformance": ConformanceAgent(pal_spec, llm_client=llm_client),
        "scorer": ScorerAgent(llm_client=llm_client),
    }

    # Pipeline: critic is called automatically after architect
    teacher = AgenticTeacherLoop(
        agents,
        pipeline=[
            "robustness",
            "subtree_enablement",
            "conformance",
        ]
    )

    # Generate BT
    result = teacher.generate_bt(
        instruction="Pick up the cup and place it on the tray",
        contact_sheet_path="path/to/contact_sheet.jpg",
    )

    print("=" * 60)
    print("Final BT:")
    print(result["bt_xml"])
    print("=" * 60)

    # Inspect critic dialogue
    for log_entry in result["audit_log"]:
        if log_entry.get("agent") == "Critic":
            print("\nCritic Dialogue:")
            print(f"Status: {log_entry.get('status')}")
            print(f"Iterations: {log_entry.get('iterations', 0)}")

            dialogue = log_entry.get("dialogue", [])
            for turn in dialogue:
                print(f"\n--- Iteration {turn['iteration']} ---")
                critique = turn.get("critique", {})
                print(f"Verdict: {critique.get('verdict')}")
                print(f"Logical Coherence Score: {critique.get('logical_coherence', {}).get('score')}/10")
                print(f"Visual Grounding Score: {critique.get('visual_grounding', {}).get('score')}/10")

                if "revision" in turn:
                    print("→ Architect revised the BT")


if __name__ == "__main__":
    main()
