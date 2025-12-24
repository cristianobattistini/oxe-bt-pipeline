from typing import Any, Callable, Dict, List, Optional, Tuple


class AgenticTeacherLoop:
    def __init__(
        self,
        agents: Dict[str, Any],
        *,
        pipeline: Optional[List[str]] = None,
    ) -> None:
        if pipeline is None:
            pipeline = [
                "conformance",
                "schema",
                "robustness",
                "subtree_enablement",
                "id_patchability",
            ]
        self.agents = agents
        self.pipeline = pipeline

    def generate_bt(
        self,
        instruction: str,
        contact_sheet_path: str,
        *,
        record_steps: bool = False,
        on_agent_step: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        architect = self.agents.get("architect")
        if architect is None:
            raise ValueError("Missing required agent: architect")

        draft_fn = getattr(architect, "draft", None)
        if not callable(draft_fn):
            raise TypeError(
                "Architect agent must implement draft(instruction, contact_sheet_path)."
            )

        bt_xml, audit_log = draft_fn(instruction, contact_sheet_path)
        if on_agent_step:
            on_agent_step("architect")
        steps: List[Dict[str, str]] = []
        if record_steps:
            steps.append({"agent": "architect", "bt_xml": bt_xml})

        for agent_name in self.pipeline:
            agent = self.agents.get(agent_name)
            if agent is None:
                continue
            bt_xml, agent_log = agent.process(bt_xml)
            audit_log.extend(agent_log)
            if record_steps:
                steps.append({"agent": agent_name, "bt_xml": bt_xml})
            if on_agent_step:
                on_agent_step(agent_name)

        verdict = "SKIP"
        score = None
        scorer = self.agents.get("scorer")
        if scorer is not None:
            verdict, score, scorer_log = scorer.evaluate(bt_xml, audit_log)
            audit_log.append(scorer_log)
            if on_agent_step:
                on_agent_step("scorer")

        result = {
            "bt_xml": bt_xml,
            "audit_log": audit_log,
            "score": score,
            "verdict": verdict,
        }
        if record_steps:
            result["steps"] = steps
        return result
