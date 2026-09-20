#!/usr/bin/env python3
"""Fast, offline unit test of the agent control loop.

Proves the Reason->Act->Observe mechanics WITHOUT forge or an API key by
injecting a fake verifier and a scripted brain:
  * a wrong proposal is rejected, its failure is recorded and fed forward,
  * a correct proposal is accepted (PROVEN),
  * LLMBrain with no key degrades (returns None) so the next brain is tried.
"""

import sys
import agent_general as ag


def test_feedback_loop_converges():
    wrong = "contract Exploit { function run(address target) external payable { /* wrong */ } }"
    right = "contract Exploit { function run(address target) external payable { /* correct */ } }"

    # fake verifier: only the 'correct' candidate breaks the invariant
    def verify(code: str):
        if "correct" in code:
            return (True, "vaultSolvent", "")
        return (False, "", "")  # NOT_PROVEN, no compile error

    ctx = ag.Context(target_source="contract T{}", invariants_source="", manifest={}, target_name="T")
    brain = ag.ScriptedBrain([wrong, right])
    res = ag.solve(ctx, [brain], verify, max_attempts=6)

    assert res.found is True, "loop should converge to the correct candidate"
    assert "correct" in res.code
    assert res.violated == "vaultSolvent"
    assert len(res.history) == 2, "should take 2 attempts"
    assert res.history[0].result == "NOT_PROVEN", "1st attempt fails and is fed back"
    assert res.history[1].result == "PROVEN"
    print("PASS test_feedback_loop_converges (attempts:",
          [f'{a.n}:{a.result}' for a in res.history], ")")


def test_compile_error_is_fed_back():
    def verify(code: str):
        return (False, "", "ParserError: expected ';'")  # simulate a compile failure

    ctx = ag.Context(target_source="", invariants_source="", manifest={}, target_name="T")
    brain = ag.ScriptedBrain(["contract Exploit { function run(address t) external payable {} }"])
    res = ag.solve(ctx, [brain], verify, max_attempts=3)

    assert res.found is False
    assert res.history[0].result == "COMPILE_ERROR"
    assert "컴파일" in res.history[0].observation
    print("PASS test_compile_error_is_fed_back")


def test_llm_degrades_to_next_brain_without_key():
    # ensure no key is visible
    for k in ("ANTHROPIC_API_KEY", "LLM_API_KEY"):
        assert k not in __import__("os").environ or not __import__("os").environ[k]

    solved = "contract Exploit { function run(address target) external payable { /* correct */ } }"

    def verify(code: str):
        return (True, "ownerUnchanged", "") if "correct" in code else (False, "", "")

    ctx = ag.Context(target_source="", invariants_source="", manifest={}, target_name="T")
    llm = ag.LLMBrain(api_key=None)                 # no key -> should yield nothing
    fallback = ag.ScriptedBrain([solved])           # stands in for HeuristicBrain
    res = ag.solve(ctx, [llm, fallback], verify, max_attempts=6)

    assert res.found is True, "should fall through LLM (no key) to the fallback brain"
    assert res.history[0].brain == "scripted", "LLM produced nothing, fallback ran"
    print("PASS test_llm_degrades_to_next_brain_without_key")


if __name__ == "__main__":
    test_feedback_loop_converges()
    test_compile_error_is_fed_back()
    test_llm_degrades_to_next_brain_without_key()
    print("\nALL LOOP TESTS PASSED")
    sys.exit(0)
