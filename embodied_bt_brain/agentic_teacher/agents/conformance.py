from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.bt_checks import check_library, check_parameters
from embodied_bt_brain.agentic_teacher.bt_repair.llm_repair import LLMRepairer
from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient


class ConformanceAgent:
    def _deterministic_fixes(self, bt_xml: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Apply non-LLM, semantics-preserving fixes for common runtime bugs that are not
        covered by PAL param/spec checks.
        """
        try:
            root = ET.fromstring(bt_xml)
        except ET.ParseError:
            return bt_xml, []

        fixes: List[Dict[str, Any]] = []

        # 1) Ensure root@main_tree_to_execute matches the first BehaviorTree ID.
        first_bt = None
        for child in list(root):
            if child.tag == "BehaviorTree":
                first_bt = child
                break
        if first_bt is not None:
            first_id = first_bt.get("ID")
            if first_id:
                cur = root.get("main_tree_to_execute")
                if cur != first_id:
                    root.set("main_tree_to_execute", first_id)
                    fixes.append(
                        {
                            "code": "fixed_main_tree_to_execute",
                            "message": f"Set root@main_tree_to_execute to '{first_id}' (was '{cur}').",
                        }
                    )

        # 2) Remove duplicate RELEASE inside placement subtrees if main already has RELEASE.
        main_id = root.get("main_tree_to_execute")
        main_bt = None
        if main_id:
            for bt in root.findall("BehaviorTree"):
                if bt.get("ID") == main_id:
                    main_bt = bt
                    break
        if main_bt is not None:
            main_has_release = any(
                (node.tag == "Action" and node.get("ID") == "RELEASE") for node in main_bt.iter()
            )
            if main_has_release:
                removed = 0
                for subtree_id in ("T_Manipulate_Place_OnTop", "T_Manipulate_Place_Inside"):
                    for bt in root.findall("BehaviorTree"):
                        if bt.get("ID") != subtree_id:
                            continue
                        # remove RELEASE actions inside this subtree definition
                        for parent in list(bt.iter()):
                            for child in list(parent):
                                if child.tag == "Action" and child.get("ID") == "RELEASE":
                                    parent.remove(child)
                                    removed += 1
                if removed:
                    fixes.append(
                        {
                            "code": "removed_duplicate_release_in_place_subtrees",
                            "message": f"Removed {removed} RELEASE Action(s) from placement subtree definitions.",
                        }
                    )

        # 3) BehaviorTree.CPP requires exactly one root node per <BehaviorTree>.
        wrapped = 0
        for bt in root.findall("BehaviorTree"):
            children = list(bt)
            if len(children) <= 1:
                continue
            seq = ET.Element("Sequence")
            for child in children:
                bt.remove(child)
                seq.append(child)
            bt.append(seq)
            wrapped += 1
        if wrapped:
            fixes.append(
                {
                    "code": "wrapped_multiple_roots",
                    "message": f"Wrapped {wrapped} BehaviorTree(s) with multiple top-level children in a Sequence.",
                }
            )

        if not fixes:
            return bt_xml, []

        try:
            ET.indent(root, space="  ")
        except AttributeError:
            pass
        return ET.tostring(root, encoding="unicode"), fixes

    def __init__(
        self,
        pal_spec: Dict[str, Any],
        *,
        allow_direct_tags: bool = False,
        strict: bool = True,
        llm_client: Optional[AzureLLMClient] = None,
        model: Optional[str] = None,
    ) -> None:
        self.pal_spec = pal_spec
        self.allow_direct_tags = allow_direct_tags
        self.strict = strict
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
        fixed_xml, deterministic_fixes = self._deterministic_fixes(bt_xml)
        bt_xml = fixed_xml

        issues = []
        issues.extend(
            check_library(bt_xml, self.pal_spec, allow_direct_tags=self.allow_direct_tags)
        )
        issues.extend(
            check_parameters(bt_xml, self.pal_spec, allow_direct_tags=self.allow_direct_tags)
        )

        if not issues:
            # If no issues, return original XML without LLM call
            if deterministic_fixes:
                return bt_xml, [
                    {
                        "agent": "Conformance",
                        "status": "ok",
                        "issues_found": 0,
                        "issues_fixed": 0,
                        "deterministic_fixes": deterministic_fixes,
                        "used_llm": False,
                    }
                ]
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
        fixed_xml = self.repairer.repair(
            bt_xml,
            issues,
            context="Fix the XML to comply with PAL v1 primitives and parameters.",
            prompt_template="conformance",
        )

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
        if self.strict and new_issues:
            raise ValueError(f"ConformanceAgent strict mode: remaining issues: {new_issues}")
        return fixed_xml, audit_log
