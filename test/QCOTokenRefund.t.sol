// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title Lane-A discovery target — QCOToken (Quantum1Net) stuck-refund (fork-proof)
/// @notice A net-new DISCOVERY target. A 2018 sale that ended in the Aborted state,
///         so requestRefund() pays each contributor back their OWN deposit:
///             function requestRefund() requireState(States.Aborted) {
///                 require(ethPossibleRefunds[msg.sender] > 0);
///                 uint refund = ethPossibleRefunds[msg.sender];
///                 ethPossibleRefunds[msg.sender] = 0;     // zero BEFORE transfer (CEI)
///                 msg.sender.transfer(refund);            // own deposit
///             }
///         57 contributors never refunded; their 31.50 ETH is the full balance. The
///         state is DURABLY Aborted (no path leaves Aborted), so the gate stays open.
///         Owner cannot DRAIN: the only owner ETH-out, requestPayout(), requires
///         States.Operational, which is unreachable from Aborted. Not front-runnable
///         (pays only the caller's own ledger) => LOW tier, owner-signs, no custody.
contract QCOTokenRefundTest is Test {
    address constant SALE = 0x3A8A97123bcCd826228e5EB4144b48cce169517B; // QCOToken

    // Real, verified UNCLAIMED contributor (top of 57): ethPossibleRefunds[OWNER] = 11.4 ETH.
    address constant OWNER = 0x0f929995C0c8a00E212dF802f57b5f63D7640FE7;

    uint256 constant FORK_BLOCK = 25_270_000;

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK);
    }

    function test_RightfulOwnerCanReclaimStuckRefund() public {
        assertEq(_state(), 3, "precondition: state == Aborted (refund open & durable)");
        uint256 deposit = _ethPossibleRefunds(OWNER);
        assertGt(deposit, 0, "precondition: owner has an unclaimed refund");
        assertGe(SALE.balance, deposit, "precondition: contract can cover this refund");
        console2.log("Contract stuck ETH (ether):", SALE.balance / 1e18);
        console2.log("Owner refund (ether):", deposit / 1e18);

        uint256 ownerEth0 = OWNER.balance;
        uint256 saleEth0 = SALE.balance;
        vm.prank(OWNER);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("requestRefund()"));
        assertTrue(ok, "requestRefund() should succeed for an unclaimed contributor");

        assertEq(OWNER.balance - ownerEth0, deposit, "owner recovered exactly their deposit");
        assertEq(saleEth0 - SALE.balance, deposit, "contract balance dropped by the refund");
        assertEq(_ethPossibleRefunds(OWNER), 0, "ledger zeroed after refund");
        console2.log("Recovered to rightful owner (ether):", (OWNER.balance - ownerEth0) / 1e18);

        vm.prank(OWNER);
        (bool twice, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("requestRefund()"));
        assertFalse(twice, "double-refund must fail (ledger zeroed)");
    }

    function test_NonContributorCannotRefund() public {
        address stranger = address(0xBEEF);
        assertEq(_ethPossibleRefunds(stranger), 0, "stranger has no refund");
        vm.prank(stranger);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("requestRefund()"));
        assertFalse(ok, "a non-contributor must not be able to refund");
    }

    function _state() internal view returns (uint8 s) {
        (bool ok, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("state()"));
        require(ok, "state read failed");
        s = abi.decode(d, (uint8));
    }
    function _ethPossibleRefunds(address a) internal view returns (uint256 v) {
        (bool ok, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("ethPossibleRefunds(address)", a));
        require(ok, "ethPossibleRefunds read failed");
        v = abi.decode(d, (uint256));
    }
}
