import hashlib

def cache_tag_for_block(block: str) -> str:
    # Tag stabile per il provider cache; usa esattamente lo stesso blocco byte-identico
    return hashlib.sha256(block.encode("utf-8")).hexdigest()[:24]

