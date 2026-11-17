#!/usr/bin/env python3
"""Turn a clean Electrum 4.8.4 checkout into 'Electrum ASKus'. Usage: apply_electrum_askus.py <electrum-src-dir>"""
import sys, pathlib, json
src = pathlib.Path(sys.argv[1])
def sub(path, old, new, count=1):
    p = src / path; t = p.read_text()
    if old not in t: sys.exit(f"pattern not found in {path}: {old[:70]!r}")
    p.write_text(t.replace(old, new, count))

C = "electrum/constants.py"
sub(C, 'WIF_PREFIX = 0x80\n    ADDRTYPE_P2PKH = 0\n    ADDRTYPE_P2SH = 5\n    SEGWIT_HRP = "bc"',
       'WIF_PREFIX = 0x97      # ASKus Coin\n    ADDRTYPE_P2PKH = 23    # "A..."\n    ADDRTYPE_P2SH = 63     # "S..."\n    SEGWIT_HRP = "ask"     # "ask1..."')
sub(C, 'GENESIS = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"\n    DEFAULT_PORTS = {\'t\': \'50001\', \'s\': \'50002\'}\n    BLOCK_HEIGHT_FIRST_LIGHTNING_CHANNELS = 497000',
       'GENESIS = "00000cf3aea2ad2fa095d69e993a2c27b543f8ffbd0e01f94a942813ba10e8c4"\n    DEFAULT_PORTS = {\'t\': \'27001\', \'s\': \'27002\'}\n    BLOCK_HEIGHT_FIRST_LIGHTNING_CHANNELS = 0')
sub(C, "LN_DNS_SEEDS = [\n        'nodes.lightning.directory.',\n        'lseed.bitcoinstats.com.',\n        'lseed.darosior.ninja',\n    ]",
       "LN_DNS_SEEDS = []  # no Lightning network for ASKus Coin")
sub(C, 'GIT_REPO_URL = "https://github.com/spesmilo/electrum"', 'GIT_REPO_URL = "https://github.com/nemoralen/askus-os"')

# Chain data: no public servers, no checkpoints, no Lightning nodes (private network)
chain = src / "electrum/chains/mainnet"
(chain / "servers.json").write_text("{}\n")
(chain / "checkpoints.json").write_text("[]\n")
(chain / "fallback_lnnodes.json").write_text("{}\n")

# Proof-of-work limit = ASKus powLimit (compact 0x1e0ffff0)
sub("electrum/blockchain.py",
    "MAX_TARGET = 0x00000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffff  # compact: 0x1d00ffff",
    "MAX_TARGET = 0x00000ffff0000000000000000000000000000000000000000000000000000000  # ASKus compact: 0x1e0ffff0")

# Units and data directory
U = "electrum/util.py"
sub(U, "base_units = {'BTC':8, 'mBTC':5, 'bits':2, 'sat':0}", "base_units = {'ASK':8, 'mASK':5, 'bits':2, 'sat':0}")
sub(U, "base_units_list = ['BTC', 'mBTC', 'bits', 'sat']", "base_units_list = ['ASK', 'mASK', 'bits', 'sat']")
sub(U, 'os.path.join(os.environ["HOME"], ".electrum")', 'os.path.join(os.environ["HOME"], ".electrum-askus")')
print("Electrum ASKus patch applied")
# Privacy defaults: talk only to your own trusted server, never auto-pick random servers
S = "electrum/simple_config.py"
sub(S, "'auto_connect', default=True, type_=bool,", "'auto_connect', default=False, type_=bool,")
sub(S, "'oneserver', default=False, type_=bool,", "'oneserver', default=True, type_=bool,")
print("Electrum ASKus privacy defaults applied")
# Small network has no fee history yet: default to a fixed fee rate (2 sat/vB) instead of "confirm in 2 blocks"
sub(S, "FEE_POLICY = ConfigVar('fee_policy.default', default='eta:2', type_=str)",
       "FEE_POLICY = ConfigVar('fee_policy.default', default='feerate:2000', type_=str)")
sub(S, "FEE_POLICY_SWAPS = ConfigVar('fee_policy.swaps', default='eta:2', type_=str)",
       "FEE_POLICY_SWAPS = ConfigVar('fee_policy.swaps', default='feerate:2000', type_=str)")
# Paper wallets: a bare WIF key is swept from legacy AND SegWit (ask1...) addresses
sub("electrum/wallet.py",
    "                await group.spawn(find_utxos_for_privkey('p2pk', privkey, compressed))\n",
    "                await group.spawn(find_utxos_for_privkey('p2pk', privkey, compressed))\n"
    "                if compressed and ':' not in sec:  # ASKus paper wallets use ask1... (p2wpkh)\n"
    "                    await group.spawn(find_utxos_for_privkey('p2wpkh', privkey, compressed))\n"
    "                    await group.spawn(find_utxos_for_privkey('p2wpkh-p2sh', privkey, compressed))\n")
print("Electrum ASKus fee + sweep fixes applied")
