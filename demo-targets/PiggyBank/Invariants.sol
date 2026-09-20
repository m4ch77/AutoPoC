// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice Invariant predicates for the PiggyBank demo target.
/// Each predicate is `view`: true = property holds (healthy), false = violated
/// (attack succeeded). `checkAll` bundles them in manifest-declared order.
contract Invariants {
    /// @dev Must match manifest.json -> deploy.value_wei for this target.
    uint256 constant SEED = 10 ether;

    /// @notice The bank must always hold at least the float it was seeded with.
    /// An honest deposit+withdraw nets to zero, so dropping below the seed means
    /// a genuine accounting/reentrancy bug drained it.
    function bankSolvent(address target) public view returns (bool) {
        return target.balance >= SEED;
    }

    function checkAll(address target) external view returns (bool allHold, string memory firstViolated) {
        if (!bankSolvent(target)) return (false, "bankSolvent");
        return (true, "");
    }
}
