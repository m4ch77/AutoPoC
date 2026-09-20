// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {LockBox} from "./src/LockBox.sol";

/// @dev Minimal cheatcode surface via the fixed Foundry VM address.
interface IVm {
    function deal(address who, uint256 amount) external;
}

/// @notice Deterministic deployment: seed the lockbox with float liquidity.
contract Setup {
    IVm constant vm = IVm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);
    uint256 constant SEED = 10 ether;

    function run() external returns (address target) {
        vm.deal(address(this), SEED);
        target = address(new LockBox{value: SEED}());
    }
}
