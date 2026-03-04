#!/bin/bash
# Auto-generated iptables rules from allowed_ips.conf
# Run as root: sudo bash iptables_setup.sh
# Re-run after editing allowed_ips.conf to update rules.

set -euo pipefail

PORT=5000
CONF="$(dirname "$0")/allowed_ips.conf"

if [[ $EUID -ne 0 ]]; then
  echo "Error: this script must be run as root (sudo)." >&2
  exit 1
fi

echo "Flushing existing rules for port ${PORT}..."
# Remove any existing rules for the port (avoid duplicates on re-run)
iptables-save | grep -v "dport ${PORT}" | iptables-restore 2>/dev/null || true

echo "Setting default DROP for port ${PORT}..."
iptables -A INPUT -p tcp --dport "${PORT}" -j DROP

echo "Allowing localhost..."
iptables -I INPUT -p tcp --dport "${PORT}" -s 127.0.0.1 -j ACCEPT
ip6tables -I INPUT -p tcp --dport "${PORT}" -s ::1 -j ACCEPT 2>/dev/null || true

echo "Processing ${CONF}..."
while IFS= read -r line; do
  # Strip comments and whitespace
  line="${line%%#*}"
  line="${line//[[:space:]]/}"
  [[ -z "$line" ]] && continue

  if [[ "$line" == "127.0.0.1" || "$line" == "::1" ]]; then
    continue  # Already handled
  fi

  echo "  Allowing: ${line}"
  if [[ "$line" == *:* ]]; then
    # IPv6
    ip6tables -I INPUT -p tcp --dport "${PORT}" -s "${line}" -j ACCEPT 2>/dev/null \
      || echo "    Warning: ip6tables failed for ${line}"
  else
    # IPv4
    iptables -I INPUT -p tcp --dport "${PORT}" -s "${line}" -j ACCEPT \
      || echo "    Warning: iptables failed for ${line}"
  fi
done < "${CONF}"

echo "Done. Current rules for port ${PORT}:"
iptables -L INPUT -n --line-numbers | grep "${PORT}" || true
