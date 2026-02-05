/**
 * CLAW ARENA - Contract Verification Script
 *
 * Verifies contracts on both Sourcify (MonadVision) and Etherscan (Monadscan).
 *
 * Usage:
 *   npx hardhat run scripts/verify.js --network monadTestnet
 *   npx hardhat run scripts/verify.js --network monadMainnet
 *
 * Note: The verify command may show errors but the contracts often verify
 * successfully anyway. Check the explorer to confirm.
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const network = hre.network.name;

  console.log("=".repeat(60));
  console.log("CLAW ARENA - Contract Verification");
  console.log("=".repeat(60));
  console.log(`Network: ${network}`);
  console.log("");

  // Load deployment data
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  const latestPath = path.join(deploymentsDir, `${network}-latest.json`);

  if (!fs.existsSync(latestPath)) {
    console.error(`No deployment found at: ${latestPath}`);
    console.error(`Run deploy first: npx hardhat run scripts/deploy.js --network ${network}`);
    process.exit(1);
  }

  const deployment = JSON.parse(fs.readFileSync(latestPath, "utf8"));
  const { ArenaFactory, ProofOfW } = deployment.contracts;

  console.log("Deployment data loaded:");
  console.log(`  ArenaFactory: ${ArenaFactory.address}`);
  console.log(`  ProofOfW:     ${ProofOfW.address}`);
  console.log(`  Deployed:     ${deployment.timestamp}`);
  console.log("");

  // Verify ArenaFactory
  console.log("--- Verifying ArenaFactory ---");
  try {
    await hre.run("verify:verify", {
      address: ArenaFactory.address,
      constructorArguments: ArenaFactory.constructorArgs,
    });
    console.log("ArenaFactory verified successfully!");
  } catch (error) {
    if (error.message.includes("Already Verified") || error.message.includes("already verified")) {
      console.log("ArenaFactory already verified.");
    } else {
      console.log(`ArenaFactory verification note: ${error.message}`);
      console.log("(Check explorer - it may still have verified via Sourcify)");
    }
  }
  console.log("");

  // Verify ProofOfW
  console.log("--- Verifying ProofOfW ---");
  try {
    await hre.run("verify:verify", {
      address: ProofOfW.address,
      constructorArguments: ProofOfW.constructorArgs,
    });
    console.log("ProofOfW verified successfully!");
  } catch (error) {
    if (error.message.includes("Already Verified") || error.message.includes("already verified")) {
      console.log("ProofOfW already verified.");
    } else {
      console.log(`ProofOfW verification note: ${error.message}`);
      console.log("(Check explorer - it may still have verified via Sourcify)");
    }
  }
  console.log("");

  // Print explorer links
  console.log("=".repeat(60));
  console.log("CHECK VERIFICATION STATUS:");
  console.log("=".repeat(60));

  if (network === "monadTestnet") {
    console.log("");
    console.log("Monadscan (Etherscan):");
    console.log(`  ArenaFactory: https://testnet.monadscan.com/address/${ArenaFactory.address}`);
    console.log(`  ProofOfW:     https://testnet.monadscan.com/address/${ProofOfW.address}`);
    console.log("");
    console.log("MonadVision (Sourcify):");
    console.log(`  ArenaFactory: https://testnet.monadvision.com/address/${ArenaFactory.address}`);
    console.log(`  ProofOfW:     https://testnet.monadvision.com/address/${ProofOfW.address}`);
  } else {
    console.log("");
    console.log("Monadscan:");
    console.log(`  ArenaFactory: https://monadscan.com/address/${ArenaFactory.address}`);
    console.log(`  ProofOfW:     https://monadscan.com/address/${ProofOfW.address}`);
    console.log("");
    console.log("MonadVision:");
    console.log(`  ArenaFactory: https://monadvision.com/address/${ArenaFactory.address}`);
    console.log(`  ProofOfW:     https://monadvision.com/address/${ProofOfW.address}`);
  }
  console.log("");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
