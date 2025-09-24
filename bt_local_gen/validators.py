import re, json
from typing import Tuple, Dict, Any
from lxml import etree

# Match di un fenced block: ```xml ... ``` oppure ```json ... ```
# - tollera spazi dopo i backtick e prima della chiusura
# - il \s* subito dopo 'xml'/'json' consente anche la forma "```xml<...>" senza newline
_FENCED_ANY = re.compile(r"```([a-zA-Z0-9_-]+)\s*\n?([\s\S]*?)\n?```", re.MULTILINE)

def split_two_code_blocks(text: str) -> Tuple[str, str]:
    """
    Estrae il PRIMO blocco ```xml ... ``` e il PRIMO blocco ```json ... ``` presenti in 'text'.
    Ordine libero. Non valida né interpreta i contenuti.
    Se uno dei due manca, solleva ValueError.
    """
    xml_block = None
    json_block = None

    for lang, body in _FENCED_ANY.findall(text):
        lang_l = lang.strip().lower()
        body = body.strip()
        if lang_l == "xml" and xml_block is None:
            xml_block = body
        elif lang_l == "json" and json_block is None:
            json_block = body
        if xml_block is not None and json_block is not None:
            break

    if xml_block is None or json_block is None:
        raise ValueError("mancano i due code block (XML, JSON)")

    return xml_block, json_block

def validate_xml(xml_str: str, allowed_ids: set[str]) -> None:
    try:
        root = etree.fromstring(xml_str.encode("utf-8"))
    except Exception as e:
        raise ValueError(f"XML non parseable: {e}")
    if root.tag not in {"root", "BehaviorTree"}:
        pass
    # Controllo elementi
    for el in root.iter():
        if el.tag in {"root", "BehaviorTree"}:
            continue
        if el.tag not in allowed_ids:
            raise ValueError(f"Nodo non ammesso dalla NODE_LIBRARY: {el.tag}")


def parse_and_validate_json(json_str: str) -> Dict[str, Any]:
    try:
        data = json.loads(json_str)
    except Exception as e:
        raise ValueError(f"JSON non parseable: {e}")
    # Controlli minimi richiesti dall’utente
    fc = data.get("format_checks", {})
    for k in ("single_root_composite", "decorators_single_child", "only_known_nodes", "only_binned_values"):
        if k not in fc:
            raise ValueError(f"JSON metadata manca format_checks.{k}")
    return data

