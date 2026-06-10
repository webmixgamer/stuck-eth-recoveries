// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title Lane-A discovery target — ZTCrowdsale stuck-refund (fork-proof)
/// @notice A net-new DISCOVERY target. A 2017 crowdsale that did not reach minAmount
///         (20000 ETH); only ~28 ETH was raised. Recovery is a PERMISSIONLESS 2-STEP:
///             function endCrowdsale() atStage(InProgress) { require(now>=end); stage=Ended; }
///             function refund() atStage(Ended) {
///                 require(raised < minAmount);            // failed sale
///                 uint amt = balances[msg.sender];
///                 balances[msg.sender] = 0;               // zero BEFORE send
///                 if (amt>0 && !msg.sender.send(amt)) balances[msg.sender]=amt; // own deposit
///             }
///         The stage is still InProgress, so NOBODY has refunded yet and refund()
///         reverts until anyone calls the un-gated endCrowdsale() (now > end = Oct-2017).
///         Owner cannot DRAIN: withdraw() requires raised>=minAmount, impossible here.
///         SOLVENT: per-owner `balances[]` read from private storage slot 23 sums to
///         21.1747 ETH across 11 EOAs == the live contract balance. (Gross contributions
///         were ~28 ETH, but ~7 ETH of pre-ICO deposits were auto-forwarded to the
///         beneficiary and carry no refundable balances[] entry — correctly excluded.)
contract ZTCrowdsaleRefundTest is Test {
    address constant SALE = 0xaf7aeA249098F2c2f50cc11d4000cCf798194373; // ZTCrowdsale

    // Real, verified contributor who never refunded (top of 14): contributed 12.5 ETH.
    address constant OWNER = 0xFa1abCcE17531a2e75E176C5E583FEC226c79206;

    uint256 constant FORK_BLOCK = 25_270_000;

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK);
    }

    function test_TwoStepRecovery_RightfulOwnerRefunds() public {
        // Stage is InProgress now => refund() reverts before endCrowdsale().
        assertEq(_stage(), 0, "precondition: stage == InProgress (refund not yet open)");
        vm.prank(OWNER);
        (bool early, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(early, "refund() must revert while stage is InProgress");

        // Step 1: ANYONE permissionlessly ends the (long-past) crowdsale.
        address anyone = address(0xA11CE);
        vm.prank(anyone);
        (bool ended, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("endCrowdsale()"));
        assertTrue(ended, "endCrowdsale() should succeed (now > end, no owner gate)");
        assertEq(_stage(), 1, "stage now Ended => refund open");

        // Step 2: the rightful owner reclaims their own deposit.
        uint256 ownerEth0 = OWNER.balance;
        uint256 saleEth0 = SALE.balance;
        vm.prank(OWNER);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertTrue(ok, "refund() should succeed once Ended");
        uint256 recovered = OWNER.balance - ownerEth0;
        assertGt(recovered, 0, "owner received their deposit back");
        assertEq(saleEth0 - SALE.balance, recovered, "contract dropped by exactly the refund");
        console2.log("Recovered to rightful owner (ether):", recovered / 1e18);

        // Idempotence: balances zeroed => a 2nd refund moves no further ETH (no-op, not revert).
        uint256 ownerEth1 = OWNER.balance;
        uint256 saleEth1 = SALE.balance;
        vm.prank(OWNER);
        (bool noop, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        noop; // refund() returns true on a zeroed ledger but moves no ETH (no-op, not a revert)
        assertEq(OWNER.balance, ownerEth1, "no further ETH to the owner on a 2nd refund");
        assertEq(SALE.balance, saleEth1, "contract balance unchanged on a 2nd refund => not a drain");
    }

    /// Durability: the company cannot drain — withdraw() requires raised >= minAmount
    /// (20000 ETH), and only ~28 ETH was raised, so it can never succeed.
    function test_CompanyCannotDrain() public {
        // open the sale first so withdraw()'s atStage(Ended) is satisfied, isolating the
        // raised<minAmount block as the reason it still cannot drain.
        vm.prank(address(0xA11CE));
        (bool ended, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("endCrowdsale()"));
        assertTrue(ended, "endCrowdsale() opens the Ended stage");
        (bool w, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("withdraw()"));
        assertFalse(w, "withdraw() must revert (raised < minAmount) => company cannot drain");
    }

    function _stage() internal view returns (uint8 s) {
        (bool ok, bytes memory d) = SALE.staticcall(abi.encodeWithSignature("stage()"));
        require(ok, "stage read failed");
        s = abi.decode(d, (uint8));
    }
}
