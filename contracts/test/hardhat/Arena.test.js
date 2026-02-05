const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ArenaFactory", function () {
  let factory;
  let owner, operator, treasury, player1, player2, player3;

  beforeEach(async function () {
    [owner, operator, treasury, player1, player2, player3] = await ethers.getSigners();

    const ArenaFactory = await ethers.getContractFactory("ArenaFactory");
    factory = await ArenaFactory.deploy(operator.address, treasury.address);
    await factory.waitForDeployment();
  });

  it("should deploy with correct state", async function () {
    expect(await factory.owner()).to.equal(owner.address);
    expect(await factory.operatorSigner()).to.equal(operator.address);
    expect(await factory.treasury()).to.equal(treasury.address);
    expect(await factory.proofOfW()).to.not.equal(ethers.ZeroAddress);
  });

  it("should create arena", async function () {
    const entryFee = ethers.parseEther("0.1");
    const now = Math.floor(Date.now() / 1000);
    const deadline = now + 3600; // 1 hour from now

    const tx = await factory.createArena("Test Arena", entryFee, 4, 250, deadline);
    const receipt = await tx.wait();

    expect(await factory.getArenaCount()).to.equal(1);
    const arenas = await factory.getArenas();
    expect(arenas.length).to.equal(1);
    expect(await factory.isArena(arenas[0])).to.be.true;
  });

  it("should let players join arena", async function () {
    const entryFee = ethers.parseEther("0.1");
    const now = Math.floor(Date.now() / 1000);
    const deadline = now + 3600;

    await factory.createArena("Join Test", entryFee, 4, 250, deadline);
    const arenas = await factory.getArenas();
    const arenaAddress = arenas[0];

    const arena = await ethers.getContractAt("ArenaEscrow", arenaAddress);

    // Player 1 joins
    await arena.connect(player1).join({ value: entryFee });
    expect(await arena.getPlayerCount()).to.equal(1);
    expect(await arena.isPlayer(player1.address)).to.be.true;

    // Player 2 joins
    await arena.connect(player2).join({ value: entryFee });
    expect(await arena.getPlayerCount()).to.equal(2);
  });

  it("should reject wrong entry fee", async function () {
    const entryFee = ethers.parseEther("0.1");
    const now = Math.floor(Date.now() / 1000);
    const deadline = now + 3600;

    await factory.createArena("Fee Test", entryFee, 4, 250, deadline);
    const arenas = await factory.getArenas();
    const arena = await ethers.getContractAt("ArenaEscrow", arenas[0]);

    await expect(
      arena.connect(player1).join({ value: ethers.parseEther("0.05") })
    ).to.be.revertedWith("Wrong entry fee");
  });

  it("should reject double join", async function () {
    const entryFee = ethers.parseEther("0.1");
    const now = Math.floor(Date.now() / 1000);
    const deadline = now + 3600;

    await factory.createArena("Double Join Test", entryFee, 4, 250, deadline);
    const arenas = await factory.getArenas();
    const arena = await ethers.getContractAt("ArenaEscrow", arenas[0]);

    await arena.connect(player1).join({ value: entryFee });
    await expect(
      arena.connect(player1).join({ value: entryFee })
    ).to.be.revertedWith("Already joined");
  });

  it("should close registration and finalize with signature", async function () {
    const entryFee = ethers.parseEther("0.1");
    const now = Math.floor(Date.now() / 1000);
    const deadline = now + 3600;

    await factory.createArena("Finalize Test", entryFee, 4, 250, deadline);
    const arenas = await factory.getArenas();
    const arenaAddress = arenas[0];
    const arena = await ethers.getContractAt("ArenaEscrow", arenaAddress);

    // Players join
    await arena.connect(player1).join({ value: entryFee });
    await arena.connect(player2).join({ value: entryFee });

    // Close registration
    await arena.closeRegistration();
    expect(await arena.isClosed()).to.be.true;

    // Calculate prize distribution
    const totalBalance = entryFee * 2n;
    const protocolFee = (totalBalance * 250n) / 10000n;
    const prizePool = totalBalance - protocolFee;
    const firstPrize = (prizePool * 70n) / 100n;
    const secondPrize = prizePool - firstPrize;

    const winners = [player1.address, player2.address];
    const amounts = [firstPrize, secondPrize];

    // Create EIP-712 signature
    const nonce = 1;
    const chainId = (await ethers.provider.getNetwork()).chainId;

    const DOMAIN_TYPEHASH = ethers.keccak256(
      ethers.toUtf8Bytes("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
    );
    const FINALIZE_TYPEHASH = ethers.keccak256(
      ethers.toUtf8Bytes("Finalize(address arena,bytes32 winnersHash,bytes32 amountsHash,uint256 nonce)")
    );

    const domainSeparator = ethers.keccak256(
      ethers.AbiCoder.defaultAbiCoder().encode(
        ["bytes32", "bytes32", "bytes32", "uint256", "address"],
        [
          DOMAIN_TYPEHASH,
          ethers.keccak256(ethers.toUtf8Bytes("ClawArena")),
          ethers.keccak256(ethers.toUtf8Bytes("1")),
          chainId,
          arenaAddress,
        ]
      )
    );

    const winnersHash = ethers.keccak256(
      ethers.solidityPacked(["address", "address"], winners)
    );
    const amountsHash = ethers.keccak256(
      ethers.solidityPacked(["uint256", "uint256"], amounts)
    );

    const structHash = ethers.keccak256(
      ethers.AbiCoder.defaultAbiCoder().encode(
        ["bytes32", "address", "bytes32", "bytes32", "uint256"],
        [FINALIZE_TYPEHASH, arenaAddress, winnersHash, amountsHash, nonce]
      )
    );

    const digest = ethers.keccak256(
      ethers.solidityPacked(
        ["string", "bytes32", "bytes32"],
        ["\x19\x01", domainSeparator, structHash]
      )
    );

    const signature = await operator.signMessage(ethers.getBytes(digest));

    // Finalize
    const treasuryBalanceBefore = await ethers.provider.getBalance(treasury.address);

    await arena.finalize(winners, amounts, signature);

    expect(await arena.isFinalized()).to.be.true;

    // Check treasury received protocol fee
    const treasuryBalanceAfter = await ethers.provider.getBalance(treasury.address);
    expect(treasuryBalanceAfter - treasuryBalanceBefore).to.equal(protocolFee);
  });
});
