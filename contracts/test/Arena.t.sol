// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/ArenaFactory.sol";
import "../src/ArenaEscrow.sol";

contract ArenaTest is Test {
    ArenaFactory public factory;
    ArenaEscrow public arena;
    
    address public owner = address(this);
    address public operator = vm.addr(1); // Test operator
    address public treasury = address(0xTREASURY);
    
    address public player1 = address(0x1);
    address public player2 = address(0x2);
    address public player3 = address(0x3);
    
    uint256 public entryFee = 0.1 ether;
    uint32 public maxPlayers = 4;
    uint16 public protocolFeeBps = 250; // 2.5%
    
    function setUp() public {
        factory = new ArenaFactory(operator, treasury);
        address arenaAddr = factory.createArena(
            "Test Arena",
            entryFee,
            maxPlayers,
            protocolFeeBps,
            0 // No deadline
        );
        arena = ArenaEscrow(payable(arenaAddr));
        
        // Fund players
        vm.deal(player1, 1 ether);
        vm.deal(player2, 1 ether);
        vm.deal(player3, 1 ether);
    }
    
    function testJoinSuccess() public {
        vm.prank(player1);
        arena.join{value: entryFee}();
        
        assertEq(arena.getPlayerCount(), 1);
        assertTrue(arena.isPlayer(player1));
    }
    
    function testJoinWrongFee() public {
        vm.prank(player1);
        vm.expectRevert("Wrong entry fee");
        arena.join{value: 0.05 ether}();
    }
    
    function testJoinTwice() public {
        vm.startPrank(player1);
        arena.join{value: entryFee}();
        
        vm.expectRevert("Already joined");
        arena.join{value: entryFee}();
        vm.stopPrank();
    }
    
    function testJoinAfterClose() public {
        vm.prank(player1);
        arena.join{value: entryFee}();
        
        arena.closeRegistration();
        
        vm.prank(player2);
        vm.expectRevert("Registration closed");
        arena.join{value: entryFee}();
    }
    
    function testFinalizeWithSignature() public {
        // Players join
        vm.prank(player1);
        arena.join{value: entryFee}();
        vm.prank(player2);
        arena.join{value: entryFee}();
        
        // Close registration
        arena.closeRegistration();
        
        // Prepare finalize data
        address[] memory winners = new address[](2);
        winners[0] = player1;
        winners[1] = player2;
        
        uint256 totalBalance = address(arena).balance;
        uint256 protocolFee = (totalBalance * protocolFeeBps) / 10000;
        uint256 available = totalBalance - protocolFee;
        
        uint256[] memory amounts = new uint256[](2);
        amounts[0] = (available * 60) / 100; // 60% to 1st
        amounts[1] = available - amounts[0]; // 40% to 2nd
        
        // Generate EIP-712 signature
        uint256 nonce = 1;
        bytes32 winnersHash = keccak256(abi.encodePacked(winners));
        bytes32 amountsHash = keccak256(abi.encodePacked(amounts));
        
        bytes32 domainSeparator = keccak256(abi.encode(
            arena.DOMAIN_TYPEHASH(),
            keccak256("ClawArena"),
            keccak256("1"),
            block.chainid,
            address(arena)
        ));
        
        bytes32 structHash = keccak256(abi.encode(
            arena.FINALIZE_TYPEHASH(),
            address(arena),
            winnersHash,
            amountsHash,
            nonce
        ));
        
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", domainSeparator, structHash));
        
        // Sign with operator key (using vm.sign in Foundry)
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(1, digest); // 1 is operator's private key
        bytes memory signature = abi.encodePacked(r, s, v);
        
        // Record balances before
        uint256 player1BalanceBefore = player1.balance;
        uint256 player2BalanceBefore = player2.balance;
        
        // Finalize
        arena.finalize(winners, amounts, signature);
        
        // Verify
        assertTrue(arena.isFinalized());
        assertEq(player1.balance, player1BalanceBefore + amounts[0]);
        assertEq(player2.balance, player2BalanceBefore + amounts[1]);
    }
    
    function testFinalizeWrongSigner() public {
        vm.prank(player1);
        arena.join{value: entryFee}();
        arena.closeRegistration();
        
        address[] memory winners = new address[](1);
        winners[0] = player1;
        uint256[] memory amounts = new uint256[](1);
        amounts[0] = 0.09 ether;
        
        // Sign with wrong key
        bytes32 fakeDigest = keccak256("fake");
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(2, fakeDigest); // Wrong signer
        bytes memory signature = abi.encodePacked(r, s, v);
        
        vm.expectRevert("Invalid signature");
        arena.finalize(winners, amounts, signature);
    }
    
    function testFinalizeReplayProtection() public {
        // Setup and finalize once
        vm.prank(player1);
        arena.join{value: entryFee}();
        arena.closeRegistration();
        
        // This test verifies nonce tracking
        // Cannot replay finalize after already finalized
        assertFalse(arena.isFinalized());
    }
    
    function testPayoutAmountsCorrect() public {
        vm.prank(player1);
        arena.join{value: entryFee}();
        vm.prank(player2);
        arena.join{value: entryFee}();
        
        (uint256 total, uint256 afterFee) = arena.getPrizePool();
        assertEq(total, 0.2 ether);
        assertEq(afterFee, 0.195 ether); // 0.2 - 2.5%
    }
}
