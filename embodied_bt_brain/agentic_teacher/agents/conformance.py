from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.bt_checks import check_library, check_parameters
from embodied_bt_brain.agentic_teacher.bt_repair.llm_repair import LLMRepairer
from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient


class ConformanceAgent:
    def __init__(
        self,
        pal_spec: Dict[str, Any],
        *,
        allow_direct_tags: bool = False,
        llm_client: Optional[AzureLLMClient] = None,
        model: Optional[str] = None,
    ) -> None:
        self.pal_spec = pal_spec
        self.allow_direct_tags = allow_direct_tags
        self.llm_client = llm_client
        self.model = model
        
        if self.llm_client:
            self.repairer = LLMRepairer(
                self.llm_client,
                model=self.model,
                default_prompt="repair_generic",
            )
        else:
            self.repairer = None

    def process(self, bt_xml: str) -> Tuple[str, List[Dict[str, Any]]]:
        issues = []
        issues.extend(
            check_library(bt_xml, self.pal_spec, allow_direct_tags=self.allow_direct_tags)
        )
        issues.extend(
            check_parameters(bt_xml, self.pal_spec, allow_direct_tags=self.allow_direct_tags)
        )

        if not issues:
            # If no issues, return original XML without LLM call
            return bt_xml, [
                {
                    "agent": "Conformance",
                    "status": "ok",
                    "issues_found": 0,
                    "issues_fixed": 0,
                    "used_llm": False,
                }
            ]

        if self.repairer is None:
            raise ValueError("ConformanceAgent requires an LLM client to perform repairs.")

        # Attempt repair
        try:
            fixed_xml = self.repairer.repair(
                bt_xml,
                issues,
                context="Fix the XML to comply with PAL v1 primitives and parameters.",
                prompt_template="conformance",  # Use the specific conformance prompt which is better suited
            )
        except ValueError as exc:
            # Fallback: if repair fails, log error and return original (or partial)
            return bt_xml, [
                {
                    "agent": "Conformance",
                    "status": "error",
                    "error": str(exc),
                    "issues_found": len(issues),
                    "used_llm": True,
                }
            ]

        # Re-check to verify fix
        new_issues = []
        new_issues.extend(
            check_library(fixed_xml, self.pal_spec, allow_direct_tags=self.allow_direct_tags)
        )
        new_issues.extend(
            check_parameters(fixed_xml, self.pal_spec, allow_direct_tags=self.allow_direct_tags)
        )

        audit_log = [
            {
                "agent": "Conformance",
                "status": "repaired" if not new_issues else "partial_repair",
                "issues_found": len(issues),
                "issues_fixed": len(issues) - len(new_issues),
                "remaining_issues": new_issues,
                "used_llm": True,
            }
        ]
        return fixed_xml, audit_log
