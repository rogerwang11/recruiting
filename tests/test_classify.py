"""The classifier's job is telling brands hiring apart from creators selling."""

import pytest

from xhire.classify import classify

BRANDS_HIRING = [
    "We're hiring UGC creators for a paid skincare campaign. $300 per video, DM to apply.",
    "Looking for a UGC creator to shoot 3 TikToks for our brand. Budget $500.",
    "UGC creators wanted! Open call for our spring product launch, paid collab.",
    "Our agency needs UGC creators for a client. Apply here with your portfolio.",
]

CREATORS_SELLING = [
    "I'm a UGC creator specialising in beauty. DM for my rates!",
    "Available for UGC work — my portfolio is in the link below.",
    "UGC creator open to work with skincare brands. Let's collab!",
    "Looking for brands to work with as a UGC creator. Rates start at $150.",
]

OFF_TOPIC = [
    "The UGC football match was incredible last night.",
    "We're hiring a backend engineer, Go and Postgres.",
]


@pytest.mark.parametrize("text", BRANDS_HIRING)
def test_brand_posts_score_as_hiring(text):
    score, verdict, _ = classify(text)
    assert verdict == "likely_hiring", f"{text!r} scored {score}"


@pytest.mark.parametrize("text", CREATORS_SELLING)
def test_creator_self_promo_is_rejected(text):
    score, verdict, _ = classify(text)
    assert verdict != "likely_hiring", f"{text!r} wrongly scored {score}"


@pytest.mark.parametrize("text", OFF_TOPIC)
def test_off_topic_scores_zero(text):
    score, _, _ = classify(text)
    assert score == 0


def test_supply_language_outweighs_a_single_demand_match():
    # The trap case: contains "looking for" but the poster is the creator.
    score, verdict, _ = classify(
        "Looking for brands! I'm a UGC creator, DM for my rates."
    )
    assert verdict == "creator_selling"
    assert score == 0


def test_quality_signals_do_not_lift_a_creator_rate_card():
    # "paid" and a dollar figure must not rescue self-promo.
    _, verdict, _ = classify("Paid UGC work wanted, I'm a UGC creator. $200 per video.")
    assert verdict != "likely_hiring"


def test_reasons_are_populated_for_a_hit():
    _, _, reasons = classify("We're hiring UGC creators, paid campaign.")
    assert "hiring" in reasons
