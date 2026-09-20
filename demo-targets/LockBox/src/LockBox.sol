// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice AutoPoC demo target (original, written for this repo).
/// A lockbox holding ETH float that anyone can empty by presenting the correct
/// numeric key. The key is a constant baked into the contract — meant to be
/// "secret", but it is plainly visible in the source, which is the weakness.
///
/// This is the CLOUD-generalization demo: blind invariant fuzzing cannot guess a
/// 256-bit key, so the offline brains abstain. A reasoning LLM reads OPEN_KEY
/// straight from the source and calls open() with it. (Needs ANTHROPIC_API_KEY.)
contract LockBox {
    uint256 private constant OPEN_KEY = 0xDEADBEEFCAFEB00B;

    constructor() payable {}

    function open(uint256 key, address payable to) external {
        require(key == OPEN_KEY, "wrong key");
        (bool ok, ) = to.call{value: address(this).balance}("");
        require(ok, "send failed");
    }

    receive() external payable {}
}
