// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title Lane-A target #3 — Jincor Token ICO stuck-refund recovery (fork-proof)
/// @notice Second instance of the BROADENED open-refund class (after Ahoolee),
///         confirming the pattern generalizes across real contracts.
///
///   Jincor ICO (0xb3b3…eb5d, solc 0.4.x, holds ~19 ETH): the sale's softCap was
///   never reached (softCapReached == false), so refund() is permanently open:
///       function refund() external icoEnded {            // icoEnded: block >= endBlock
///           require(softCapReached == false);
///           require(deposited[msg.sender] > 0);
///           uint refund = deposited[msg.sender];
///           deposited[msg.sender] = 0;                    // zeroed => unclaimed iff deposited()>0
///           msg.sender.transfer(refund); ...
///       }
///   30+ contributors still have deposited()>0 (~16.7 ETH). Each can reclaim their
///   OWN deposit via the intended path — not front-runnable => LOW tier, owner-signs.
contract JincorRefundTest is Test {
    address constant SALE  = 0xB3B33F59174f2eF62167770E4C9cAbaA3879eB5d; // JincorTokenICO
    address constant OWNER = 0x916DDd79B8c8202f22451da16d32b7f96D4b0825; // real unclaimed contributor

    uint256 constant FORK_BLOCK = 25_220_000;

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK);
    }

    function test_RightfulOwnerCanReclaimStuckRefund() public {
        assertEq(_softCapReached(), false, "precondition: softCap not reached => refund open");
        uint256 dep = _deposited(OWNER);
        assertGt(dep, 0, "precondition: owner has an unclaimed deposit");
        assertGe(SALE.balance, dep, "precondition: contract can cover this refund");
        console2.log("Contract stuck ETH (ether):", SALE.balance / 1e18);
        console2.log("Owner unclaimed deposit (wei):", dep);

        uint256 ownerEth0 = OWNER.balance;
        uint256 saleEth0 = SALE.balance;
        vm.prank(OWNER);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertTrue(ok, "refund() should succeed for an unclaimed rightful owner");

        assertEq(OWNER.balance - ownerEth0, dep, "owner recovered exactly their deposit");
        assertEq(saleEth0 - SALE.balance, dep, "contract balance dropped by the refund");
        assertEq(_deposited(OWNER), 0, "ledger zeroed after refund");
        console2.log("Recovered to rightful owner (wei):", OWNER.balance - ownerEth0);

        // Idempotence: deposited now 0 => a second refund must revert.
        vm.prank(OWNER);
        (bool twice, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(twice, "double-refund must fail");
    }

    /// Durability: withdraw() requires softCapReached; softCapReached only flips in
    /// doPurchase(), which requires whitelist + active sale, so a stranger cannot flip
    /// it. The stuck ETH is durably refund-only.
    function test_RefundPathIsDurable_ownerCannotDrain() public {
        (, bytes memory od) = SALE.staticcall(abi.encodeWithSignature("owner()"));
        address owner = abi.decode(od, (address));
        vm.prank(owner);
        (bool w, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("withdraw()"));
        assertFalse(w, "owner withdraw() must revert while softCap unreached");

        // A stranger's contribution must revert (not whitelisted) => can't flip softCap.
        address buyer = address(0xCAFE);
        vm.deal(buyer, 5000 ether);
        vm.prank(buyer);
        (bool bought, ) = SALE.call{value: 4000 ether, gas: 300_000}("");
        assertFalse(bought, "stranger contribution must revert (cannot flip softCapReached)");
        assertEq(_softCapReached(), false, "refund stays open");
    }

    // Two real unclaimed owners whose 2017-2018 refund() attempts REVERTED (one
    // before endBlock = timing; one likely out-of-gas). Prove they can refund NOW.
    address constant FAILED_EARLY = 0x06953644550ba5B43E7C64CAC054aa8F09A06F14; // tried pre-endBlock
    address constant FAILED_LATER = 0x8d3004BD966006c927Cb6EE1BCa86120C53b02ef; // tried post-endBlock, reverted

    /// The refund is NOT closed: owners whose past attempts failed can still recover now.
    function test_PreviouslyFailedOwnersCanRefundNow() public {
        for (uint256 i = 0; i < 2; i++) {
            address owner = i == 0 ? FAILED_EARLY : FAILED_LATER;
            uint256 dep = _deposited(owner);
            assertGt(dep, 0, "still has an unclaimed deposit");
            uint256 before = owner.balance;
            vm.prank(owner);
            (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
            assertTrue(ok, "previously-failed owner can refund now");
            assertEq(owner.balance - before, dep, "recovers exactly their deposit");
            console2.log("recovered (wei) for previously-failed owner:", dep);
        }
    }

    /// Negative control: a non-contributor has no deposit => refund() reverts (LOW tier).
    function test_NonContributorCannotRefund() public {
        address stranger = address(0xBEEF);
        assertEq(_deposited(stranger), 0, "stranger has no deposit");
        vm.prank(stranger);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(ok, "a non-contributor must not be able to refund");
    }

    function _softCapReached() internal view returns (bool b) {
        (, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("softCapReached()"));
        b = abi.decode(d, (bool));
    }
    function _deposited(address a) internal view returns (uint256 v) {
        (, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("deposited(address)", a));
        v = abi.decode(d, (uint256));
    }
}
