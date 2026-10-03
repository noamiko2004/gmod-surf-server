#!/usr/bin/env bash
# Sets up the web portal (portal/server.py): Caddy for HTTPS in front of it,
# a systemd service, and a small root helper the portal may call through sudo
# (restart the game server, run an update, read its log). Run as root; deploy.sh
# calls it when PORTAL_ENABLED=1, so every update keeps it current.
source "$(dirname "$0")/common.sh"
[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }

PORTAL_PORT=8090
# Non-interactive, or needrestart can stop at a hidden prompt in the web console
APT=(env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get -o DPkg::Lock::Timeout=600 -y)
PUBLIC_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}' || true)"
PUBLIC_IP="${PUBLIC_IP:-$(hostname -I | awk '{print $1}')}"
[[ "$PUBLIC_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Could not find this server's IPv4 address." >&2; exit 1; }

caddy_ok() {  # Caddy 2.10+ can get Let's Encrypt certificates for an IP address
  command -v caddy >/dev/null || return 1
  local v; v="$(caddy version 2>/dev/null | grep -o 'v2\.[0-9]*' | head -n 1 | cut -d. -f2 || true)"
  [[ -n "$v" && "$v" -ge 10 ]]
}

# Let's Encrypt checks ports 80/443 before it hands out a certificate
if command -v ufw >/dev/null; then
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
fi

if ! caddy_ok; then
  log "Installing Caddy (official repository)"
  "${APT[@]}" install curl gpg >/dev/null || true
  if curl -fsSL 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
     && curl -fsSL 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list; then
    chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
    "${APT[@]}" update >/dev/null || true
  fi
  "${APT[@]}" install caddy >/dev/null || log "Could not install Caddy"
fi

if [[ -n "${PORTAL_DOMAIN:-}" ]]; then
  SITE="$PORTAL_DOMAIN"
  TLS=""
  GLOBAL=""
elif caddy_ok; then
  SITE="$PUBLIC_IP"
  # Let's Encrypt only issues IP-address certificates with its 6-day profile;
  # Caddy renews them by itself. Browsers send no SNI for an IP, hence default_sni.
  TLS=$'\ttls {\n\t\tissuer acme {\n\t\t\tprofile shortlived\n\t\t}\n\t}'
  GLOBAL=$'\tdefault_sni '"$PUBLIC_IP"
else
  # Old Caddy: fall back to a free DNS name that points at this IP
  SITE="${PUBLIC_IP//./-}.sslip.io"
  TLS=""
  GLOBAL=""
fi
BASE_URL="https://$SITE"

if command -v caddy >/dev/null; then
  log "Configuring Caddy for $BASE_URL"
  mkdir -p /etc/caddy
  cat > /etc/caddy/Caddyfile <<CADDY
# Written by $REPO_DIR/scripts/portal.sh; changes here are overwritten.
{
$GLOBAL
}

$SITE {
$TLS
	encode gzip
	reverse_proxy 127.0.0.1:$PORTAL_PORT
}
CADDY
  caddy fmt --overwrite /etc/caddy/Caddyfile >/dev/null 2>&1 || true
  systemctl enable caddy >/dev/null 2>&1 || true
  systemctl reload caddy 2>/dev/null || systemctl restart caddy || log "Caddy did not start, see: journalctl -u caddy"
fi

log "Installing the portal service"
cat > /usr/local/sbin/surfline-ctl <<CTL
#!/usr/bin/env bash
# Root helper for the web portal (allowed through sudo). Fixed actions only.
set -euo pipefail
case "\${1:-}" in
  status)
    echo "active=\$(systemctl is-active $SERVICE_NAME || true)"
    echo "since=\$(systemctl show $SERVICE_NAME -p ActiveEnterTimestamp --value)"
    if systemctl is-active --quiet surfline-update; then echo update_running=yes; else echo update_running=no; fi
    ;;
  restart) systemctl restart $SERVICE_NAME && echo "Game server restarted" ;;
  update)
    if systemctl is-active --quiet surfline-update; then echo "An update is already running"; exit 0; fi
    systemctl reset-failed surfline-update 2>/dev/null || true
    systemd-run --unit=surfline-update --collect /bin/bash -c 'bash $REPO_DIR/scripts/update.sh >> $GMOD_HOME/update.log 2>&1'
    echo "Update started"
    ;;
  logs) journalctl -u $SERVICE_NAME -n 300 --no-pager ;;
  *) echo "usage: surfline-ctl status|restart|update|logs" >&2; exit 2 ;;
esac
CTL
chown root:root /usr/local/sbin/surfline-ctl
chmod 755 /usr/local/sbin/surfline-ctl

SUDOERS_TMP="$(mktemp)"
echo "$GMOD_USER ALL=(root) NOPASSWD: /usr/local/sbin/surfline-ctl" > "$SUDOERS_TMP"
if visudo -cf "$SUDOERS_TMP" >/dev/null; then
  install -m 440 -o root -g root "$SUDOERS_TMP" /etc/sudoers.d/surf-portal
else
  log "Could not add the sudo rule; the portal's restart and update buttons will not work"
fi
rm -f "$SUDOERS_TMP"

cat > /etc/systemd/system/surf-portal.service <<UNIT
[Unit]
Description=Surf server web portal
After=network-online.target
Wants=network-online.target

[Service]
User=$GMOD_USER
ExecStart=/usr/bin/python3 $REPO_DIR/portal/server.py --repo $REPO_DIR --listen 127.0.0.1:$PORTAL_PORT --base-url $BASE_URL --public-addr $PUBLIC_IP:$PORT
Restart=always
RestartSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable surf-portal >/dev/null 2>&1 || true
systemctl restart surf-portal

echo "$BASE_URL" > "$GMOD_HOME/portal_url.txt"
log "Portal: $BASE_URL"
