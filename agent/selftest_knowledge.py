#!/usr/bin/env python3
"""Verify the DeFiHackLabs knowledge-card wiring (offline, no LLM, no forge).

Checks:
  1. A classified target injects its matching card into the LLM prompt.
  2. An unknown/empty class injects NOTHING (graceful degrade).
  3. route() sets ctx.vuln_class from triage.top so the injection can fire.
  4. Cards are static -> same class produces the byte-identical prompt (determinism).
"""

import sys

import knowledge
import agent_combined as ac
from agent_general import Context


def _ctx(vuln_class: str, src: str = "contract T {}") -> Context:
    return Context(
        target_source=src,
        invariants_source="contract Invariants {}",
        manifest={"invariants": {"predicates": ["protocolSolvent"]}},
        target_name="T",
        vuln_class=vuln_class,
    )


def _user_msg(ctx: Context) -> str:
    msgs = ac._build_messages("SYS", ctx, [])
    return next(m["content"] for m in msgs if m["role"] == "user")


def test_card_injected_for_known_class():
    u = _user_msg(_ctx("oracle"))
    assert "LIKELY CLASS: oracle" in u, "class hint missing"
    assert "price-oracle manipulation" in u, "oracle card body missing"
    assert knowledge.card_for("oracle") in u, "full card not embedded"
    print("PASS injected oracle card into LLM prompt")


def test_no_card_for_unknown():
    for cls in ("unknown", ""):
        u = _user_msg(_ctx(cls))
        assert "LIKELY CLASS" not in u, f"unexpected hint for {cls!r}"
        assert "ATTACK PATTERN" not in u, f"unexpected card for {cls!r}"
    print("PASS no card injected for unknown/empty class (graceful degrade)")


def test_all_triage_classes_have_a_card():
    import triage
    for cls in triage.VULN_CLASSES:
        assert knowledge.card_for(cls), f"missing card for {cls}"
    print(f"PASS all {len(triage.VULN_CLASSES)} triage classes map to a card")


def test_route_sets_vuln_class():
    # A minimal access-control target: unguarded owner setter.
    src = (
        "// SPDX-License-Identifier: MIT\npragma solidity 0.8.24;\n"
        "contract T { address public owner;\n"
        "  function setOwner(address a) external { owner = a; } }\n"
    )
    ctx = _ctx("", src=src)
    # route() classifies and MUST stamp ctx.vuln_class (contract paths unused
    # until a brain runs, so dummy paths are fine here).
    _order, tr = ac.route(ctx, "/dev/null", "/dev/null", seed=42)
    assert ctx.vuln_class == tr.top, f"route did not set vuln_class ({ctx.vuln_class!r} != {tr.top!r})"
    assert tr.top == "access_control", f"expected access_control, got {tr.top}"
    # and that class now drives a card into the prompt
    assert "LIKELY CLASS: access_control" in _user_msg(ctx)
    print(f"PASS route() stamped vuln_class={ctx.vuln_class} and it reaches the prompt")


def test_prompt_is_deterministic():
    a = _user_msg(_ctx("reentrancy"))
    b = _user_msg(_ctx("reentrancy"))
    assert a == b, "same class produced different prompts"
    print("PASS same class -> byte-identical prompt (deterministic)")


if __name__ == "__main__":
    tests = [
        test_card_injected_for_known_class,
        test_no_card_for_unknown,
        test_all_triage_classes_have_a_card,
        test_route_sets_vuln_class,
        test_prompt_is_deterministic,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print("ALL KNOWLEDGE TESTS PASSED" if not failed else f"{failed} TEST(S) FAILED")
    sys.exit(1 if failed else 0)
