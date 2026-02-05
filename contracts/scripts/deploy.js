/**
 * CLAW ARENA - Deployment Script for Monad
 *
 * Deploys:
 *   1. ArenaFactory (which internally deploys ProofOfW)
 *
 * Usage:
 *   npx hardhat run scripts/deploy.js --network monadTestnet
 *   npx hardhat run scripts/deploy.js --network monadMainnet
 *
 * Required env vars:
 *   DEPLOYER_PRIVATE_KEY  - Private key of the deployer wallet
 *   OPERATOR_ADDRESS      - Address of the OpenClaw operator signer
 *   TREASURY_ADDRESS      - Address that receives protocol fees
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const network = hre.network.name;
  const chainId = hre.network.config.chainId;

  console.log("=".repeat(60));
  console.log("CLAW ARENA - Contract Deployment");
  console.log("=".repeat(60));
  console.log(`Network:  ${network}`);
  console.log(`Chain ID: ${chainId}`);
  console.log("");

  // Get deployer
  const [deployer] = await hre.ethers.getSigners();
  const deployerAddress = await deployer.getAddress();
  const balance = await hre.ethers.provider.getBalance(deployerAddress);

  console.log(`Deployer: ${deployerAddress}`);
  console.log(`Balance:  ${hre.ethers.formatEther(balance)} MON`);
  console.log("");

  // Validate env vars
  const operatorAddress = process.env.OPERATOR_ADDRESS;
  const treasuryAddress = process.env.TREASURY_ADDRESS;

  if (!operatorAddress) {
    console.error("ERROR: OPERATOR_ADDRESS not set in .env");
    console.error("This is the OpenClaw agent signer address.");
    process.exit(1);
  }

  if (!treasuryAddress) {
    console.error("ERROR: TREASURY_ADDRESS not set in .env");
    console.error("This is the address that receives protocol fees.");
    process.exit(1);
  }

  console.log(`Operator Signer: ${operatorAddress}`);
  console.log(`Treasury:        ${treasuryAddress}`);
  console.log("");

  // Check balance
  if (balance === 0n) {
    console.error("ERROR: Deployer has 0 MON. Get testnet funds from the faucet:");
    console.error("  https://testnet.monad.xyz/");
    process.exit(1);
  }

  console.log("Deploying ArenaFactory...");
  console.log("  (This also deploys ProofOfW internally)");
  console.log("");

  // Deploy ArenaFactory
  const ArenaFactory = await hre.ethers.getContractFactory("ArenaFactory");
  const factory = await ArenaFactory.deploy(operatorAddress, treasuryAddress);
  await factory.waitForDeployment();

  const factoryAddress = await factory.getAddress();
  console.log(`ArenaFactory deployed: ${factoryAddress}`);

  // Get ProofOfW address (deployed by factory constructor)
  const proofOfWAddress = await factory.proofOfW();
  console.log(`ProofOfW deployed:    ${proofOfWAddress}`);
  console.log("");

  // Verify factory owner
  const owner = await factory.owner();
  const operator = await factory.operatorSigner();
  const treasury = await factory.treasury();

  console.log("Verification:");
  console.log(`  Owner:    ${owner}`);
  console.log(`  Operator: ${operator}`);
  console.log(`  Treasury: ${treasury}`);
  console.log(`  ProofOfW: ${proofOfWAddress}`);
  console.log("");

  // Save deployment info
  const deployment = {
    network: network,
    chainId: chainId,
    deployer: deployerAddress,
    timestamp: new Date().toISOString(),
    contracts: {
      ArenaFactory: {
        address: factoryAddress,
        constructorArgs: [operatorAddress, treasuryAddress],
      },
      ProofOfW: {
        address: proofOfWAddress,
        constructorArgs: [],
        note: "Deployed internally by ArenaFactory constructor",
      },
    },
  };

  const deploymentsDir = path.join(__dirname, "..", "deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const filename = `${network}-${Date.now()}.json`;
  const filepath = path.join(deploymentsDir, filename);
  fs.writeFileSync(filepath, JSON.stringify(deployment, null, 2));
  console.log(`Deployment saved: deployments/${filename}`);

  // Also save a "latest" file for easy reference
  const latestPath = path.join(deploymentsDir, `${network}-latest.json`);
  fs.writeFileSync(latestPath, JSON.stringify(deployment, null, 2));
  console.log(`Latest saved:     deployments/${network}-latest.json`);

  console.log("");
  console.log("=".repeat(60));
  console.log("DEPLOYMENT COMPLETE");
  console.log("=".repeat(60));
  console.log("");
  console.log("Next steps:");
  console.log(`  1. Verify contracts:`);
  console.log(`     npx hardhat run scripts/verify.js --network ${network}`);
  console.log("");
  console.log(`  2. Update backend .env with:`);
  console.log(`     ${network.includes("Testnet") ? "TESTNET" : "MAINNET"}_ARENA_FACTORY_ADDRESS=${factoryAddress}`);
  console.log(`     ${network.includes("Testnet") ? "TESTNET" : "MAINNET"}_TREASURY_ADDRESS=${treasuryAddress}`);
  console.log(`     OPERATOR_ADDRESS=${operatorAddress}`);
  console.log("");
  console.log(`  3. View on explorer:`);
  if (network === "monadTestnet") {
    console.log(`     https://testnet.monadscan.com/address/${factoryAddress}`);
  } else {
    console.log(`     https://monadscan.com/address/${factoryAddress}`);
  }
  console.log("");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
