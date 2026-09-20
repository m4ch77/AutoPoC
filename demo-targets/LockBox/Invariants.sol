// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice Invariant for the LockBox demo target. Healthy = the box still holds
/// at least the float it was seeded with. Emptying it via the hidden key drives
/// this to false.
contract Invariants {
    /// @dev Must match manifest.json -> deploy.value_wei for this target.
    uint256 constant SEED = 10 ether;

    function boxFunded(address target) public view returns (bool) {
        return target.balance >= SEED;
    }

    function checkAll(address target) external view returns (bool allHold, string memory firstViolated) {
        if (!boxFunded(target)) return (false, "boxFunded");
        return (true, "");
    }
}
