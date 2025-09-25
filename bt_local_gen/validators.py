import re, json
from typing import Tuple, Dict, Any, Optional
from lxml import etree

# Parser con fence: ```xml ... ```, ```json ... ```
_FENCED_ANY = re.compile(r"```([a-zA-Z0-9_-]+)?\s*\n?([\s\S]*?)\n?```", re.MULTILINE)

def split_two_code_blocks(text: str) -> Tuple[str, str]:
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
        raise ValueError("mancano i due code block (XML, JSON)")
    return xml_block, json_block

# ----------------- Fallback senza fence -----------------

def _find_balanced_segment(s: str, start_pat: str, end_pat: str) -> Optional[str]:
    import re as _re
    start_re = _re.compile(start_pat, _re.IGNORECASE | _re.DOTALL)
    end_re   = _re.compile(end_pat,   _re.IGNORECASE | _re.DOTALL)

    m = start_re.search(s)
    if not m:
        return None
    start_idx = m.start()

    opens = list(start_re.finditer(s, start_idx))
    ends  = list(end_re.finditer(s, start_idx))
    if not opens or not ends:
        return None

    depth = 0
    i_open, i_end = 0, 0
    pos = start_idx
    while i_open < len(opens) or i_end < len(ends):
        next_open = opens[i_open].start() if i_open < len(opens) else None
        next_end  = ends[i_end].start()  if i_end  < len(ends)  else None

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
    seg = _find_balanced_segment(text, r"<\s*BehaviorTree\b", r"</\s*BehaviorTree\s*>")
    if not seg:
        return None
    try:
        etree.fromstring(seg.encode("utf-8"))
        return seg.strip()
    except Exception:
        return None

def _extract_first_json_loose(text: str) -> Optional[str]:
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
    """
    Wrapper con il nome che pipeline.py si aspetta.
    Restituisce (xml, json) oppure (None, None) se non trova entrambi.
    """
    xml = _extract_xml_loose(text or "")
    jsn = _extract_first_json_loose(text or "")
    return xml, jsn

# ----------------- Validazioni -----------------

def validate_xml(xml_str: str, allowed_ids: set[str]) -> None:
    """
    Validazione permissiva:
    - controlla solo che l'XML sia ben formato;
    - NON verifica i tag rispetto alla NODE_LIBRARY;
    - non altera l'XML.
    """
    try:
        etree.fromstring(xml_str.encode("utf-8"))
    except Exception as e:
        raise ValueError(f"XML non parseable: {e}")
    # Nessun controllo su allowed_ids: accettiamo qualsiasi tag.
    return

def parse_and_validate_json(json_str: str) -> Dict[str, Any]:
    try:
        data = json.loads(json_str)
    except Exception as e:
        raise ValueError(f"JSON non parseable: {e}")
    fc = data.get("format_checks", {})
    for k in ("single_root_composite", "decorators_single_child", "only_known_nodes", "only_binned_values"):
        if k not in fc:
            raise ValueError(f"JSON metadata manca format_checks.{k}")
    return data
