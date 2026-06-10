// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title Lane-A discovery target — Blocklancer (LNC) stuck-refund (fork-proof)
/// @notice A net-new DISCOVERY target. A 2017 token sale that did not reach its
///         minimum cap, so refund() pays each contributor back their OWN deposit:
///             function refund() external {
///                 if(!funding) throw;                       // not finalized
///                 if(block.timestamp <= fundingEnd) throw;  // sale ended
///                 if(totalTokens >= tokenCreationMin) throw;// min not reached (failed)
///                 var ethValue = balancesEther[msg.sender];
///                 ... balances/balancesEther[msg.sender] = 0;  // zero BEFORE send (CEI)
///                 if(!msg.sender.send(ethValue)) throw;        // own deposit
///             }
///         28 contributors never refunded; their 21.66 ETH is the full balance.
///         Owner cannot DRAIN: the only master ETH-out is finalize() ->
///         master.send(this.balance), which THROWS unless totalTokens+5000e18 >=
///         tokenCreationCap — impossible for this failed raise. (And refund succeeding
///         proves `funding` is still true, i.e. not yet finalized.) Not front-runnable
///         (pays only the caller's own ledger) => LOW tier, owner-signs, no custody.
contract BlocklancerRefundTest is Test {
    address constant SALE = 0x9EA80e204045329Ba752D03C395F82A12799f13d; // BlocklancerToken

    // Real, verified contributor who NEVER refunded (top of 28): contributed 7 ETH.
    address constant OWNER = 0x61e120B9ca6559961982D9Bd1b1dbeA7485B84d1;

    uint256 constant FORK_BLOCK = 25_270_000;

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK);
    }

    function test_RightfulOwnerCanReclaimStuckRefund() public {
        // balancesEther is a PRIVATE mapping (no getter) — we prove via balance deltas:
        // the owner's gain equals the contract's drop, and a 2nd call reverts.
        assertGe(SALE.balance, 7 ether, "precondition: contract holds the stuck refunds");
        uint256 ownerEth0 = OWNER.balance;
        uint256 saleEth0 = SALE.balance;

        // The recovery succeeding is the SOLE oracle that the gate holds now
        // (funding still true, sale ended, min not reached).
        vm.prank(OWNER);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertTrue(ok, "refund() should succeed for a never-refunded contributor");

        uint256 recovered = OWNER.balance - ownerEth0;
        assertGt(recovered, 0, "owner received their deposit back");
        assertEq(saleEth0 - SALE.balance, recovered, "contract dropped by exactly the refund (self-paying)");
        console2.log("Recovered to rightful owner (ether):", recovered / 1e18);

        // Idempotence: ledger zeroed => a 2nd refund reverts (lncValue==0 throw).
        vm.prank(OWNER);
        (bool twice, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(twice, "double-refund must fail (ledger zeroed) => not a drain");
    }

    /// Negative control: a non-contributor has no token ledger, so refund() reverts.
    function test_NonContributorCannotRefund() public {
        address stranger = address(0xBEEF);
        vm.prank(stranger);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refund()"));
        assertFalse(ok, "a non-contributor must not be able to refund");
    }

    /// Durability: master cannot drain the failed-raise ETH — finalize() reverts
    /// (totalTokens+5000e18 < tokenCreationCap), so master.send(this.balance) is unreachable.
    function test_MasterCannotDrain() public {
        (, bytes memory md) = SALE.staticcall(abi.encodeWithSignature("master()"));
        address master = abi.decode(md, (address));
        vm.prank(master);
        (bool f, ) = SALE.call{gas: 300_000}(abi.encodeWithSignature("finalize()"));
        assertFalse(f, "finalize() must revert => master cannot drain the failed-raise ETH");
    }
}
