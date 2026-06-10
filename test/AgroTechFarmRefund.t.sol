// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title Lane-A target #4 — AgroTechFarm Crowdsale stuck-refund recovery (fork-proof)
/// @notice The FIRST target found by the GENERALIZED open-refund detector
///         (scripts/detect_open_refund.py, task #5), then proven here. Same
///         BROADENED class as Ahoolee/jincor — an *intended* refund left open —
///         but reached via the enum-state openness variant (a RefundVault-style
///         `state == State.Refunding`) rather than a bool cap flag.
///
///   AgroTechFarmCrowdsale (0x3fD3…8869, solc 0.4.x, holds 16.69 ETH): the 2018
///   sale's softcap was never reached, so enableRefunds() was called and the sale
///   sits permanently in `state == State.Refunding`. refund() is therefore open:
///       function refund() public {
///           require(state == State.Refunding);
///           uint value = balances[msg.sender];   // the caller's OWN ETH deposit
///           balances[msg.sender] = 0;            // zeroed => unclaimed iff balances()>0
///           msg.sender.transfer(value);          // pays the caller
///       }
///   12 contributors still have balances()>0 (16.69 ETH, all EOA, fully covered).
///   Each can reclaim their OWN deposit — pays msg.sender => NOT front-runnable => LOW.
///
///   Durability: state can only change via enableRefunds()/closeRefunds(), both of
///   which require state == State.Active. Since state == State.Refunding, NEITHER
///   can fire again, so the refund path is frozen open and the owner cannot drain.
contract AgroTechFarmRefundTest is Test {
    address constant SALE = 0x3fD30f3E1fbF4F3Ea6BDf3E3bb11826266708869;

    // Largest real UNCLAIMED rightful owner: 11.58 ETH deposit, balances()>0, EOA.
    address constant OWNER = 0xa12b9BbFdbA29e8bac265AD89350ce1d06CAcfdE;
    uint256 constant OWNER_DEPOSIT = 11.58 ether;
    // A second real unclaimed owner (2.95 ETH) — confirms the path is not owner-specific.
    address constant OWNER2 = 0x6d3fCf513c746fA1Ba2c7aE9967b75e502764F01;

    uint8 constant REFUNDING = 1; // enum State { Active, Refunding, Closed }
    uint256 constant FORK_BLOCK = 25_220_000;

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK);
    }

    function test_RightfulOwnerCanReclaimStuckRefund() public {
        // --- 0. Confirm the genuinely recoverable (open) state ---
        assertEq(_state(), REFUNDING, "precondition: state == Refunding => refund open");
        uint256 dep = _balances(OWNER);
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
        assertEq(_balances(OWNER), 0, "ledger zeroed after refund");
        console2.log("Recovered to rightful owner (ether):", (OWNER.balance - ownerEth0) / 1e18);

        // --- 3. Idempotence: ledger zeroed => a second refund moves NO further ETH.
        // (agrotech's refund has no require(value>0); it no-ops on a zero balance
        // rather than reverting — still no over-recovery.) ---
        uint256 ownerEth1 = OWNER.balance;
        vm.prank(OWNER);
        (bool twice, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertEq(OWNER.balance, ownerEth1, "a second refund must move no further ETH");
        twice; // call result irrelevant; the ETH-delta assertion is the guarantee
    }

    /// A second real unclaimed owner also recovers — the path is general, not bespoke.
    function test_SecondRightfulOwnerAlsoRecovers() public {
        uint256 dep = _balances(OWNER2);
        assertGt(dep, 0, "owner2 has an unclaimed deposit");
        uint256 before = OWNER2.balance;
        vm.prank(OWNER2);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertTrue(ok, "refund() succeeds for the second unclaimed owner");
        assertEq(OWNER2.balance - before, dep, "owner2 recovered exactly their deposit");
    }

    /// Durability: even the owner cannot drain. closeRefunds() (the only path that
    /// sends the balance to the multisig) requires state == State.Active, but state
    /// is Refunding, so it reverts; and no function can move state back to Active.
    function test_RefundPathIsDurable_ownerCannotDrain() public {
        (, bytes memory od) = SALE.staticcall(abi.encodeWithSignature("owner()"));
        address owner = abi.decode(od, (address));
        vm.prank(owner);
        (bool c, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("closeRefunds()"));
        assertFalse(c, "owner closeRefunds() must revert while state == Refunding");
        assertEq(_state(), REFUNDING, "refund stays open");
    }

    /// Negative control: a non-contributor has a zero ledger, so refund() returns
    /// their OWN (zero) deposit and moves no ETH — never someone else's funds (LOW).
    function test_NonContributorRecoversNothing() public {
        address stranger = address(0xBEEF);
        assertEq(_balances(stranger), 0, "stranger has no deposit");
        uint256 before = stranger.balance;
        vm.prank(stranger);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        ok;
        assertEq(stranger.balance, before, "a non-contributor recovers nothing");
    }

    // --- live readers ---
    function _state() internal view returns (uint8 s) {
        (, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("state()"));
        s = abi.decode(d, (uint8));
    }
    function _balances(address a) internal view returns (uint256 v) {
        (, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("balances(address)", a));
        v = abi.decode(d, (uint256));
    }
}
