"""Tests for aggregate.prompt — prompt templates (S3).

Templates are constants; only the render seams are exercised. Offline.
"""

from __future__ import annotations

from backend.backend.aggregate import prompt


def test_user_prompt_inlines_digest_and_drops_placeholder():
    out = prompt.build_user_prompt("DIGEST_BODY")

    assert "DIGEST_BODY" in out
    assert "{{DIGEST}}" not in out
    assert "atoms" in out  # the expected JSON skeleton is present


def test_user_template_keeps_the_placeholder_itself():
    # The placeholder must live in the template so builders substitute it.
    assert "{{DIGEST}}" in prompt.USER_TEMPLATE


def test_system_prompt_enforces_json_only_and_rules():
    assert "JSON" in prompt.SYSTEM_PROMPT
    assert "atoms" in prompt.SYSTEM_PROMPT
    assert "/tests/" in prompt.SYSTEM_PROMPT  # noise-path ban (rule 8)
    assert "/fixtures/" in prompt.SYSTEM_PROMPT


def test_repair_prompt_contains_raw_output_and_error():
    out = prompt.render_repair_prompt("RAW_BODY", "ERR_MSG")

    assert "RAW_BODY" in out and "ERR_MSG" in out
    assert "{{RAW_OUTPUT}}" not in out and "{{ERROR}}" not in out


def test_learn_prompt_contains_both_outputs():
    out = prompt.render_learn_prompt("LOCAL_ANS", "API_ANS")

    assert "LOCAL_ANS" in out and "API_ANS" in out
    assert "{{LOCAL_OUTPUT}}" not in out and "{{API_OUTPUT}}" not in out
    # Loose format on purpose (learning material, not a product artifact): the
    # reflection prompt asks for prose notes, not strict JSON.
    assert "2-5 句" in prompt.LEARN_TEMPLATE
    assert "不要 JSON" in prompt.LEARN_TEMPLATE
