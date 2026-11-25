#!/bin/bash
# ASKus Coin HUB: an always-on server (Debian 13 / Ubuntu 24.04) that your friends' ASKus OS
# nodes and Electrum ASKus wallets connect to. It is reachable ONLY as a Tor .onion address:
# nothing is opened on your router and your server's IP is never published.
#   sudo ./setup-hub.sh          (run from a checkout of the askus-os repository)
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd); PATCHES="$HERE/../../config/includes.chroot/usr/local/lib/askus/askuscoin"
BITCOIN_COMMIT=241537a697561d1748909744069f1382aa15827f    # Bitcoin Core v31.2
ELECTRUMX_TAG=2.0.1
ELECTRUMX_COMMIT=39d477f31727ff95ce99694f6d8cb4a4cd7bd633   # ElectrumX 2.0.1
U=askuscoin; HOME_DIR=/var/lib/askuscoin

apt-get update
apt-get install -y --no-install-recommends git build-essential cmake pkg-config libboost-dev libevent-dev \
  libsqlite3-dev python3 python3-venv python3-dev python3-plyvel libleveldb-dev tor openssl ca-certificates
id $U >/dev/null 2>&1 || useradd --system --home-dir $HOME_DIR --create-home --shell /usr/sbin/nologin $U
SRC=$(mktemp -d)

# 1. node
git clone -q --depth 1 --branch v31.2 https://github.com/bitcoin/bitcoin "$SRC/core"
[ "$(git -C "$SRC/core" rev-parse HEAD)" = "$BITCOIN_COMMIT" ] || { echo "source is not the pinned commit"; exit 1; }
python3 -B "$PATCHES/apply_askus.py" "$SRC/core"
cmake -S "$SRC/core" -B "$SRC/core/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=OFF -DBUILD_BENCH=OFF -DBUILD_GUI=OFF -DENABLE_IPC=OFF -DWITH_ZMQ=OFF
cmake --build "$SRC/core/build" -j"$(nproc)"
install -m755 "$SRC/core/build/bin/bitcoind" /usr/local/bin/askuscoind
install -m755 "$SRC/core/build/bin/bitcoin-cli" /usr/local/bin/askuscoin-cli

# 2. ElectrumX (server for Electrum ASKus)
git clone -q --depth 1 --branch $ELECTRUMX_TAG https://github.com/spesmilo/electrumx "$SRC/electrumx"
[ "$(git -C "$SRC/electrumx" rev-parse HEAD)" = "$ELECTRUMX_COMMIT" ] || { echo "ElectrumX source is not the pinned commit"; exit 1; }
python3 -B "$HERE/apply_electrumx_askus.py" "$SRC/electrumx"
# every Python package is checked against its pinned SHA-256; LevelDB comes from python3-plyvel
python3 -m venv --system-site-packages /opt/electrumx-askus
/opt/electrumx-askus/bin/pip install -q --no-cache-dir --require-hashes -r "$HERE/requirements-electrumx.txt"
/opt/electrumx-askus/bin/pip install -q --no-cache-dir --no-deps --no-build-isolation "$SRC/electrumx"

# 3. config (random RPC password, never leaves this machine)
RPCPASS=$(openssl rand -hex 24)
install -d -o $U -g $U -m700 $HOME_DIR/node $HOME_DIR/electrumx
cat > $HOME_DIR/node/askuscoin.conf <<CONF
server=1
txindex=1
txospenderindex=1
rpcbind=127.0.0.1
rpcallowip=127.0.0.1
rpcuser=electrumx
rpcpassword=$RPCPASS
# incoming only via the Tor onion service below; outgoing only via Tor
listen=1
bind=127.0.0.1:27444
proxy=127.0.0.1:9050
onlynet=onion
listenonion=0
dnsseed=0
dns=0
fixedseeds=0
discover=0
fallbackfee=0.00002
CONF
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=askuscoin-hub" \
  -keyout $HOME_DIR/electrumx/key.pem -out $HOME_DIR/electrumx/cert.pem 2>/dev/null
cat > $HOME_DIR/electrumx/env <<CONF
COIN=ASKusCoin
NET=mainnet
DB_ENGINE=leveldb
DB_DIRECTORY=$HOME_DIR/electrumx/db
DAEMON_URL=http://electrumx:$RPCPASS@127.0.0.1:27443/
SERVICES=tcp://127.0.0.1:27001,ssl://127.0.0.1:27002,rpc://127.0.0.1:8000
SSL_CERTFILE=$HOME_DIR/electrumx/cert.pem
SSL_KEYFILE=$HOME_DIR/electrumx/key.pem
PEER_DISCOVERY=off
PEER_ANNOUNCE=
CONF
install -d -o $U -g $U $HOME_DIR/electrumx/db
chown -R $U:$U $HOME_DIR; chmod 600 $HOME_DIR/node/askuscoin.conf $HOME_DIR/electrumx/env $HOME_DIR/electrumx/key.pem

# 4. services
cat > /etc/systemd/system/askuscoind.service <<UNIT
[Unit]
Description=ASKus Coin hub node
After=network-online.target tor.service
[Service]
User=$U
ExecStart=/usr/local/bin/askuscoind -conf=$HOME_DIR/node/askuscoin.conf -datadir=$HOME_DIR/node
ExecStop=/usr/local/bin/askuscoin-cli -conf=$HOME_DIR/node/askuscoin.conf -datadir=$HOME_DIR/node stop
Restart=on-failure
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectHome=yes
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/electrumx-askus.service <<UNIT
[Unit]
Description=ElectrumX server for ASKus Coin
After=askuscoind.service
Requires=askuscoind.service
[Service]
User=$U
EnvironmentFile=$HOME_DIR/electrumx/env
ExecStart=/opt/electrumx-askus/bin/electrumx_server
Restart=on-failure
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectHome=yes
[Install]
WantedBy=multi-user.target
UNIT

# 5. Tor onion service: node (27444) + Electrum (27002 SSL, 27001 TCP)
grep -q askuscoin /etc/tor/torrc || cat >> /etc/tor/torrc <<TORRC

# ASKus Coin hub
HiddenServiceDir /var/lib/tor/askuscoin/
HiddenServicePort 27444 127.0.0.1:27444
HiddenServicePort 27001 127.0.0.1:27001
HiddenServicePort 27002 127.0.0.1:27002
TORRC
systemctl daemon-reload
systemctl restart tor
systemctl enable --now askuscoind electrumx-askus
for i in $(seq 30); do [ -f /var/lib/tor/askuscoin/hostname ] && break; sleep 1; done
rm -rf "$SRC"
ONION=$(cat /var/lib/tor/askuscoin/hostname)
cat <<DONE

ASKus Coin hub is running.
  Give your friends this hub address:   $ONION
  On ASKus OS:   ASKus Coin > "Add a friend's hub"   (or: askuscoin addpeer $ONION)
  In Electrum ASKus:  Tools > Network > Server:   $ONION:27001:t
     (the .onion address already encrypts and authenticates the connection)
DONE
