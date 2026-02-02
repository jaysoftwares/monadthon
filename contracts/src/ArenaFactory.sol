// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./ArenaEscrow.sol";
import "./ProofOfW.sol";

/**
 * @title ArenaFactory
 * @notice Factory for deploying and managing CLAW ARENA tournaments
 * @dev Stores operator signer address for EIP-712 signature verification
 */
contract ArenaFactory {
    // ============ State ============
    
    address public owner;
    address public operatorSigner; // OpenClaw operator address
    address public proofOfW;       // NFT contract
    address public treasury;       // Protocol fee recipient
    
    address[] public arenas;
    mapping(address => bool) public isArena;
    
    // ============ Events ============
    
    event ArenaCreated(
        address indexed arena,
        string name,
        uint256 entryFee,
        uint32 maxPlayers,
        uint16 protocolFeeBps
    );
    event OperatorSignerUpdated(address indexed oldSigner, address indexed newSigner);
    event TreasuryUpdated(address indexed oldTreasury, address indexed newTreasury);
    
    // ============ Modifiers ============
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }
    
    // ============ Constructor ============
    
    constructor(address _operatorSigner, address _treasury) {
        owner = msg.sender;
        operatorSigner = _operatorSigner;
        treasury = _treasury;
        
        // Deploy NFT contract
        proofOfW = address(new ProofOfW());
    }
    
    // ============ Arena Creation ============
    
    function createArena(
        string calldata name,
        uint256 entryFee,
        uint32 maxPlayers,
        uint16 protocolFeeBps,
        uint64 registrationDeadline
    ) external onlyOwner returns (address arena) {
        require(maxPlayers >= 2, "Min 2 players");
        require(protocolFeeBps <= 1000, "Max 10% fee");
        
        arena = address(new ArenaEscrow(
            address(this),
            entryFee,
            maxPlayers,
            protocolFeeBps,
            treasury,
            registrationDeadline
        ));
        
        arenas.push(arena);
        isArena[arena] = true;
        
        emit ArenaCreated(arena, name, entryFee, maxPlayers, protocolFeeBps);
    }
    
    // ============ Admin Functions ============
    
    function setOperatorSigner(address _operatorSigner) external onlyOwner {
        address old = operatorSigner;
        operatorSigner = _operatorSigner;
        emit OperatorSignerUpdated(old, _operatorSigner);
    }
    
    function setTreasury(address _treasury) external onlyOwner {
        address old = treasury;
        treasury = _treasury;
        emit TreasuryUpdated(old, _treasury);
    }
    
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Zero address");
        owner = newOwner;
    }
    
    // ============ View Functions ============
    
    function getArenas() external view returns (address[] memory) {
        return arenas;
    }
    
    function getArenaCount() external view returns (uint256) {
        return arenas.length;
    }
    
    // ============ NFT Minting ============
    
    function mintProofOfW(address winner, uint256 tournamentId) external {
        require(isArena[msg.sender], "Only arena");
        ProofOfW(proofOfW).mint(winner, tournamentId, 1, "");
    }
}
