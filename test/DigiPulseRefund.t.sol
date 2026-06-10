// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title Lane-A target #5 — DigiPulse (DGT) stuck-refund recovery (fork-proof)
/// @notice The FIRST target found by the DISCOVERY sweep (beyond ForgottenETH):
///         a free BigQuery `balances⨝contracts` pull → scan_addresses.py →
///         detect_open_refund → adversarial triage → this proof. Same broadened
///         open-refund class as Ahoolee: not an exploit, an *intended* refund left
///         open and never taken (no custody, the contributor signs, LOW legal tier).
///
///   The situation (DigiPulse.sol, 0x9aca…aa4d, solc 0.4.13, holds 100.58 ETH):
///     The Aug-2017 DGT token sale raised ~1,920 ETH against an 8,000 ETH minimum.
///     `finalise()` ran once; balance < 8000 ether so it latched `icoFailed = true`
///     (one-way — no code path ever clears it), enabling refunds:
///         function refundEther() external {
///             require(icoFailed);                       // openness latch (durable)
///             var ethValue = ethBalanceOf[msg.sender];
///             require(ethValue != 0);
///             ethBalanceOf[msg.sender] = 0;             // zero BEFORE send (CEI)
///             msg.sender.transfer(ethValue);           // pays the caller's OWN deposit
///         }
///     515 contributors already refunded; the remaining ~100.58 ETH belongs to the
///     contributors who never called refundEther. Each can still reclaim today.
///
///   Recovery (no bug): a rightful contributor calls refundEther() and gets their ETH.
///   The gate keys on msg.sender's OWN ethBalanceOf and sends to msg.sender, so it is
///   NOT front-runnable (a third party cannot redirect someone else's refund) => LOW.
///
///   Owner cannot drain: the only owner ETH-out, withdrawFundsToOwner(), is gated by
///   `require(icoFulfilled)` — false forever (finalise() already latched icoFailed and
///   self-guards `require(!icoFailed)`, so icoFulfilled can never become true). Immutable
///   (verified solc-0.4.13 source: no assembly/delegatecall/callcode/selfdestruct).
contract DigiPulseRefundTest is Test {
    address constant SALE = 0x9AcA6aBFe63A5ae0Dc6258cefB65207eC990Aa4D; // DigiPulse (DGT)

    // A real, verified UNCLAIMED rightful contributor: deposited 10 ETH in the 2017
    // sale, ethBalanceOf still 10 ETH (never called refundEther).
    address constant OWNER = 0xc4A03DbA02a43490fb94cA3c019d5bB0FE006711;
    uint256 constant OWNER_DEPOSIT = 10 ether;

    uint256 constant FORK_BLOCK = 25_270_000; // recent; state static (sale ended 2017)

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK);
    }

    function test_RightfulOwnerCanReclaimStuckRefund() public {
        // --- 0. Confirm the genuinely recoverable state (real on-chain data) ---
        uint256 deposit = _getBalanceInEth(OWNER);
        assertEq(deposit, OWNER_DEPOSIT, "precondition: owner's recorded ETH deposit");
        assertGe(SALE.balance, deposit, "precondition: contract can cover this refund");
        console2.log("Contract stuck ETH (ether):", SALE.balance / 1e18);
        console2.log("Rightful owner deposit (ether):", deposit / 1e18);

        // --- 1. THE RECOVERY: the rightful owner calls the intended refundEther() ---
        // Its success is the SOLE oracle that the icoFailed openness latch is set.
        uint256 ownerEth0 = OWNER.balance;
        uint256 saleEth0 = SALE.balance;
        vm.prank(OWNER);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refundEther()"));
        assertTrue(ok, "refundEther() should succeed for an unclaimed rightful owner");

        // --- 2. PROVE the ETH actually moved to the rightful owner ---
        assertEq(OWNER.balance - ownerEth0, deposit, "owner recovered exactly their deposit");
        assertEq(saleEth0 - SALE.balance, deposit, "contract balance dropped by the refund");
        assertEq(_getBalanceInEth(OWNER), 0, "ledger entry zeroed after refund");
        console2.log("Recovered to rightful owner (ether):", (OWNER.balance - ownerEth0) / 1e18);

        // --- 3. Idempotence: a second refundEther() must now revert (ledger zeroed) ---
        vm.prank(OWNER);
        (bool twice, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refundEther()"));
        assertFalse(twice, "double-refund must fail (no draining beyond one's deposit)");
    }

    /// Negative control: a non-contributor has no deposit, so refundEther() reverts —
    /// proving the path returns each caller's OWN funds, never someone else's (LOW tier).
    function test_NonContributorCannotRefund() public {
        address stranger = address(0xBEEF);
        assertEq(_getBalanceInEth(stranger), 0, "stranger has no deposit");
        vm.prank(stranger);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refundEther()"));
        assertFalse(ok, "a non-contributor must not be able to refund");
    }

    /// Durability: the refund path cannot be closed and the owner cannot drain.
    /// withdrawFundsToOwner() requires icoFulfilled (false forever); finalise() reverts
    /// because icoFailed is already latched. Hence the stuck ETH is durably refund-only.
    function test_RefundPathIsDurable_ownerCannotDrain() public {
        // The only owner ETH-out is gated by icoFulfilled==false and reverts for any caller.
        (bool w, ) = SALE.call{gas: 200_000}(
            abi.encodeWithSignature("withdrawFundsToOwner(uint256)", SALE.balance));
        assertFalse(w, "withdrawFundsToOwner() must revert while icoFulfilled is false");

        // finalise() cannot flip icoFulfilled true: it self-guards require(!icoFailed),
        // and icoFailed is already latched true. So openness is durable.
        (bool f, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("finalise()"));
        assertFalse(f, "finalise() must revert (icoFailed already latched) => latch durable");

        // The refund still works after these attempts (state unchanged).
        uint256 deposit = _getBalanceInEth(OWNER);
        uint256 ownerEth0 = OWNER.balance;
        vm.prank(OWNER);
        (bool ok, ) = SALE.call{gas: 200_000}(abi.encodeWithSignature("refundEther()"));
        assertTrue(ok, "refund still open after owner-drain attempts");
        assertEq(OWNER.balance - ownerEth0, deposit, "owner still recovers exactly their deposit");
    }

    // --- live reader (getBalanceInEth is read-only; staticcall-safe) ---
    function _getBalanceInEth(address a) internal view returns (uint256 v) {
        (bool ok, bytes memory d) = SALE.staticcall(
            abi.encodeWithSignature("getBalanceInEth(address)", a));
        require(ok, "getBalanceInEth read failed");
        v = abi.decode(d, (uint256));
    }
}
