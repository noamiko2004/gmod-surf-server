#!/usr/bin/env bash
# Gives the website a name instead of the bare IP address. Run as root:
#   sudo bash /home/gmod/surfline/scripts/set-domain.sh surf.example.com
#   sudo bash /home/gmod/surfline/scripts/set-domain.sh off      (back to the IP)
# The name must already point at this server: an A record with this server's
# IPv4 address at your domain registrar or DNS host (on duckdns.org, the
# "current ip" field). It saves PORTAL_DOMAIN in config.env and applies it to
# the website, the loading screen and the in-game links.
source "$(dirname "$0")/common.sh"
[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }

PUBLIC_IP="$(public_ip)"
ARG="${1:-}"
if [[ -z "$ARG" ]]; then
  echo "Website now: $(cat "$GMOD_HOME/portal_url.txt" 2>/dev/null || echo "not set up")"
  echo "Usage: sudo bash $0 your.domain.com   (or: off)"
  echo "The name needs an A record pointing at $PUBLIC_IP first."
  exit 2
fi

if [[ "${ARG,,}" == off ]]; then
  NAME=""
else
  NAME="$(domain_name "$ARG")"
  [[ -n "$NAME" ]] || { echo "\"$ARG\" is not a valid domain name (example: surf.example.com)." >&2; exit 1; }
  if ! points_here "$NAME"; then
    echo "$NAME points at $(resolve "$NAME" || echo nothing), not at this server ($PUBLIC_IP)." >&2
    echo "Add an A record for $NAME with the value $PUBLIC_IP, wait a few minutes, then run this again." >&2
    exit 1
  fi
fi

if grep -q '^PORTAL_DOMAIN=' "$CONFIG_FILE"; then
  sed -i "s|^PORTAL_DOMAIN=.*|PORTAL_DOMAIN=\"$NAME\"|" "$CONFIG_FILE"
else
  printf '\n# Website name (scripts/set-domain.sh)\nPORTAL_DOMAIN="%s"\n' "$NAME" >> "$CONFIG_FILE"
fi
log "PORTAL_DOMAIN=\"$NAME\" saved in config.env"

# Applies it: Caddy and its certificate, the portal, server.cfg's loading screen
SKIP_MAPS=1 bash "$REPO_DIR/scripts/deploy.sh"

URL="$(cat "$GMOD_HOME/portal_url.txt" 2>/dev/null || true)"
echo
echo "Website: $URL"
if [[ -n "$NAME" && "$URL" != "https://$NAME" ]]; then
  echo "The name was saved but the site still uses $URL; see the lines above." >&2
  exit 1
fi
echo "The certificate can take a minute. The loading screen switches at the next map change."
