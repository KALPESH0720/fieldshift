"""
FieldShift Crop Rotation Simulation.

Evaluates multi-season crop sequences using crop families,
root depth, nitrogen contribution and residue return.
"""

from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence


class RotationError(ValueError):
    """Invalid crop rotation configuration."""


@dataclass(frozen=True)
class CropInRotation:

    crop: str
    season: str
    family: str

    root_depth_class: str = "medium"

    nitrogen_fixing: bool = False

    residue_return_kg_ha: float = 0.0

    nitrogen_contribution_kg_ha: float = 0.0

    water_demand_class: str = "medium"

    def __post_init__(self):

        if not self.crop.strip():
            raise RotationError("Crop name is required.")

        if not self.family.strip():
            raise RotationError("Crop family is required.")

        if self.root_depth_class not in {
            "shallow", "medium", "deep"
        }:
            raise RotationError("Invalid root depth class.")

        if self.water_demand_class not in {
            "low", "medium", "high"
        }:
            raise RotationError("Invalid water demand class.")

        if self.residue_return_kg_ha < 0:
            raise RotationError("Residue return cannot be negative.")

        if self.nitrogen_contribution_kg_ha < 0:
            raise RotationError("Nitrogen contribution cannot be negative.")

    @classmethod
    def from_mapping(cls, item: Mapping[str, Any]):

        return cls(
            crop=str(item["crop"]),
            season=str(item.get("season", "unspecified")),
            family=str(item.get("family", "unknown")),
            root_depth_class=str(
                item.get("root_depth_class", "medium")
            ).lower(),
            nitrogen_fixing=bool(
                item.get("nitrogen_fixing", False)
            ),
            residue_return_kg_ha=float(
                item.get("residue_return_kg_ha", 0)
            ),
            nitrogen_contribution_kg_ha=float(
                item.get("nitrogen_contribution_kg_ha", 0)
            ),
            water_demand_class=str(
                item.get("water_demand_class", "medium")
            ).lower()
        )


def evaluate_rotation(
    crops: Sequence[CropInRotation | Mapping[str, Any]],
    minimum_family_gap=2,
    family_repeat_penalty=25,
    legume_after_cereal_bonus=8,
    root_depth_alternation_bonus=4
):
    """
    Evaluate a multi-season crop rotation.

    The score is a heuristic from 0 to 100, not a yield prediction.
    """

    if minimum_family_gap < 1:
        raise RotationError(
            "Minimum family gap must be at least 1."
        )

    sequence = [
        crop if isinstance(crop, CropInRotation)
        else CropInRotation.from_mapping(crop)
        for crop in crops
    ]

    if not sequence:
        raise RotationError("At least one crop is required.")

    score = 100.0

    issues = []
    benefits = []

    family_positions = {}

    for index, crop in enumerate(sequence):

        family = crop.family.casefold()

        family_positions.setdefault(family, []).append(index)

        if index == 0:
            continue

        previous = sequence[index - 1]

        if family == previous.family.casefold():

            score -= family_repeat_penalty

            issues.append({
                "type": "consecutive_same_family",
                "season_index": index,
                "crop": crop.crop,
                "family": crop.family
            })

        elif (
            previous.family.casefold() in {
                "poaceae", "gramineae", "grass"
            }
            and crop.nitrogen_fixing
        ):

            score += legume_after_cereal_bonus

            benefits.append({
                "type": "legume_after_cereal",
                "season_index": index
            })

        if crop.root_depth_class != previous.root_depth_class:

            score += root_depth_alternation_bonus

            benefits.append({
                "type": "root_depth_alternation",
                "season_index": index
            })

    for family, positions in family_positions.items():

        for first, second in zip(positions, positions[1:]):

            gap = second - first

            if gap < minimum_family_gap:

                penalty = (
                    family_repeat_penalty
                    * (minimum_family_gap - gap)
                    / minimum_family_gap
                )

                score -= penalty

                issues.append({
                    "type": "family_gap_below_minimum",
                    "family": family,
                    "first_index": first,
                    "next_index": second,
                    "gap": gap
                })

    nitrogen_total = sum(
        crop.nitrogen_contribution_kg_ha
        for crop in sequence
    )

    residue_total = sum(
        crop.residue_return_kg_ha
        for crop in sequence
    )

    score = max(0, min(100, score))

    return {

        "rotation_score": round(score, 2),

        "score_type": "heuristic_rotation_score_0_to_100",

        "seasons": [
            asdict(crop) for crop in sequence
        ],

        "nitrogen_contribution_total_kg_ha": round(
            nitrogen_total, 2
        ),

        "residue_return_total_kg_ha": round(
            residue_total, 2
        ),

        "issues": issues,

        "benefits": benefits,

        "interpretation": (
            "Higher scores indicate better alignment with "
            "configured crop rotation rules. This is not a "
            "measured soil-health or yield outcome."
        )
    }


def compare_rotations(rotations, **kwargs):
    """Evaluate and rank multiple candidate crop rotations."""

    results = []

    for name, crops in rotations.items():

        result = evaluate_rotation(crops, **kwargs)

        results.append({
            "rotation_name": name,
            **result
        })

    return sorted(
        results,
        key=lambda item: item["rotation_score"],
        reverse=True
    )