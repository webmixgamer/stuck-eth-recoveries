// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title Lane-A target #5 — Luckchemy Crowdsale stuck-refund recovery (fork-proof)
/// @notice Second target surfaced by the generalized open-refund detector (task #5).
///         Bool-flag openness variant (like Ahoolee/jincor), zeroed-on-refund ledger.
///
///   LuckchemyCrowdsale (0x1877…DFc, solc 0.4.x, holds 10.77 ETH): softCap (2000 ETH)
///   was never reached, so softCapReached() == false and refund() is open:
///       function refund() public {
///           require(hasEnded());
///           require(!softCapReached() || ((now > END_TIME_SALE + 30 days) && !token.released()));
///           uint256 amount = deposits[msg.sender];   // the caller's OWN ETH deposit
///           require(amount > 0);
///           deposits[msg.sender] = 0;                 // zeroed => unclaimed iff deposits()>0
///           msg.sender.transfer(amount);              // pays the caller
///       }
///   23 contributors still have deposits()>0 (10.77 ETH, all EOA, fully covered).
///   Each can reclaim their OWN deposit — pays msg.sender => NOT front-runnable => LOW.
///
///   Durability: forwardFunds() (the only owner drain path) requires softCapReached(),
///   which is permanently false (the sale has ended; the cap can no longer be met),
///   so the owner cannot redirect the stuck ETH.
contract LuckchemyRefundTest is Test {
    address constant SALE = 0x18777Aec0B231D1a4A9C66B51253088a03affDFc;

    // Largest real UNCLAIMED rightful owner: 4.0 ETH deposit, deposits()>0, EOA.
    address constant OWNER = 0x932Dd29FBD1D1Bff4C16704f8eAe879f4E968ba5;
    uint256 constant OWNER_DEPOSIT = 4 ether;
    // A second real unclaimed owner (2.0 ETH).
    address constant OWNER2 = 0x264D1405922873f8BF61F55C884eB6C77C52f469;

    uint256 constant FORK_BLOCK = 25_220_000;

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK);
    }

    function test_RightfulOwnerCanReclaimStuckRefund() public {
        // --- 0. Confirm the genuinely recoverable (open) state ---
        assertEq(_softCapReached(), false, "precondition: softCap not reached => refund open");
        assertEq(_hasEnded(), true, "precondition: sale has ended (refund requires hasEnded())");
        uint256 dep = _deposits(OWNER);
        assertEq(dep, OWNER_DEPOSIT, "precondition: owner's recorded ETH deposit");
        assertGe(SALE.balance, dep, "precondition: contract can cover this refund");
        console2.log("Contract stuck ETH (ether):", SALE.balance / 1e18);
        console2.log("Rightful owner deposit (ether):", dep / 1e18);

        // --- 1. THE RECOVERY: the rightful owner calls the intended refund() ---
        uint256 ownerEth0 = OWNER.balance;
        uint256 saleEth0 = SALE.balance;
        vm.prank(OWNER);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertTrue(ok, "refund() should succeed for an unclaimed rightful owner");

        // --- 2. PROVE the ETH actually moved to the rightful owner ---
        assertEq(OWNER.balance - ownerEth0, dep, "owner recovered exactly their deposit");
        assertEq(saleEth0 - SALE.balance, dep, "contract balance dropped by the refund");
        assertEq(_deposits(OWNER), 0, "ledger zeroed after refund");
        console2.log("Recovered to rightful owner (ether):", (OWNER.balance - ownerEth0) / 1e18);

        // --- 3. Idempotence: deposits zeroed => require(amount > 0) now reverts ---
        vm.prank(OWNER);
        (bool twice, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(twice, "double-refund must fail (require(amount > 0) after zeroing)");
    }

    /// A second real unclaimed owner also recovers — the path is general, not bespoke.
    function test_SecondRightfulOwnerAlsoRecovers() public {
        uint256 dep = _deposits(OWNER2);
        assertGt(dep, 0, "owner2 has an unclaimed deposit");
        uint256 before = OWNER2.balance;
        vm.prank(OWNER2);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertTrue(ok, "refund() succeeds for the second unclaimed owner");
        assertEq(OWNER2.balance - before, dep, "owner2 recovered exactly their deposit");
    }

    /// Durability: even the owner cannot drain. forwardFunds() requires
    /// softCapReached() == true, which is permanently false, so it reverts.
    function test_RefundPathIsDurable_ownerCannotDrain() public {
        (, bytes memory od) = SALE.staticcall(abi.encodeWithSignature("owner()"));
        address owner = abi.decode(od, (address));
        vm.prank(owner);
        (bool w, ) = SALE.call{gas: 300_000}(abi.encodeWithSignature("forwardFunds()"));
        assertFalse(w, "owner forwardFunds() must revert while softCap unreached");
        assertEq(_softCapReached(), false, "refund stays open");
    }

    /// Negative control: a non-contributor has no deposit => refund() reverts
    /// (require(amount > 0)) — proving the path returns each caller's OWN funds (LOW).
    function test_NonContributorCannotRefund() public {
        address stranger = address(0xBEEF);
        assertEq(_deposits(stranger), 0, "stranger has no deposit");
        vm.prank(stranger);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(ok, "a non-contributor must not be able to refund");
    }

    // --- live readers ---
    function _softCapReached() internal view returns (bool b) {
        (, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("softCapReached()"));
        b = abi.decode(d, (bool));
    }
    function _hasEnded() internal view returns (bool b) {
        (, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("hasEnded()"));
        b = abi.decode(d, (bool));
    }
    function _deposits(address a) internal view returns (uint256 v) {
        (, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("deposits(address)", a));
        v = abi.decode(d, (uint256));
    }
}
