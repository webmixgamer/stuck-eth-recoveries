// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";

/// @title Lane-A discovery target — hodlEthereum stuck-deposit recovery (fork-proof)
/// @notice A net-new DISCOVERY target. The cleanest possible open-refund: a 2017
///         time-locked "hodl" vault. Each depositor's OWN ETH is credited
///         `hodlers[msg.sender] += msg.value` and reclaimable after a constant
///         unlock date via party():
///             function party() {
///                 require(block.timestamp > partyTime && hodlers[msg.sender] > 0);
///                 uint value = hodlers[msg.sender];
///                 hodlers[msg.sender] = 0;           // zero BEFORE transfer (CEI)
///                 msg.sender.transfer(value);        // pays the caller's OWN deposit
///             }
///         `partyTime` is a CONSTANT (1596067200, 30-Jul-2020) — the unlock passed
///         ~6 years ago and can never re-close. The contract has NO owner/admin, no
///         pause, no sweep — it is fully immutable (solc 0.4.11). 11 depositors never
///         withdrew; their 22.53 ETH is reclaimable today. Not front-runnable (pays
///         only the caller's own ledger) => LOW tier, owner-signs, no custody.
contract HodlEthereumRefundTest is Test {
    address constant VAULT = 0x1BB28e79f2482df6bf60efc7a33365703bCF1536; // hodlEthereum

    // Real, verified UNCLAIMED depositor (top of 11): hodlers[OWNER] = 20 ETH.
    address constant OWNER = 0xF11cC2152D3e1E44825eB4Cc71EaC0E9A6f5f2b1;

    uint256 constant FORK_BLOCK = 25_270_000;

    function setUp() public {
        vm.createSelectFork(vm.rpcUrl("mainnet"), FORK_BLOCK);
    }

    function test_RightfulOwnerCanReclaimStuckDeposit() public {
        uint256 deposit = _hodlers(OWNER);
        assertGt(deposit, 0, "precondition: owner has an unclaimed deposit");
        assertGt(block.timestamp, 1596067200, "precondition: now > partyTime (unlock passed)");
        assertGe(VAULT.balance, deposit, "precondition: contract can cover this refund");
        console2.log("Contract stuck ETH (ether):", VAULT.balance / 1e18);
        console2.log("Owner deposit (ether):", deposit / 1e18);

        uint256 ownerEth0 = OWNER.balance;
        uint256 vaultEth0 = VAULT.balance;
        vm.prank(OWNER);
        (bool ok, ) = VAULT.call{gas: 200_000}(abi.encodeWithSignature("party()"));
        assertTrue(ok, "party() should succeed for an unclaimed depositor past unlock");

        assertEq(OWNER.balance - ownerEth0, deposit, "owner recovered exactly their deposit");
        assertEq(vaultEth0 - VAULT.balance, deposit, "contract balance dropped by exactly the refund");
        assertEq(_hodlers(OWNER), 0, "ledger zeroed after refund");
        console2.log("Recovered to rightful owner (ether):", (OWNER.balance - ownerEth0) / 1e18);

        vm.prank(OWNER);
        (bool twice, ) = VAULT.call{gas: 200_000}(abi.encodeWithSignature("party()"));
        assertFalse(twice, "double-claim must fail (ledger zeroed) => not a drain");
    }

    /// Negative control: a non-depositor has no ledger entry, so party() reverts —
    /// the path returns each caller's OWN funds only (LOW tier, not front-runnable).
    function test_NonDepositorCannotClaim() public {
        address stranger = address(0xBEEF);
        assertEq(_hodlers(stranger), 0, "stranger has no deposit");
        vm.prank(stranger);
        (bool ok, ) = VAULT.call{gas: 200_000}(abi.encodeWithSignature("party()"));
        assertFalse(ok, "a non-depositor must not be able to claim");
    }

    function _hodlers(address a) internal view returns (uint256 v) {
        (bool ok, bytes memory d) = VAULT.staticcall(abi.encodeWithSignature("hodlers(address)", a));
        require(ok, "hodlers read failed");
        v = abi.decode(d, (uint256));
    }
}
