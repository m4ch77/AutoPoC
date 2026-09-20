#!/usr/bin/env python3
"""Attack-pattern knowledge cards, distilled from the recurring vulnerability
classes catalogued in DeFiHackLabs (github.com/SunWeb3Sec/DeFiHackLabs).

WHY THIS EXISTS
---------------
DeFiHackLabs is ~600+ real-hack reproductions. They are mainnet-FORK based and
protocol-specific; Track04 targets are the opposite: local, no-fork, single-file
toy contracts deployed fresh in a harness. So we do NOT copy any PoC code. We
distil only the *transferable reasoning* per vulnerability class and TRANSLATE
each lesson into this harness's terms:

  * the Exploit is funded with 10 ETH before ``run(address target)`` is called;
  * ``block.number`` / ``block.timestamp`` are FIXED (no time-passing tricks);
  * there is NO external flashloan/liquidity provider -- get capital from the
    target itself (a faucet / mint / deposit path) or from the 10 ETH you hold.

HOW IT IS USED
--------------
``triage.classify()`` labels the target with one of the classes below. A card is
injected into the LLM prompt ONLY when (a) triage produced that class AND (b) an
LLM brain is actually active. The fuzzer / heuristic / reentrancy brains never
see these cards (they do not read prose). The cards are static text keyed by a
deterministic class, so injection stays fully offline and deterministic.

Content was rephrased/summarised for compliance with source licensing; these are
class-level patterns in our own words, not reproductions of DeFiHackLabs code.
"""

from __future__ import annotations

from typing import Optional

