// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title P0 fork smoke test
/// @notice Proves the foundation of the whole project: we can fork Ethereum
///         mainnet (via your Alchemy key) and read the *real* on-chain state of
///         a contract — entirely inside a local sandbox, touching nothing on the
///         real chain and spending no gas. This is Stage 3 ("proof-on-fork") of
///         DESIGN.md in miniature.
///
///         The target is the HongCoin contract from docs/story.md — the 2016 ICO
///         whose ~$2M was freed after 9 years. Fitting first contract to read.
contract ForkSmokeTest is Test {
    // HongCoin (2016 ICO). EIP-55 checksummed address.
    address constant HONGCOIN = 0x9Fa8fA61A10Ff892E4EBCeB7f4e0FC684C2ce0a9;

    function setUp() public {
        // Create + select a fork of mainnet at the latest block.
        // "mainnet" resolves to ALCHEMY_RPC_URL from .env (see foundry.toml).
        vm.createSelectFork(vm.rpcUrl("mainnet"));
    }

    function test_CanReadRealChainState() public view {
        uint256 blockNo = block.number;
        uint256 codeSize = HONGCOIN.code.length;
        uint256 balanceWei = HONGCOIN.balance;

        console2.log("Forked mainnet at block: ", blockNo);
        console2.log("HongCoin deployed bytecode size (bytes):", codeSize);
        console2.log("HongCoin ETH balance (wei):  ", balanceWei);

        // We really pulled mainnet state if the block number is far past genesis...
        assertGt(blockNo, 15_000_000, "fork should be a recent mainnet block");
        // ...and if the target address actually has deployed contract code.
        assertGt(codeSize, 0, "HongCoin should have real deployed bytecode on-chain");
    }
}
