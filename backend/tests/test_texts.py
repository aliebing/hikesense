"""Both reply languages carry every fixed sentence."""

import dataclasses

import pytest

from hikeall.agent import prompts
from hikeall.agent.texts import DE, EN, TEXTS, texts

# fields whose English and German wording is legitimately identical
SAME_IN_BOTH: set[str] = set()


@pytest.mark.parametrize("f", [f.name for f in dataclasses.fields(DE)])
def test_every_field_is_filled_and_translated(f):
    de, en = getattr(DE, f), getattr(EN, f)
    assert de.strip() and en.strip()
    if f not in SAME_IN_BOTH:
        assert en != de


@pytest.mark.parametrize("f", [f.name for f in dataclasses.fields(DE)])
def test_placeholders_match(f):
    import string

    def names(s):
        return {n for _, n, _, _ in string.Formatter().parse(s) if n}

    assert names(getattr(DE, f)) == names(getattr(EN, f))


def test_texts_lookup_and_german_reexport():
    assert texts("en") is EN and texts("de") is DE and set(TEXTS) == {"de", "en"}
    assert prompts.OTHER_REPLY == DE.other_reply
    assert prompts.GROUPS_CHECK_MIXED == DE.groups_check_mixed