# Keyed by triage.VULN_CLASSES (+ nothing for "unknown": no card => no injection).
CARDS: dict[str, str] = {
    "reentrancy": (
        "ATTACK PATTERN — reentrancy (DeFiHackLabs class):\n"
        "The target sends ETH with `.call{value:}` BEFORE it zeroes/decrements the "
        "caller's recorded balance, and has no nonReentrant guard. Your Exploit IS "
        "the reentering actor. Steps: (1) use the payable deposit path to record a "
        "credit; (2) call the vulnerable withdraw; (3) in `receive()`, while the "
        "target still holds ETH, re-enter the withdraw to pull your credit again and "
        "again until it is drained. Cross-function variant: if the ETH is sent by one "
        "function but the balance is updated in another, re-enter the OTHER function "
        "that still sees your stale balance. Stop the recursion with a hop counter so "
        "run() terminates."
    ),
    "access_control": (
        "ATTACK PATTERN — missing access control (DeFiHackLabs class):\n"
        "A state-changing, privileged function lacks an owner/role check "
        "(`require(msg.sender==owner)`), or an `initialize()`/`init()` is left "
        "unprotected so anyone can seize ownership. Also suspect functions that trust "
        "a caller-supplied address. Exploit: from run() just call the unguarded "
        "function directly — take ownership, then call the owner-only withdraw/mint/"
        "sweep to move the assets to your Exploit, or set a parameter that breaks the "
        "invariant. No trick needed beyond calling what should have been gated."
    ),
    "arithmetic": (
        "ATTACK PATTERN — arithmetic / accounting (DeFiHackLabs class):\n"
        "Three recurring bugs: (1) UNDERFLOW — a balance is mutated inside "
        "`unchecked{}` with no `require(bal >= amount)`; transfer/burn more than you "
        "hold and your balance wraps to ~2^256, then redeem/withdraw the REAL asset. "
        "(2) PRECISION/ROUNDING — divide-before-multiply or truncating division lets "
        "you pay 0 while receiving >0; repeat to drain. (3) SHARE INFLATION / "
        "first-depositor / donation — in a shares=assets vault, deposit 1 wei to mint "
        "1 share, then `transfer` assets directly to the vault to inflate share price "
        "so the accounting/solvency invariant breaks. Pick the one the code enables."
    ),
    "oracle": (
        "ATTACK PATTERN — price-oracle manipulation (DeFiHackLabs class, the #1 DeFi "
        "hack):\nValuation is read from a manipulable source — a single AMM pool's "
        "INSTANTANEOUS reserves / spotPrice / balanceOf, with no TWAP, no staleness "
        "or deviation bound. Real hacks flashloan-pump the pool; HERE there is no "
        "flashloan, so get the input token from the target's own faucet()/mint or a "
        "cheap swap, then trade against the SAME pool the oracle reads to skew its "
        "reserves and move the reported price. Then, within the same run(): deposit a "
        "little collateral and borrow/withdraw against the INFLATED valuation, "
        "exceeding fair value so the solvency invariant (debt <= fair collateral) "
        "breaks. Do everything before any re-sync corrects the price."
    ),
    "delegatecall": (
        "ATTACK PATTERN — delegatecall / proxy (DeFiHackLabs class):\n"
        "The target `delegatecall`s an address or selector you influence, executing "
        "attacker code in the TARGET's storage context. Exploit via storage-slot "
        "collision: point the delegatecall at code that writes the slot holding "
        "`owner`/`implementation` (often slot 0), overwriting it with your address; "
        "or call an unprotected `setImplementation`/`upgradeTo` to install your logic, "
        "then invoke it to move funds or flip the invariant."
    ),
    "tx_origin": (
        "ATTACK PATTERN — tx.origin auth (DeFiHackLabs class):\n"
        "The target authorises with `tx.origin == owner` instead of `msg.sender`. "
        "This is exploitable only when a privileged origin calls THROUGH your "
        "contract. In THIS harness the caller of run() is the test/EOA, so unless the "
        "harness makes the owner your origin, tx.origin will not equal a victim owner "
        "— prefer another vector if the code offers one. Only pursue this if the "
        "target's owner is set to the very address that invokes your Exploit."
    ),
    "storage_read": (
        "ATTACK PATTERN — 'private is not secret' (DeFiHackLabs class):\n"
        "A gate checks a `private` state variable against a caller input "
        "(`require(input == secret)`) as if `private` meant confidential. On-chain "
        "storage is fully readable and you also have the SOURCE. Recover the value: if "
        "it is a literal/initialised in source, read it directly; if set in the "
        "constructor from known args, recompute it; otherwise read its storage slot. "
        "Then pass the recovered value to clear the gate and break the invariant."
    ),
    "randomness": (
        "ATTACK PATTERN — weak on-chain randomness (DeFiHackLabs class):\n"
        "The target derives a 'random' outcome from on-chain data — `blockhash`, "
        "`block.timestamp`, `block.prevrandao`/`difficulty`, often via `%` or "
        "`keccak256`. These are observable and, here, FIXED and known. Recompute the "
        "exact outcome in your Exploit using the SAME formula and the SAME block "
        "values the target sees, then call the function with the winning input in the "
        "same transaction so you deterministically hit the payout/branch."
    ),
    "selfdestruct_force": (
        "ATTACK PATTERN — forced ETH / selfdestruct (DeFiHackLabs class):\n"
        "The target assumes `address(this).balance` only moves through its own "
        "payable paths, and an invariant asserts `balance == trackedTotal`. You can "
        "force ETH in without triggering its accounting: deploy a tiny helper that "
        "`selfdestruct(payable(target))`s your ETH (or use the SENDALL path) so the "
        "real balance exceeds the tracked total and the invariant breaks. If the "
        "target itself exposes an unguarded selfdestruct/teardown, call it directly."
    ),
}


def card_for(vuln_class: Optional[str]) -> Optional[str]:
    """Return the attack-pattern card for a triage class, or None.

    None is returned for empty/``unknown``/unmapped classes, which is exactly the
    graceful-degrade path: the LLM prompt is then left unchanged.
    """
    if not vuln_class:
        return None
    return CARDS.get(vuln_class)


if __name__ == "__main__":
    # Quick self-check: every mapped class has a non-trivial card.
    import triage
    missing = [c for c in triage.VULN_CLASSES if c not in CARDS]
    print(f"classes with cards : {sorted(CARDS)}")
    print(f"triage classes     : {list(triage.VULN_CLASSES)}")
    print(f"unmapped classes   : {missing or 'none'}")
    print(f"card_for('unknown'): {card_for('unknown')!r}")
    print(f"card_for('oracle') : {len(card_for('oracle') or '')} chars")
