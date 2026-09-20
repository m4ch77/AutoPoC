// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice Invariant predicates for the GuardedBank demo target (same property
/// as PiggyBank). true = healthy, false = violated. This target is safe, so a
/// correct agent never drives this to false.
contract Invariants {
    /// @dev Must match manifest.json -> deploy.value_wei for this target.
    uint256 constant SEED = 10 ether;

    /// @notice The bank must always hold at least the float it was seeded with.
    function bankSolvent(address target) public view returns (bool) {
        return target.balance >= SEED;
    }

    function checkAll(address target) external view returns (bool allHold, string memory firstViolated) {
        if (!bankSolvent(target)) return (false, "bankSolvent");
        return (true, "");
    }
}
