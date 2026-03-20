from __future__ import annotations

import asyncio

from hypo_gpt.layer3_tribunal.adversarial_critic import critique_adversarial
from hypo_gpt.layer3_tribunal.domain_critic import critique_domain
from hypo_gpt.layer3_tribunal.executability_critic import critique_executability
from hypo_gpt.layer3_tribunal.mechanism_validator import validate_mechanism
from hypo_gpt.layer3_tribunal.methodology_critic import critique_methodology
from hypo_gpt.layer3_tribunal.resource_critic import critique_resource
from hypo_gpt.models import HypothesisV2


async def run_tribunal(hypothesis: HypothesisV2) -> dict:
    domain, method, adversarial, resource, executability = await asyncio.gather(
        critique_domain(hypothesis),
        critique_methodology(hypothesis),
        critique_adversarial(hypothesis),
        critique_resource(hypothesis),
        critique_executability(hypothesis),
    )
    mechanism = validate_mechanism(hypothesis)
    return {
        "domain": domain,
        "methodology": method,
        "adversarial": adversarial,
        "resource": resource,
        "executability": executability,
        "mechanism": mechanism,
    }
