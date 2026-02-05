/**
 * CLAW ARENA - Create Arena Script
 *
 * Creates a new ArenaEscrow tournament via the ArenaFactory.
 *
 * Usage:
 *   npx hardhat run scripts/create-arena.js --network monadTestnet
 *
 * Required env vars:
 *   DEPLOYER_PRIVATE_KEY  - Factory owner private key
 *
 * Optional env vars (or edit defaults below):
 *   ARENA_NAME            - Tournament name
 *   ARENA_ENTRY_FEE       - Entry fee in MON (e.g., "0.01")
 *   ARENA_MAX_PLAYERS     - Max players (e.g., 8)
 *   ARENA_PROTOCOL_FEE    - Protocol fee in basis points (e.g., 250 = 2.5%)
 *   ARENA_REG_DEADLINE    - Registration deadline in minutes from now (e.g., 60)
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const network = hre.network.name;

  console.log("=".repeat(60));
  console.log("CLAW ARENA - Create New Arena");
  console.log("=".repeat(60));
  console.log(`Network: ${network}`);
  console.log("");

  // Load deployment
  const deploymentsDir = path.join(__dirname, "..", "deployments");
  const latestPath = path.join(deploymentsDir, `${network}-latest.json`);

  if (!fs.existsSync(latestPath)) {
    console.error(`No deployment found. Run deploy first.`);
    process.exit(1);
  }

  const deployment = JSON.parse(fs.readFileSync(latestPath, "utf8"));
  const factoryAddress = deployment.contracts.ArenaFactory.address;

  // Arena parameters
  const name = process.env.ARENA_NAME || "Claw Arena Tournament #1";
  const entryFeeMON = process.env.ARENA_ENTRY_FEE || "0.01";
  const entryFeeWei = hre.ethers.parseEther(entryFeeMON);
  const maxPlayers = parseInt(process.env.ARENA_MAX_PLAYERS || "8");
  const protocolFeeBps = parseInt(process.env.ARENA_PROTOCOL_FEE || "250");
  const regDeadlineMinutes = parseInt(process.env.ARENA_REG_DEADLINE || "60");

  // Calculate registration deadline as unix timestamp
  const now = Math.floor(Date.now() / 1000);
  const registrationDeadline = now + (regDeadlineMinutes * 60);

  console.log("Arena Parameters:");
  console.log(`  Name:                 ${name}`);
  console.log(`  Entry Fee:            ${entryFeeMON} MON (${entryFeeWei} wei)`);
  console.log(`  Max Players:          ${maxPlayers}`);
  console.log(`  Protocol Fee:         ${protocolFeeBps / 100}% (${protocolFeeBps} bps)`);
  console.log(`  Registration Deadline: ${regDeadlineMinutes} min from now`);
  console.log(`  Deadline Timestamp:   ${registrationDeadline}`);
  console.log(`  Factory:              ${factoryAddress}`);
  console.log("");

  // Connect to factory
  const [deployer] = await hre.ethers.getSigners();
  const factory = await hre.ethers.getContractAt("ArenaFactory", factoryAddress, deployer);

  // Create arena
  console.log("Creating arena...");
  const tx = await factory.createArena(
    name,
    entryFeeWei,
    maxPlayers,
    protocolFeeBps,
    registrationDeadline
  );

  console.log(`Transaction hash: ${tx.hash}`);
  console.log("Waiting for confirmation...");

  const receipt = await tx.wait();
  console.log(`Confirmed in block: ${receipt.blockNumber}`);

  // Get the arena address from the event
  const arenaCreatedEvent = receipt.logs.find(log => {
    try {
      const parsed = factory.interface.parseLog(log);
      return parsed && parsed.name === "ArenaCreated";
    } catch {
      return false;
    }
  });

  let arenaAddress;
  if (arenaCreatedEvent) {
    const parsed = factory.interface.parseLog(arenaCreatedEvent);
    arenaAddress = parsed.args.arena;
  } else {
    // Fallback: get last arena from factory
    const arenas = await factory.getArenas();
    arenaAddress = arenas[arenas.length - 1];
  }

  console.log("");
  console.log("=".repeat(60));
  console.log(`ARENA CREATED: ${arenaAddress}`);
  console.log("=".repeat(60));
  console.log("");

  if (network === "monadTestnet") {
    console.log(`View on Monadscan: https://testnet.monadscan.com/address/${arenaAddress}`);
    console.log(`TX: https://testnet.monadscan.com/tx/${tx.hash}`);
  } else {
    console.log(`View on Monadscan: https://monadscan.com/address/${arenaAddress}`);
    console.log(`TX: https://monadscan.com/tx/${tx.hash}`);
  }
  console.log("");
  console.log("Update backend .env with this arena address, or");
  console.log("use the backend API to register it.");
  console.log("");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
