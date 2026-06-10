// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title P1 — reproduce the real HongCoin recovery on a fork (DESIGN.md Stage 3)
/// @notice We fork mainnet at a PRE-unlock block where a real ICO investor is
///         genuinely blocked, then reproduce the exact integer-overflow admin
///         reset the team used, and prove the previously-stuck refund now pays out.
///
///   The bug (HONG.sol):
///     refundMyIcoInvestment() gates on `balances[msg.sender] > tokensCreated` (line 391).
///     `tokensCreated` is decremented on every refund (line 408) while bounty tokens
///     inflate balances without bumping it — so over 9 years it degraded to 356 and
///     holders with balance > 356 became permanently blocked ("invalidTokenCount").
///
///   The escape (unchecked v0.3.5 math):
///     mgmtIssueBountyToken(addr, amount) does `balances[addr] += amount` with no
///     overflow check (line 439). Choosing amount = (1 - balance) wraps the balance
///     down to 1 (<= tokensCreated), unblocking the refund. The same wrap also slips
///     the bounty-cap check (line 252). The refund pays `weiGiven`, not balance, so
///     the holder still gets their full ETH back.
contract HongUnlockTest is Test {
    address constant HONG   = 0x9Fa8fA61A10Ff892E4EBCeB7f4e0FC684C2ce0a9; // "The HONG" (2016 ICO)
    address constant MGMT   = 0xb79Ab5993Cef2E0B714A66F3edA73b55DE812D31; // managementBodyAddress (multisig)
    address constant HOLDER = 0x521DABfd2c8b76DEaC89d44222bD3F75f388A2eC; // a real blocked ICO investor
    uint256 constant PRE_UNLOCK_BLOCK = 25_195_000;                       // before the May 2026 unlock

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), PRE_UNLOCK_BLOCK);
    }

    function test_ReproduceHongUnlock() public {
        // --- 0. Confirm the genuinely blocked starting state (real on-chain data) ---
        uint256 bal0 = _balanceOf(HOLDER);
        uint256 gate = _tokensCreated();
        console2.log("Holder token balance:", bal0);
        console2.log("tokensCreated gate:  ", gate);
        console2.log("Contract ETH (ether):", HONG.balance / 1e18);
        assertGt(bal0, gate, "precondition: holder must be blocked (balance > tokensCreated)");

        // --- 1. THE BUG: the refund is blocked and reverts ('invalidTokenCount') ---
        vm.prank(HOLDER);
        (bool refundWhileBlocked, ) = HONG.call{gas: 500_000}(
            abi.encodeWithSignature("refundMyIcoInvestment()")
        );
        assertFalse(refundWhileBlocked, "bug repro: blocked holder's refund must revert");
        console2.log("Step 1: refund while blocked reverted, as expected");

        // --- 2. THE RECOVERY: management body resets the balance to 1 via overflow ---
        uint256 amount;
        unchecked { amount = 1 - bal0; } // == 2**256 - (bal0 - 1); wraps balances[HOLDER] to 1
        vm.prank(MGMT);
        (bool unlockOk, ) = HONG.call(
            abi.encodeWithSignature("mgmtIssueBountyToken(address,uint256)", HOLDER, amount)
        );
        assertTrue(unlockOk, "recovery: overflow reset call must succeed");
        assertEq(_balanceOf(HOLDER), 1, "recovery: holder balance must be reset to 1");
        console2.log("Step 2: overflow reset holder balance to", _balanceOf(HOLDER));

        // --- 3. THE FIX CONFIRMED: the previously-blocked refund now pays the holder ---
        uint256 ethBefore = HOLDER.balance;
        vm.prank(HOLDER);
        (bool refundOk, ) = HONG.call(abi.encodeWithSignature("refundMyIcoInvestment()"));
        assertTrue(refundOk, "fix: previously-blocked refund must now succeed");

        uint256 recovered = HOLDER.balance - ethBefore;
        console2.log("Step 3: refund succeeded; ETH recovered (wei):  ", recovered);
        console2.log("Step 3: ETH recovered (ether):", recovered / 1e18);
        assertGt(recovered, 0, "fix: holder must receive their refund");
        assertEq(_balanceOf(HOLDER), 0, "fix: balance zeroed after a successful refund");
    }

    // --- read helpers (call the deployed v0.3.5 bytecode) ---
    function _balanceOf(address a) internal view returns (uint256) {
        (bool ok, bytes memory ret) = HONG.staticcall(abi.encodeWithSignature("balanceOf(address)", a));
        require(ok, "balanceOf failed");
        return abi.decode(ret, (uint256));
    }
    function _tokensCreated() internal view returns (uint256) {
        (bool ok, bytes memory ret) = HONG.staticcall(abi.encodeWithSignature("tokensCreated()"));
        require(ok, "tokensCreated failed");
        return abi.decode(ret, (uint256));
    }
}
