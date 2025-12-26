from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from xml.etree import ElementTree as ET

from embodied_bt_brain.primitive_library.validator import validate_bt_xml


class AgenticTeacherLoop:
    """
    Orchestrates a multi-agent "teacher" pipeline to produce a single BT XML.

    Notes:
    - Each agent is expected to return syntactically valid BT.CPP XML (or raise).
    - PAL conformance is enforced at the end (via ConformanceAgent).
    - Optional preflight agents can skip an episode early (FeasibilityAgent).
    """

    def __init__(
        self,
        agents: Dict[str, Any],
        *,
        pipeline: Optional[List[str]] = None,
    ) -> None:
        if pipeline is None:
            pipeline = [
                "robustness",
                "subtree_enablement",
                "conformance",
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
        # Always init steps list
        steps: List[Dict[str, Any]] = []

        feasibility = self.agents.get("feasibility")
        if feasibility is not None:
            feasibility_data, feasibility_log = feasibility.check(  # type: ignore[call-arg]
                instruction,
                contact_sheet_path,
            )
            audit_log: List[dict] = [feasibility_log]
            if on_agent_step:
                on_agent_step("feasibility")
            
            # Record step regardless of outcome
            step_record = {
                "agent": "feasibility",
                "content": feasibility_data,
                "ext": "json",
                "feasible": feasibility_log.get("feasible", True)
            }
            if record_steps:
                steps.append(step_record)

            if not feasibility_log.get("feasible", True):
                # STOP HERE, but return the trace for the "Safety" dataset.
                return {
                    "bt_xml": "",  # No XML generated
                    "audit_log": audit_log,
                    "score": 0,
                    "verdict": "REJECT",
                    "reason": f"Infeasible: {feasibility_log.get('reason')}",
                    "steps": steps if record_steps else [step_record], # Ensure trace is present
                }
        else:
            audit_log = []

        scene_analysis = ""
        scene = self.agents.get("scene_analysis")
        if scene is not None:
            scene_analysis, scene_log = scene.analyze(  # type: ignore[call-arg]
                instruction,
                contact_sheet_path,
            )
            audit_log.append(scene_log)
            if on_agent_step:
                on_agent_step("scene_analysis")
            if record_steps:
                steps.append(
                    {
                        "agent": "scene_analysis",
                        "content": scene_analysis,
                        "ext": "txt",
                    }
                )

        architect = self.agents.get("architect")
        if architect is None:
            raise ValueError("Missing required agent: architect")

        draft_fn = getattr(architect, "draft", None)
        if not callable(draft_fn):
            raise TypeError(
                "Architect agent must implement draft(instruction, contact_sheet_path)."
            )

        bt_xml, architect_log = draft_fn(
            instruction,
            contact_sheet_path,
            scene_analysis=scene_analysis,
        )
        audit_log.extend(architect_log)
        if on_agent_step:
            on_agent_step("architect")
        if record_steps:
            steps.append({
                "agent": "architect", 
                "bt_xml": bt_xml,
                "type": "baseline" # Mark as baseline for DPO
            })

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

        # Final hard checks (syntactic + PAL v1 conformance) after all mutations.
        try:
            ET.fromstring(bt_xml)
        except ET.ParseError as exc:
            raise ValueError(f"final XML parse error: {exc}") from exc

        conformance_agent = self.agents.get("conformance")
        pal_spec = getattr(conformance_agent, "pal_spec", None)
        if pal_spec:
            final_issues = validate_bt_xml(bt_xml, pal_spec)
            audit_log.append(
                {
                    "agent": "FinalValidator",
                    "status": "ok" if not final_issues else "error",
                    "issues": final_issues,
                }
            )
            if final_issues:
                # Instead of raising, we can reject it
                return {
                    "bt_xml": bt_xml,
                    "audit_log": audit_log,
                    "score": 0,
                    "verdict": "REJECT",
                    "reason": f"PAL validation failed: {final_issues}",
                    "steps": steps
                }

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
            "steps": steps # Always include steps if record_steps was requested (or even if not? User said "Lossless")
        }
        return result


class SkipEpisode(Exception):
    def __init__(self, reason: str, *, details: Optional[dict] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}
