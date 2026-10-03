#!/usr/bin/env bash
# Helply monitoring agent - Linux installer (systemd).
#
#   curl -fsSL https://YOUR-HELPLY/monitoring/agent/install.sh | sudo bash -s -- --url https://YOUR-HELPLY --token TOKEN
#   sudo bash install.sh --uninstall
#
# Installs /opt/helply-agent, a config file readable only by the agent user, and a hardened
# systemd service running as the unprivileged user "helply-agent". The agent only sends readings.
set -euo pipefail

URL=""
TOKEN=""
INTERVAL="10"
UNINSTALL=0
DIR=/opt/helply-agent
CONF=/etc/helply-agent.conf
UNIT=/etc/systemd/system/helply-agent.service
SERVICE_USER=helply-agent

while [ $# -gt 0 ]; do
  case "$1" in
    --url) URL="${2:-}"; shift 2 ;;
    --token) TOKEN="${2:-}"; shift 2 ;;
    --interval) INTERVAL="${2:-10}"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1;33m[helply]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[helply]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Please run as root (use sudo)."
command -v systemctl >/dev/null 2>&1 || die "systemd is required."

if [ "$UNINSTALL" -eq 1 ]; then
  systemctl disable --now helply-agent 2>/dev/null || true
  rm -f "$UNIT" "$CONF"
  rm -rf "$DIR"
  systemctl daemon-reload
  id "$SERVICE_USER" >/dev/null 2>&1 && userdel "$SERVICE_USER" 2>/dev/null || true
  say "Helply agent removed."
  exit 0
fi

URL="${URL%/}"
[ -n "$URL" ] || die "Missing --url (the address of your Helply, e.g. https://helply.example.com)."
case "$URL" in https://*|http://127.0.0.1*|http://localhost*) ;; *) die "--url must start with https://" ;; esac
if [ -z "$TOKEN" ] && [ -r /dev/tty ]; then
  printf 'Agent token: ' > /dev/tty; read -r TOKEN < /dev/tty
fi
[ -n "$TOKEN" ] || die "Missing --token (shown in Helply when you add the server)."
case "$INTERVAL" in ''|*[!0-9]*) INTERVAL=10 ;; esac

PY=$(command -v python3 || true)
[ -n "$PY" ] || die "python3 not found. Install it first (apt install python3 / dnf install python3)."
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || die "Python 3.8 or newer is required."

say "Installing to $DIR"
mkdir -p "$DIR"
curl -fsSL "$URL/monitoring/agent/helply_agent.py" -o "$DIR/helply_agent.py.new" || die "Could not download the agent from $URL."
head -1 "$DIR/helply_agent.py.new" | grep -q python || die "The download from $URL does not look like the agent."
mv "$DIR/helply_agent.py.new" "$DIR/helply_agent.py"

# psutil: the distribution package if available, else a private virtualenv (nothing installed system-wide by pip).
if "$PY" -c 'import psutil' 2>/dev/null; then
  AGENT_PY="$PY"
else
  say "Installing psutil"
  if command -v apt-get >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-psutil >/dev/null 2>&1 || true
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y -q python3-psutil >/dev/null 2>&1 || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y -q python3-psutil >/dev/null 2>&1 || true
  fi
  if "$PY" -c 'import psutil' 2>/dev/null; then
    AGENT_PY="$PY"
  else
    "$PY" -m venv "$DIR/venv" || die "Could not create a virtualenv (install python3-venv) or install python3-psutil."
    "$DIR/venv/bin/pip" install -q psutil || die "Could not install psutil."
    AGENT_PY="$DIR/venv/bin/python"
  fi
fi

id "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"

umask 077
cat > "$CONF" <<EOF
# Helply agent settings. Keep this file private: the token identifies this server.
HELPLY_URL=$URL
HELPLY_TOKEN=$TOKEN
HELPLY_INTERVAL=$INTERVAL
EOF
chown root:"$SERVICE_USER" "$CONF"
chmod 640 "$CONF"
chown -R root:root "$DIR"
chmod 755 "$DIR"; chmod 644 "$DIR/helply_agent.py"

cat > "$UNIT" <<EOF
[Unit]
Description=Helply monitoring agent (read-only reporter)
After=network-online.target
Wants=network-online.target

[Service]
User=$SERVICE_USER
Group=$SERVICE_USER
ExecStart=$AGENT_PY $DIR/helply_agent.py --config $CONF
Restart=always
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
MemoryMax=64M
CPUQuota=10%

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable helply-agent >/dev/null 2>&1
systemctl restart helply-agent
sleep 3
if systemctl is-active --quiet helply-agent; then
  say "Done. The agent is running - the server's card in Helply turns live within ~10 seconds."
  say "Logs: journalctl -u helply-agent -f"
else
  journalctl -u helply-agent -n 20 --no-pager || true
  die "The agent did not start - see the log above."
fi
