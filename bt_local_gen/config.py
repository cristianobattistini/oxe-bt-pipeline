from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ModelCfg:
    name: str = "gpt-5-thinking"
    temperature: float = 0.2
    top_p: float = 1.0
    use_provider_cache: bool = True

@dataclass(frozen=True)
class PriceCfgUSD:
    per_m_input: float = 1.25
    per_m_output: float = 10.0
    per_image_equiv_tokens: int = 1000  # stima per 1024×1024

@dataclass
class Paths:
    project_root: Path = Path(".").resolve()
    dataset_root: Path = project_root / "dataset"
    logs_root: Path = project_root / "out" / "logs"
    node_library: Path = project_root / "library" / "node_library_v_01.json"

MODEL = ModelCfg()
PRICES = PriceCfgUSD()
PATHS = Paths()
TIMEOUT_S = 120
MAX_RETRIES = 4
SEED = 7

SUPPORTED_DATASETS = [
    "columbia_cairlab_pusht_real_0.1.0",
    "utokyo_pr2_opening_fridge_0.1.0",
    "utokyo_pr2_tabletop_manipulation_0.1.0",
    "utokyo_xarm_pick_and_place_0.1.0",
    "cmu_stretch_0.1.0",
]

STRICT_FILESET = {
    "bt": ("bt.xml",),
    "meta": ("meta.json",),
    "locals": (
        "locals/local_1/subtree_.xml",
        "locals/local_1/subtree_.json",
        "locals/local_1/local_prompt",
        "locals/local_1/frame_XX.jpg",
    )
}

