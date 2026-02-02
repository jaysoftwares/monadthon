// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title ProofOfW
 * @notice ERC-1155 NFT awarded to tournament winners
 * @dev Only the ArenaFactory can mint tokens
 */
contract ProofOfW is ERC1155, Ownable {
    string public name = "CLAW ARENA Proof of W";
    string public symbol = "POW";
    
    mapping(uint256 => string) private _tokenURIs;
    
    event ProofMinted(address indexed winner, uint256 indexed tokenId, uint256 amount);
    
    constructor() ERC1155("https://clawarena.xyz/api/nft/{id}.json") Ownable(msg.sender) {}
    
    function mint(
        address to,
        uint256 tokenId,
        uint256 amount,
        bytes memory data
    ) external onlyOwner {
        _mint(to, tokenId, amount, data);
        emit ProofMinted(to, tokenId, amount);
    }
    
    function mintBatch(
        address to,
        uint256[] memory tokenIds,
        uint256[] memory amounts,
        bytes memory data
    ) external onlyOwner {
        _mintBatch(to, tokenIds, amounts, data);
    }
    
    function setTokenURI(uint256 tokenId, string memory tokenURI) external onlyOwner {
        _tokenURIs[tokenId] = tokenURI;
    }
    
    function uri(uint256 tokenId) public view override returns (string memory) {
        string memory tokenURI = _tokenURIs[tokenId];
        if (bytes(tokenURI).length > 0) {
            return tokenURI;
        }
        return super.uri(tokenId);
    }
}
