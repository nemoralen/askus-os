#!/usr/bin/env python3
"""Add the ASKus Coin network to ElectrumX 2.0.1. Usage: apply_electrumx_askus.py <electrumx-src-dir>
Run the server with COIN=ASKusCoin NET=mainnet."""
import sys, pathlib
p = pathlib.Path(sys.argv[1]) / "src/electrumx/lib/coins.py"
t = p.read_text()
marker = "\nclass BitcoinTestnetMixin"
if "class ASKusCoin(" in t: sys.exit("already applied")
if marker not in t: sys.exit("marker not found")
CLS = '''

class ASKusCoin(Bitcoin):
    """ASKus Coin - private Bitcoin Core fork (21M cap, SHA-256, 10-min blocks)."""
    NAME = "ASKusCoin"
    SHORTNAME = "ASK"
    NET = "mainnet"
    P2PKH_VERBYTE = bytes.fromhex("17")      # 23 -> "A..."
    P2SH_VERBYTES = (bytes.fromhex("3f"),)   # 63 -> "S..."
    WIF_BYTE = bytes.fromhex("97")           # 151
    GENESIS_HASH = ('00000cf3aea2ad2fa095d69e993a2c27'
                    'b543f8ffbd0e01f94a942813ba10e8c4')
    RPC_PORT = 27443
    PEER_DEFAULT_PORTS = {'t': '27001', 's': '27002'}
    TX_COUNT = 1
    TX_COUNT_HEIGHT = 1
    TX_PER_BLOCK = 2
    PEERS = []                                 # private network: no public peer discovery
    BLACKLIST_URL = None
'''
i = t.index(marker)
p.write_text(t[:i] + CLS + t[i:])
print("ElectrumX ASKus coin added")
