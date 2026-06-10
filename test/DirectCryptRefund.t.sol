// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title Lane-A discovery target — DirectCrypt TokenPreSale stuck-refund (fork-proof)
/// @notice A net-new DISCOVERY target. A 2017 presale that failed its soft cap, so
///         refund() pays each contributor back their OWN deposit:
///             function refund() external preSaleEnded inNormalState {
///                 require(softCapReached == false);
///                 uint amount = deposited[msg.sender];
///                 require(amount > 0 && refunded[msg.sender] == false);
///                 deposited[msg.sender] = 0; refunded[msg.sender] = true;  // CEI
///                 msg.sender.transfer(amount);                              // own deposit
///             }
///         32 contributors never refunded; their 81.89 ETH is the full balance.
///         Owner cannot DRAIN: withdraw() (onlyOwner) requires softCapReached, which
///         can never flip (only doPurchase sets it, and the sale is ended).
///         CAVEAT (not a drain): the owner CAN halt() (reversible pause) to close
///         refund() via the inNormalState modifier; this proof confirms the gate is
///         OPEN now (refund succeeds) and that the owner cannot take the ETH.
///         Not front-runnable (pays only the caller's own deposit) => LOW tier.
contract DirectCryptRefundTest is Test {
    address constant SALE = 0x12d5b7c26DD8dc6E2F71f5bF240d5e76452b2FE5; // DirectCryptTokenPreSale

    // Real, verified UNCLAIMED contributor (top of 32): deposited[OWNER] ~= 32 ETH.
    address constant OWNER = 0x05E4A5f1A824abEB0BD2617ce2b27f8555045F88;

    uint256 constant FORK_BLOCK = 25_270_000;

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK);
    }

    function test_RightfulOwnerCanReclaimStuckRefund() public {
        uint256 deposit = _deposited(OWNER);
        assertGt(deposit, 0, "precondition: owner has an unclaimed deposit");
        assertGe(SALE.balance, deposit, "precondition: contract can cover this refund");
        console2.log("Contract stuck ETH (ether):", SALE.balance / 1e18);
        console2.log("Owner deposit (ether):", deposit / 1e18);

        // The recovery succeeding is the SOLE oracle that the openness gate
        // (softCapReached==false AND !halted AND preSaleEnded) holds at current state.
        uint256 ownerEth0 = OWNER.balance;
        uint256 saleEth0 = SALE.balance;
        vm.prank(OWNER);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertTrue(ok, "refund() should succeed for an unclaimed contributor");

        assertEq(OWNER.balance - ownerEth0, deposit, "owner recovered exactly their deposit");
        assertEq(saleEth0 - SALE.balance, deposit, "contract balance dropped by the refund");
        assertEq(_deposited(OWNER), 0, "ledger zeroed after refund");
        console2.log("Recovered to rightful owner (ether):", (OWNER.balance - ownerEth0) / 1e18);

        vm.prank(OWNER);
        (bool twice, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(twice, "double-refund must fail (ledger zeroed + refunded flag)");
    }

    function test_NonContributorCannotRefund() public {
        address stranger = address(0xBEEF);
        assertEq(_deposited(stranger), 0, "stranger has no deposit");
        vm.prank(stranger);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(ok, "a non-contributor must not be able to refund");
    }

    /// Durability: the owner cannot drain the failed-presale ETH — withdraw() requires
    /// softCapReached, which is false and can never flip (sale ended).
    function test_OwnerCannotDrain() public {
        (, bytes memory od) = SALE.staticcall(abi.encodeWithSignature("owner()"));
        address owner = abi.decode(od, (address));
        vm.prank(owner);
        (bool w, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("withdraw()"));
        assertFalse(w, "owner withdraw() must revert while softCap unreached");
    }

    function _deposited(address a) internal view returns (uint256 v) {
        (bool ok, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("deposited(address)", a));
        require(ok, "deposited read failed");
        v = abi.decode(d, (uint256));
    }
}
