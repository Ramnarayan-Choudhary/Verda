from hypo_gpt.layer2_generation.strategies.s1_gap_fill import generate_s1
from hypo_gpt.layer2_generation.strategies.s2_cross_domain import generate_s2
from hypo_gpt.layer2_generation.strategies.s3_assumption import generate_s3
from hypo_gpt.layer2_generation.strategies.s4_recombination import generate_s4
from hypo_gpt.layer2_generation.strategies.s5_failure_inv import generate_s5
from hypo_gpt.layer2_generation.strategies.s6_abductive import generate_s6
from hypo_gpt.layer2_generation.strategies.s7_constraint_relax import generate_s7

STRATEGY_BUILDERS = {
    "gap_fill": generate_s1,
    "cross_domain": generate_s2,
    "assumption_challenge": generate_s3,
    "method_recomb": generate_s4,
    "failure_inversion": generate_s5,
    "abductive": generate_s6,
    "constraint_relax": generate_s7,
}

__all__ = [
    "STRATEGY_BUILDERS",
    "generate_s1",
    "generate_s2",
    "generate_s3",
    "generate_s4",
    "generate_s5",
    "generate_s6",
    "generate_s7",
]
