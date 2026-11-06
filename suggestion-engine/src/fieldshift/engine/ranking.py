"""Step 4a: rank sequences and measure how stable the ranking is."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .scoring import SeqEval, total_score

TRIALS = 100
JITTER = 0.30  # each weight is multiplied by a factor in [1-JITTER, 1+JITTER]


@dataclass
class Ranked:
    seq: SeqEval
    total: float
    pessimistic_total: float
    stability: float


def rank_sequences(seqs: list[SeqEval], weights: dict[str, float], seed: int) -> list[Ranked]:
    if not seqs:
        return []
    scored = [(total_score(s, weights), s) for s in seqs]
    scored.sort(key=lambda t: (-t[0], tuple(t[1].crops)))

    rng = random.Random(seed)
    in_top3 = {id(s): 0 for s in seqs}
    for _ in range(TRIALS):
        w = {k: v * rng.uniform(1 - JITTER, 1 + JITTER) for k, v in weights.items()}
        norm = sum(w.values())
        w = {k: v / norm for k, v in w.items()}
        trial = sorted(seqs, key=lambda s: (-total_score(s, w), tuple(s.crops)))[:3]
        for s in trial:
            in_top3[id(s)] += 1

    return [
        Ranked(s, round(t, 4), round(total_score(s, weights, dry=True), 4), in_top3[id(s)] / TRIALS)
        for t, s in scored
    ]
