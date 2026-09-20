// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice AutoPoC demo target (original, written for this repo).
/// A tiny ETH piggy bank: anyone can deposit and later withdraw their own
/// recorded balance. The bank is seeded with some float liquidity at
/// deployment.
///
/// INTENTIONALLY VULNERABLE: `withdraw` sends ETH *before* it zeroes the
/// caller's balance (violates checks-effects-interactions), so a reentering
/// actor can drain the seeded float. AutoPoC should PROVE this with a
/// reentrancy Exploit.sol.
contract PiggyBank {
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

        (bool ok, ) = msg.sender.call{value: bal}(""); // external call BEFORE state update
        require(ok, "send failed");

        balances[msg.sender] = 0;
        emit Withdrawn(msg.sender, bal);
    }

    receive() external payable {}
}
