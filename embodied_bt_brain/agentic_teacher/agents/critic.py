from typing import Any, Dict, List, Optional, Tuple

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.llm_parse import extract_xml
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


class CriticAgent:
    """
    Socratic Critic Agent - challenges Architect's BT design.

    - Max 2 iterations of critique-revision dialogue
    - Blocking but solvable (Architect must address critical issues)
    - Focus on logical coherence + visual grounding
    """

    def __init__(
        self,
        llm_client: Optional[AzureLLMClient] = None,
        *,
        model: Optional[str] = None,
        max_iterations: int = 2,
        strict_mode: bool = True,
    ) -> None:
        self.llm_client = llm_client
        self.model = model
        self.max_iterations = max_iterations
        self.strict_mode = strict_mode  # If True, must address all critical issues

    def process(
        self,
        bt_xml: str,
        instruction: str,
        scene_analysis: Optional[Dict[str, Any]] = None,
        architect_agent: Optional[Any] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Run Socratic dialogue between Critic and Architect.

        Args:
            bt_xml: Initial BT from Architect
            instruction: Original task instruction
            scene_analysis: Scene analysis output (if available)
            architect_agent: Reference to Architect for regeneration

        Returns:
            (final_bt_xml, audit_log)
        """
        if self.llm_client is None:
            # No LLM - skip critique
            return bt_xml, [
                {
                    "agent": "Critic",
                    "status": "skipped",
                    "reason": "No LLM client provided",
                }
            ]

        audit_log = []
        current_bt = bt_xml
        dialogue_history = []

        for iteration in range(self.max_iterations):
            # Step 1: Critic reviews the BT
            critique = self._critique_bt(
                current_bt,
                instruction,
                scene_analysis,
                iteration,
            )

            dialogue_history.append(
                {
                    "iteration": iteration + 1,
                    "critique": critique,
                }
            )

            # Step 2: Check verdict
            verdict = critique.get("verdict", "CONCERNS")

            if verdict == "ACCEPT":
                # Critic is satisfied
                audit_log.append(
                    {
                        "agent": "Critic",
                        "status": "accepted",
                        "iterations": iteration + 1,
                        "dialogue": dialogue_history,
                    }
                )
                return current_bt, audit_log

            # Step 3: Critic has concerns - Architect must respond
            if architect_agent is None:
                # Can't revise without Architect reference
                audit_log.append(
                    {
                        "agent": "Critic",
                        "status": "concerns_unresolved",
                        "verdict": verdict,
                        "critique": critique,
                        "reason": "No Architect agent to revise",
                    }
                )
                return current_bt, audit_log

            # Step 4: Architect revises based on critique
            try:
                revised_bt, revision_log = self._request_revision(
                    architect_agent,
                    current_bt,
                    instruction,
                    critique,
                    scene_analysis,
                )

                dialogue_history[-1]["revision"] = {
                    "bt_xml": revised_bt,
                    "log": revision_log,
                }

                current_bt = revised_bt

            except Exception as exc:
                # Revision failed
                audit_log.append(
                    {
                        "agent": "Critic",
                        "status": "revision_failed",
                        "iteration": iteration + 1,
                        "error": str(exc),
                        "dialogue": dialogue_history,
                    }
                )
                # Return original BT if revision fails
                return bt_xml, audit_log

        # Max iterations reached - check final state
        final_critique = self._critique_bt(
            current_bt,
            instruction,
            scene_analysis,
            self.max_iterations,
        )

        final_verdict = final_critique.get("verdict", "CONCERNS")

        if self.strict_mode and final_verdict == "REJECT":
            # In strict mode, REJECT means failure
            audit_log.append(
                {
                    "agent": "Critic",
                    "status": "rejected",
                    "iterations": self.max_iterations,
                    "final_critique": final_critique,
                    "dialogue": dialogue_history,
                    "action": "DISCARD_EPISODE",
                }
            )
            raise ValueError(
                f"Critic rejected BT after {self.max_iterations} iterations: "
                f"{final_critique.get('critical_issues', [])}"
            )

        # Max iterations but acceptable
        audit_log.append(
            {
                "agent": "Critic",
                "status": "max_iterations_reached",
                "final_verdict": final_verdict,
                "iterations": self.max_iterations,
                "dialogue": dialogue_history,
            }
        )

        return current_bt, audit_log

    def _critique_bt(
        self,
        bt_xml: str,
        instruction: str,
        scene_analysis: Optional[Dict[str, Any]],
        iteration: int,
    ) -> Dict[str, Any]:
        """Generate critique of the BT."""

        # Format scene analysis for prompt
        scene_context = "No scene analysis available."
        if scene_analysis:
            scene_context = f"""
Scene Description: {scene_analysis.get('scene_description', 'N/A')}
Favorable Conditions: {scene_analysis.get('favorable_conditions', [])}
Unfavorable Conditions: {scene_analysis.get('unfavorable_conditions', [])}
Predicted Failures: {scene_analysis.get('predicted_failures', [])}
Complexity: {scene_analysis.get('complexity_estimate', 'unknown')}
"""

        prompt = f"""You are a Critical Reviewer of Behavior Trees (Socratic Mode).

INSTRUCTION: {instruction}

SCENE ANALYSIS:
{scene_context}

ARCHITECT'S BT (Iteration {iteration + 1}):
{bt_xml}

Your role: Challenge this BT design with tough, constructive questions.

Evaluate on TWO dimensions:

1. LOGICAL COHERENCE:
   - Does the BT actually accomplish the instruction?
   - Are actions in the correct order?
   - Any logical impossibilities? (e.g., PLACE before GRASP)
   - Missing critical steps?
   - Are control flow semantics correct? (Sequence vs Fallback)

2. VISUAL GROUNDING:
   - Did the Architect use the scene analysis?
   - Scene mentioned obstacles/clutter - is navigation adjusted?
   - Scene predicted failures - are they mitigated?
   - Scene mentioned specific conditions - are they addressed?
   - Does the BT match the visual reality shown in frames?

Output a JSON object:
{{
  "verdict": "ACCEPT" | "CONCERNS" | "REJECT",

  "logical_coherence": {{
    "score": 0-10,
    "issues": ["issue 1", "issue 2"],
    "questions": ["Why did you...", "How will you handle..."]
  }},

  "visual_grounding": {{
    "score": 0-10,
    "scene_elements_used": ["element 1", "element 2"],
    "scene_elements_ignored": ["ignored 1"],
    "questions": ["Scene says X but BT does Y - why?"]
  }},

  "critical_issues": [
    "CRITICAL: [issue that must be fixed]"
  ],

  "suggestions": [
    "Consider adding...",
    "Could simplify by..."
  ]
}}

Verdict guide:
- ACCEPT: Logical and grounded, ready for refinement
- CONCERNS: Some issues but fixable, suggest improvements
- REJECT: Critical logical flaws or complete scene ignorance (must fix)

Be constructive but rigorous. Ask pointed questions.
"""

        response = self.llm_client.complete(prompt, model=self.model)

        # Parse JSON response
        import json
        try:
            # Try to extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                critique = json.loads(response[start:end])
            else:
                # Fallback: couldn't parse, accept the BT
                critique = {
                    "verdict": "ACCEPT",
                    "parse_error": True,
                    "raw_response": response,
                }
        except json.JSONDecodeError:
            # Fallback
            critique = {
                "verdict": "ACCEPT",
                "parse_error": True,
                "raw_response": response,
            }

        return critique

    def _request_revision(
        self,
        architect_agent: Any,
        current_bt: str,
        instruction: str,
        critique: Dict[str, Any],
        scene_analysis: Optional[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """Request Architect to revise BT based on critique."""

        # Format critique for Architect
        critical_issues = critique.get("critical_issues", [])
        suggestions = critique.get("suggestions", [])
        logical_questions = critique.get("logical_coherence", {}).get("questions", [])
        visual_questions = critique.get("visual_grounding", {}).get("questions", [])

        all_feedback = []

        if critical_issues:
            all_feedback.append("CRITICAL ISSUES (must address):")
            all_feedback.extend([f"  - {issue}" for issue in critical_issues])

        if logical_questions:
            all_feedback.append("\nLOGICAL COHERENCE QUESTIONS:")
            all_feedback.extend([f"  - {q}" for q in logical_questions])

        if visual_questions:
            all_feedback.append("\nVISUAL GROUNDING QUESTIONS:")
            all_feedback.extend([f"  - {q}" for q in visual_questions])

        if suggestions:
            all_feedback.append("\nSUGGESTIONS:")
            all_feedback.extend([f"  - {s}" for s in suggestions])

        feedback_text = "\n".join(all_feedback)

        # Build revision prompt
        revision_prompt = f"""Your initial BT has been reviewed by a Critic. Address the feedback.

ORIGINAL INSTRUCTION: {instruction}

YOUR CURRENT BT:
{current_bt}

CRITIC'S FEEDBACK:
{feedback_text}

Generate a REVISED BehaviorTree that addresses the feedback.
- Fix all CRITICAL ISSUES
- Answer the questions through your design choices
- Incorporate relevant suggestions
- Maintain the same XML format
- Use ONLY PAL v1 primitives

Return ONLY the XML, no explanations.
"""

        # Call Architect's LLM to revise
        response = architect_agent.llm_client.complete(
            revision_prompt,
            model=architect_agent.model,
        )

        revised_bt = extract_xml(response)

        if not revised_bt:
            raise ValueError("Architect failed to generate valid XML in revision")

        return revised_bt, "Revised based on critic feedback"
