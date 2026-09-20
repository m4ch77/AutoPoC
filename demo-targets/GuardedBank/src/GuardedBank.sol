// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice AutoPoC demo target (original, written for this repo).
/// The same piggy bank as PiggyBank, but SAFE: `withdraw` zeroes the caller's
/// balance BEFORE sending ETH (checks-effects-interactions), so a reentering
/// actor cannot drain the float. There is no exploit here — AutoPoC should
/// ABSTAIN (exit 1) rather than fabricate a false success.
contract GuardedBank {
    mapping(address => uint256) public balances;

    event Deposited(address indexed who, uint256 amount);
    event Withdrawn(address indexed who, uint256 amount);

    constructor() payable {}

    function deposit() external payable {
        require(msg.value > 0, "zero deposit");
        balances[msg.sender] += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    function withdraw() external {
        uint256 bal = balances[msg.sender];
        require(bal > 0, "no balance");

        balances[msg.sender] = 0;                        // state update BEFORE external call
        (bool ok, ) = msg.sender.call{value: bal}("");
        require(ok, "send failed");
        emit Withdrawn(msg.sender, bal);
    }

    receive() external payable {}
}
