// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/ArenaFactory.sol";

contract DeployScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address operatorSigner = vm.envAddress("OPERATOR_ADDRESS");
        address treasury = vm.envAddress("TREASURY_ADDRESS");
        
        vm.startBroadcast(deployerPrivateKey);
        
        ArenaFactory factory = new ArenaFactory(operatorSigner, treasury);
        
        console.log("ArenaFactory deployed at:", address(factory));
        console.log("ProofOfW deployed at:", factory.proofOfW());
        console.log("Operator Signer:", operatorSigner);
        console.log("Treasury:", treasury);
        
        vm.stopBroadcast();
    }
}
