from dataclasses import dataclass
from typing import Iterable, List, Optional
import re
from pathlib import Path
from .config import PATHS

@dataclass
class EpisodeRef:
    dataset: str
    version: str
    episode_id: str
    path: Path

_EPISODE_RE = re.compile(r"^episode_\d{3}$")


def list_episodes(dataset: str) -> List[EpisodeRef]:
    # Nuovo layout: dataset/<dataset_with_version>/episode_XXX
    base = PATHS.dataset_root / dataset
    if not base.exists():
        return []
    eps = []
    for p in sorted(base.iterdir()):
        if p.is_dir() and _EPISODE_RE.match(p.name):
            eps.append(EpisodeRef(dataset, "", p.name, p))
    return eps


def slice_episodes(
    episodes: List[EpisodeRef],
    start: Optional[int],
    end: Optional[int],
    ids: Optional[List[int]] = None,
) -> List[EpisodeRef]:
    if ids:
        selected = [e for e in episodes if int(e.episode_id.split("_")[1]) in ids]
        return selected
    if start is None and end is None:
        return episodes
    s = start or 1
    e = end or int(episodes[-1].episode_id.split("_")[1])
    out = []
    for ep in episodes:
        k = int(ep.episode_id.split("_")[1])
        if s <= k <= e:
            out.append(ep)
    return out

