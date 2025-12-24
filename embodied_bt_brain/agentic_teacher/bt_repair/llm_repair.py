from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

from embodied_bt_brain.agentic_teacher.llm_client import AzureLLMClient
from embodied_bt_brain.agentic_teacher.llm_parse import extract_xml
from embodied_bt_brain.agentic_teacher.prompt_loader import render_prompt


class LLMRepairer:
    """
    A generic repair agent that uses an LLM to fix Behavior Tree XML based on
    reported validation issues.
    """

    def __init__(
        self,
        llm_client: AzureLLMClient,
        *, 
        model: Optional[str] = None,
        default_prompt: str = "repair_generic",
    ) -> None:
        self.llm_client = llm_client
        self.model = model
        self.default_prompt = default_prompt

    def repair(
        self,
        bt_xml: str,
        issues: List[Any],
        *, 
        context: str = "",
        prompt_template: Optional[str] = None,
    ) -> str:
        """
        Attempt to repair the BT XML using the LLM.

        Args:
            bt_xml: The invalid XML string.
            issues: A list of issue objects (dicts or strings) describing the errors.
            context: Optional string providing extra context (e.g. instruction).
            prompt_template: Optional prompt filename to use (without .md).

        Returns:
            The corrected XML string.

        Raises:
            ValueError: If the LLM fails to generate valid XML.
        """
        # Format issues into a readable list
        formatted_issues = []
        for i, issue in enumerate(issues, 1):
            if isinstance(issue, dict):
                msg = issue.get("message") or issue.get("issue") or str(issue)
            else:
                msg = str(issue)
            formatted_issues.append(f"{i}. {msg}")
        
        issues_text = "\n".join(formatted_issues)

        # Render the prompt
        template = prompt_template or self.default_prompt
        try:
            prompt = render_prompt(
                template,
                bt_xml=bt_xml,
                issues=issues_text,
                context=context,
            )
        except FileNotFoundError:
            # Fallback if specific template is missing, though this shouldn't happen
            # with correct configuration.
            prompt = (
                f"Fix the following XML based on these errors:\n\nErrors:\n{issues_text}\n\n"
                f"XML:\n{bt_xml}\n\nContext:\n{context}\n\nReturn ONLY the XML."
            )

        # Call LLM
        response = self.llm_client.complete(prompt, model=self.model)
        
        # Extract and validate XML
        fixed_xml = extract_xml(response)
        if not fixed_xml:
            raise ValueError("LLM Repair failed: No XML block found in response.")

        try:
            ET.fromstring(fixed_xml)
        except ET.ParseError as exc:
            raise ValueError(f"LLM Repair returned invalid XML: {exc}") from exc

        return fixed_xml
