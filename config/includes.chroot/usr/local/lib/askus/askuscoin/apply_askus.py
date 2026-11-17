#!/usr/bin/env python3
"""Turn a clean Bitcoin Core v31.2 checkout into ASKus Coin. Usage: apply_askus.py <bitcoin-src-dir>"""
import re, sys, pathlib
src = pathlib.Path(sys.argv[1])
def sub(path, old, new, count=1):
    p = src / path; t = p.read_text()
    if old not in t: sys.exit(f"pattern not found in {path}: {old[:60]!r}")
    p.write_text(t.replace(old, new, count))

MAIN = r'''class CMainParams : public CChainParams {
public:
    CMainParams() {
        // ===== ASKus Coin main network =====
        m_chain_type = ChainType::MAIN;
        consensus.signet_blocks = false;
        consensus.signet_challenge.clear();
        consensus.nSubsidyHalvingInterval = 210000;      // same schedule as Bitcoin -> 21,000,000 ASK cap
        // All soft forks (P2SH, BIP34/65/66, CSV, SegWit, Taproot) enforced from the start
        consensus.BIP34Height = 1;
        consensus.BIP34Hash = uint256{};
        consensus.BIP65Height = 1;
        consensus.BIP66Height = 1;
        consensus.CSVHeight = 1;
        consensus.SegwitHeight = 0;
        consensus.MinBIP9WarningHeight = 0;
        // Starting difficulty a handful of home CPUs can mine; retargets every 2016 blocks like Bitcoin
        consensus.powLimit = uint256{"00000ffff0000000000000000000000000000000000000000000000000000000"};
        consensus.nPowTargetTimespan = 14 * 24 * 60 * 60; // two weeks
        consensus.nPowTargetSpacing = 10 * 60;            // 10-minute blocks
        consensus.fPowAllowMinDifficultyBlocks = false;
        consensus.enforce_BIP94 = true;                   // hardening: timewarp-attack fix from testnet4
        consensus.fPowNoRetargeting = false;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].bit = 28;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].nStartTime = Consensus::BIP9Deployment::NEVER_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].min_activation_height = 0;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].threshold = 1815;
        consensus.vDeployments[Consensus::DEPLOYMENT_TESTDUMMY].period = 2016;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].bit = 2;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nStartTime = Consensus::BIP9Deployment::ALWAYS_ACTIVE;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].nTimeout = Consensus::BIP9Deployment::NO_TIMEOUT;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].min_activation_height = 0;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].threshold = 1815;
        consensus.vDeployments[Consensus::DEPLOYMENT_TAPROOT].period = 2016;

        consensus.nMinimumChainWork = uint256{};
        consensus.defaultAssumeValid = uint256{};

        // Network magic "ASK" + 0xC0 - ASKus nodes ignore Bitcoin nodes and vice versa
        pchMessageStart[0] = 0x41;
        pchMessageStart[1] = 0x53;
        pchMessageStart[2] = 0x4b;
        pchMessageStart[3] = 0xc0;
        nDefaultPort = 27444;
        nPruneAfterHeight = 100000;
        m_assumed_blockchain_size = 1;
        m_assumed_chain_state_size = 1;

        genesis = CreateGenesisBlock("ASKus Coin 16/Nov/2026 Hollywood FL - private, secure, fixed 21M supply",
                                     CScript() << OP_RETURN, 1794844800, 67437, 0x1e0ffff0, 1, 50 * COIN);
        consensus.hashGenesisBlock = genesis.GetHash();
        assert(consensus.hashGenesisBlock == uint256{"00000cf3aea2ad2fa095d69e993a2c27b543f8ffbd0e01f94a942813ba10e8c4"});
        assert(genesis.hashMerkleRoot == uint256{"7d799fdb61b2f985722ed76e2ccfe2c143ece5bb2535968e82288c21e61ae773"});

        // Private network: no public DNS seeds. Peers are added with addnode= / connect=
        vSeeds.clear();
        vFixedSeeds.clear();

        base58Prefixes[PUBKEY_ADDRESS] = std::vector<unsigned char>(1,23);   // legacy addresses start with "A"
        base58Prefixes[SCRIPT_ADDRESS] = std::vector<unsigned char>(1,63);   // P2SH multisig starts with "S"
        base58Prefixes[SECRET_KEY] =     std::vector<unsigned char>(1,151);  // WIF private keys
        base58Prefixes[EXT_PUBLIC_KEY] = {0x04, 0x88, 0xB2, 0x1E};           // standard xpub (hardware-wallet friendly)
        base58Prefixes[EXT_SECRET_KEY] = {0x04, 0x88, 0xAD, 0xE4};

        bech32_hrp = "ask";                                                  // SegWit addresses start with "ask1"

        fDefaultConsistencyChecks = false;
        m_is_mockable_chain = false;

        m_assumeutxo_data = {};
        chainTxData = ChainTxData{
            .nTime    = 1794844800,
            .tx_count = 1,
            .dTxRate  = 0.001,
        };
        m_headers_sync_params = HeadersSyncParams{
            .commitment_period = 641,
            .redownload_buffer_size = 15218,
        };
    }
};
'''
p = src / "src/kernel/chainparams.cpp"; t = p.read_text()
start = t.index("class CMainParams : public CChainParams {")
end = t.index("\n};\n", t.index("m_headers_sync_params", start)) + 4
t = t[:start] + MAIN + t[end:]
p.write_text(t)

# RPC port for mainnet
sub("src/chainparamsbase.cpp", 'std::make_unique<CBaseChainParams>("", 8332)', 'std::make_unique<CBaseChainParams>("", 27443)')
# Separate config file / data dir / pid so it never touches a real Bitcoin install
sub("src/common/args.cpp", '"bitcoin.conf"', '"askuscoin.conf"')
sub("src/common/args.cpp", 'GetSpecialFolderPath(CSIDL_APPDATA) / "Bitcoin"', 'GetSpecialFolderPath(CSIDL_APPDATA) / "ASKusCoin"')
sub("src/common/args.cpp", 'GetSpecialFolderPath(CSIDL_LOCAL_APPDATA) / "Bitcoin"', 'GetSpecialFolderPath(CSIDL_LOCAL_APPDATA) / "ASKusCoin"')
sub("src/common/args.cpp", '"Library/Application Support/Bitcoin"', '"Library/Application Support/ASKusCoin"')
sub("src/common/args.cpp", 'pathRet / ".bitcoin"', 'pathRet / ".askuscoin"')
sub("src/init.cpp", '"bitcoind.pid"', '"askuscoind.pid"')
# Currency unit shown by the wallet / RPC help
cu = src / "src/policy/feerate.h"
print("ASKus Coin patch applied")
sub("src/policy/feerate.h", 'CURRENCY_UNIT = "BTC"', 'CURRENCY_UNIT = "ASK"')
sub("CMakeLists.txt", 'set(CLIENT_NAME "Bitcoin Core")', 'set(CLIENT_NAME "ASKus Coin")')
sub("CMakeLists.txt", 'set(COPYRIGHT_HOLDERS_FINAL "The ${CLIENT_NAME} developers")', 'set(COPYRIGHT_HOLDERS_FINAL "The Bitcoin Core and ASKus Coin developers")')
print("ASKus Coin branding applied")
