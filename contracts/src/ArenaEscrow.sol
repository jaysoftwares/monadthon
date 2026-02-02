// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./ArenaFactory.sol";

/**
 * @title ArenaEscrow
 * @notice Individual tournament escrow contract
 * @dev Handles player registration, escrow, and prize distribution
 */
contract ArenaEscrow {
    // ============ State ============
    
    ArenaFactory public immutable factory;
    uint256 public immutable entryFee;
    uint32 public immutable maxPlayers;
    uint16 public immutable protocolFeeBps;
    address public immutable treasury;
    uint64 public immutable registrationDeadline;
    
    address[] public players;
    mapping(address => bool) public isPlayer;
    
    bool public isClosed;
    bool public isFinalized;
    uint256 public usedNonce;
    
    // EIP-712 Domain
    bytes32 public constant DOMAIN_TYPEHASH = 
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");
    bytes32 public constant FINALIZE_TYPEHASH = 
        keccak256("Finalize(address arena,bytes32 winnersHash,bytes32 amountsHash,uint256 nonce)");
    
    // ============ Events ============
    
    event Joined(address indexed player);
    event RegistrationClosed();
    event Finalized(address[] winners, uint256[] amounts, bytes32 txId);
    event Payout(address indexed winner, uint256 amount);
    event ProofMinted(address indexed winner, uint256 tokenId);
    
    // ============ Modifiers ============
    
    modifier onlyFactoryOwner() {
        require(msg.sender == factory.owner(), "Not factory owner");
        _;
    }
    
    // ============ Constructor ============
    
    constructor(
        address _factory,
        uint256 _entryFee,
        uint32 _maxPlayers,
        uint16 _protocolFeeBps,
        address _treasury,
        uint64 _registrationDeadline
    ) {
        factory = ArenaFactory(_factory);
        entryFee = _entryFee;
        maxPlayers = _maxPlayers;
        protocolFeeBps = _protocolFeeBps;
        treasury = _treasury;
        registrationDeadline = _registrationDeadline;
    }
    
    // ============ Player Functions ============
    
    function join() external payable {
        require(!isClosed, "Registration closed");
        require(!isFinalized, "Already finalized");
        require(msg.value == entryFee, "Wrong entry fee");
        require(players.length < maxPlayers, "Arena full");
        require(!isPlayer[msg.sender], "Already joined");
        
        if (registrationDeadline > 0) {
            require(block.timestamp <= registrationDeadline, "Deadline passed");
        }
        
        players.push(msg.sender);
        isPlayer[msg.sender] = true;
        
        emit Joined(msg.sender);
    }
    
    // ============ Admin Functions ============
    
    function closeRegistration() external onlyFactoryOwner {
        require(!isClosed, "Already closed");
        require(!isFinalized, "Already finalized");
        
        isClosed = true;
        emit RegistrationClosed();
    }
    
    function finalize(
        address[] calldata winners,
        uint256[] calldata amounts,
        bytes calldata signature
    ) external onlyFactoryOwner {
        require(!isFinalized, "Already finalized");
        require(isClosed, "Not closed");
        require(winners.length == amounts.length, "Length mismatch");
        require(winners.length > 0, "No winners");
        
        // Calculate available balance
        uint256 totalBalance = address(this).balance;
        uint256 protocolFee = (totalBalance * protocolFeeBps) / 10000;
        uint256 availableForPayout = totalBalance - protocolFee;
        
        // Verify amounts
        uint256 totalPayout;
        for (uint256 i = 0; i < amounts.length; i++) {
            require(isPlayer[winners[i]], "Winner not player");
            totalPayout += amounts[i];
        }
        require(totalPayout <= availableForPayout, "Payout exceeds balance");
        
        // Verify EIP-712 signature
        uint256 nonce = usedNonce + 1;
        bytes32 winnersHash = keccak256(abi.encodePacked(winners));
        bytes32 amountsHash = keccak256(abi.encodePacked(amounts));
        
        bytes32 domainSeparator = keccak256(abi.encode(
            DOMAIN_TYPEHASH,
            keccak256("ClawArena"),
            keccak256("1"),
            block.chainid,
            address(this)
        ));
        
        bytes32 structHash = keccak256(abi.encode(
            FINALIZE_TYPEHASH,
            address(this),
            winnersHash,
            amountsHash,
            nonce
        ));
        
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", domainSeparator, structHash));
        address signer = recoverSigner(digest, signature);
        require(signer == factory.operatorSigner(), "Invalid signature");
        
        // Update state before transfers (CEI pattern)
        isFinalized = true;
        usedNonce = nonce;
        
        // Send protocol fee
        if (protocolFee > 0) {
            (bool feeSuccess, ) = treasury.call{value: protocolFee}("");
            require(feeSuccess, "Fee transfer failed");
        }
        
        // Distribute payouts
        bytes32 txId = keccak256(abi.encodePacked(block.timestamp, address(this), nonce));
        for (uint256 i = 0; i < winners.length; i++) {
            (bool success, ) = winners[i].call{value: amounts[i]}("");
            require(success, "Payout failed");
            emit Payout(winners[i], amounts[i]);
            
            // Mint Proof of W NFT
            uint256 tokenId = uint256(keccak256(abi.encodePacked(address(this))));
            factory.mintProofOfW(winners[i], tokenId);
            emit ProofMinted(winners[i], tokenId);
        }
        
        emit Finalized(winners, amounts, txId);
    }
    
    // ============ View Functions ============
    
    function getPlayers() external view returns (address[] memory) {
        return players;
    }
    
    function getPlayerCount() external view returns (uint256) {
        return players.length;
    }
    
    function getEscrowBalance() external view returns (uint256) {
        return address(this).balance;
    }
    
    function getPrizePool() external view returns (uint256 total, uint256 afterFee) {
        total = address(this).balance;
        afterFee = total - (total * protocolFeeBps) / 10000;
    }
    
    // ============ Internal ============
    
    function recoverSigner(bytes32 digest, bytes memory signature) internal pure returns (address) {
        require(signature.length == 65, "Invalid signature length");
        
        bytes32 r;
        bytes32 s;
        uint8 v;
        
        assembly {
            r := mload(add(signature, 32))
            s := mload(add(signature, 64))
            v := byte(0, mload(add(signature, 96)))
        }
        
        if (v < 27) v += 27;
        require(v == 27 || v == 28, "Invalid signature v");
        
        return ecrecover(digest, v, r, s);
    }
    
    // ============ Receive ============
    
    receive() external payable {
        revert("Use join()");
    }
}
