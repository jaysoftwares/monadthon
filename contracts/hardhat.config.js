require("@nomicfoundation/hardhat-toolbox");
require("@nomicfoundation/hardhat-verify");
require("dotenv").config();

const PRIVATE_KEY = process.env.DEPLOYER_PRIVATE_KEY || "0x" + "0".repeat(64);
// Etherscan API key is OPTIONAL - Sourcify verification works without it
const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY || "";
const hasEtherscanKey = ETHERSCAN_API_KEY.length > 0;

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      viaIR: true, // Required to avoid "stack too deep" in finalize()
      optimizer: {
        enabled: true,
        runs: 200,
      },
      metadata: {
        bytecodeHash: "ipfs", // Required for Sourcify verification
      },
    },
  },

  // Use "src" as the source directory (matches existing Foundry layout)
  paths: {
    sources: "./src",
    tests: "./test/hardhat",
    cache: "./cache",
    artifacts: "./artifacts",
  },

  networks: {
    hardhat: {
      chainId: 31337,
    },
    monadTestnet: {
      url: "https://testnet-rpc.monad.xyz",
      accounts: [PRIVATE_KEY],
      chainId: 10143,
    },
    monadMainnet: {
      url: "https://rpc.monad.xyz",
      accounts: [PRIVATE_KEY],
      chainId: 143,
    },
  },

  // Sourcify verification (MonadVision)
  sourcify: {
    enabled: true,
    apiUrl: "https://sourcify-api-monad.blockvision.org",
    browserUrl: "https://testnet.monadvision.com",
  },

  // Etherscan verification (Monadscan) - only enabled if API key is provided
  etherscan: {
    enabled: hasEtherscanKey,
    apiKey: {
      monadTestnet: ETHERSCAN_API_KEY,
      monadMainnet: ETHERSCAN_API_KEY,
    },
    customChains: [
      {
        network: "monadTestnet",
        chainId: 10143,
        urls: {
          apiURL: "https://api.etherscan.io/v2/api?chainid=10143",
          browserURL: "https://testnet.monadscan.com",
        },
      },
      {
        network: "monadMainnet",
        chainId: 143,
        urls: {
          apiURL: "https://api.etherscan.io/v2/api?chainid=143",
          browserURL: "https://monadscan.com",
        },
      },
    ],
  },
};
