// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title Lane-A target #2 — Ahoolee Token Sale stuck-refund recovery (fork-proof)
/// @notice A REAL second mainnet target found via the ForgottenETH funnel. This is
///         the BROADENED recovery class: not an exploit, but an *intended* refund
///         path left open and never taken — the cleanest possible white-hat case
///         (no custody, the rightful contributor signs, LOW legal tier).
///
///   The situation (AhooleeTokenSale.sol, 0x575c…e3f7, solc 0.4.x, holds 191.5 ETH):
///     The 2017 sale raised 581 ETH but its softCap (3030 ETH) was never reached, so
///     `softCapReached == false`. refund() is therefore permanently OPEN:
///         function refund() public onlyAfter(endTime) {
///             require(!softCapReached);
///             require(!refunded[msg.sender]);
///             require(saleBalances[msg.sender] != 0);
///             uint refund = saleBalances[msg.sender];
///             require(msg.sender.send(refund));   // pays the caller's OWN deposit
///             refunded[msg.sender] = true; ...
///         }
///     216 of 322 contributors already refunded (~389.6 ETH). 106 never did — their
///     ~188 ETH is the stuck balance. Each can still reclaim their OWN deposit today.
///
///   The recovery (no bug): a rightful contributor calls refund() and gets their ETH.
///   The gate keys on msg.sender's own saleBalance and sends to msg.sender, so it is
///   NOT front-runnable (a third party cannot redirect someone else's refund) => LOW.
contract AhooleeRefundTest is Test {
    address constant SALE = 0x575cb87ab3C2329A0248C7d70e0ead8E57f3e3F7; // AhooleeTokenSale

    // A real, verified UNCLAIMED rightful owner: contributed 100 ETH, never appears
    // in the Refunded event log. (Top of 106 unclaimed contributors.)
    address constant OWNER = 0xEf58321032cF693Fa7e39F31e45CBc32f2092cb3;
    uint256 constant OWNER_DEPOSIT = 100 ether;

    // A real contributor who ALREADY refunded (present in the Refunded log) — used as
    // a negative control: their refund() must revert (refunded[] already true).
    address constant ALREADY_REFUNDED = 0x889484ceE499A0d64daeAa8578c7aDA04337b1A5;

    uint256 constant FORK_BLOCK = 25_220_000; // recent; state static since 2017

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK);
    }

    function test_RightfulOwnerCanReclaimStuckRefund() public {
        // --- 0. Confirm the genuinely recoverable state (real on-chain data) ---
        assertEq(_softCapReached(), false, "precondition: softCap not reached => refund open");
        assertGt(block.timestamp, _endTime(), "precondition: now > endTime (onlyAfter)");
        uint256 saleBal = _saleBalanceOf(OWNER);
        assertEq(saleBal, OWNER_DEPOSIT, "precondition: owner's recorded deposit");
        assertGe(SALE.balance, saleBal, "precondition: contract can cover this refund");
        console2.log("Contract stuck ETH (ether):", SALE.balance / 1e18);
        console2.log("Rightful owner deposit (ether):", saleBal / 1e18);

        // --- 1. THE RECOVERY: the rightful owner calls the intended refund() ---
        uint256 ownerEth0 = OWNER.balance;
        uint256 saleEth0 = SALE.balance;
        vm.prank(OWNER);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertTrue(ok, "refund() should succeed for an unclaimed rightful owner");

        // --- 2. PROVE the ETH actually moved to the rightful owner ---
        assertEq(OWNER.balance - ownerEth0, saleBal, "owner recovered exactly their deposit");
        assertEq(saleEth0 - SALE.balance, saleBal, "contract balance dropped by the refund");
        console2.log("Recovered to rightful owner (ether):", (OWNER.balance - ownerEth0) / 1e18);

        // --- 3. Idempotence: a second refund() must now revert (refunded[] set) ---
        vm.prank(OWNER);
        (bool twice, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(twice, "double-refund must fail (no draining beyond one's deposit)");
    }

    /// Negative control: the recovery is OWNER-SPECIFIC, not a drain.
    function test_AlreadyRefundedCannotRefundAgain() public {
        vm.prank(ALREADY_REFUNDED);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(ok, "an already-refunded contributor must not refund twice");
    }

    /// Durability: the refund path cannot be closed and the owner cannot drain.
    /// withdraw() requires softCapReached, and softCapReached can only flip inside
    /// doPurchase() — which is onlyBefore(endTime) and so reverts now. Hence the
    /// stuck ETH is durably refund-only; it cannot be redirected to the beneficiary.
    function test_RefundPathIsDurable_ownerCannotDrain() public {
        (, bytes memory od) = SALE.staticcall(abi.encodeWithSignature("owner()"));
        address owner = abi.decode(od, (address));
        vm.prank(owner);
        (bool w, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("withdraw()"));
        assertFalse(w, "owner withdraw() must revert while softCap unreached");

        // A fresh contribution must revert (sale ended) => softCapReached can't flip.
        address buyer = address(0xCAFE);
        vm.deal(buyer, 5000 ether);
        vm.prank(buyer);
        (bool bought, ) = SALE.call{value: 4000 ether, gas: 300_000}("");
        assertFalse(bought, "post-endTime contribution must revert (cannot flip softCapReached)");
        assertEq(_softCapReached(), false, "refund stays open");
    }

    /// Negative control: a non-contributor has no deposit, so refund() reverts —
    /// proving the path returns each caller's OWN funds, never someone else's (LOW tier).
    function test_NonContributorCannotRefund() public {
        address stranger = address(0xBEEF);
        assertEq(_saleBalanceOf(stranger), 0, "stranger has no deposit");
        vm.prank(stranger);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(ok, "a non-contributor must not be able to refund");
    }

    // --- live readers ---
    function _softCapReached() internal view returns (bool b) {
        (, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("softCapReached()"));
        b = abi.decode(d, (bool));
    }
    function _endTime() internal view returns (uint256 t) {
        (, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("endTime()"));
        t = abi.decode(d, (uint256));
    }
    function _saleBalanceOf(address a) internal view returns (uint256 v) {
        (, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("saleBalanceOf(address)", a));
        v = abi.decode(d, (uint256));
    }
}
