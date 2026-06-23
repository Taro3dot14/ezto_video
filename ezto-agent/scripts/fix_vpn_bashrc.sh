#!/usr/bin/env bash
# Fix vpn aliases in ~/.bashrc

BASHRC="$HOME/.bashrc"
sed -i "s|alias vpn_on='source \"~/vpn_on.sh\"'|alias vpn_on='source \"\$HOME/vpn_on.sh\"'|" "$BASHRC"
sed -i "s|alias vpn_off='source \"~/vpn_off.sh\"'|alias vpn_off='source \"\$HOME/vpn_off.sh\"'|" "$BASHRC"
sed -i "s|alias vpn_on='source \"\${_EZTO_VPN_DIR}/vpn_on.sh\"'|alias vpn_on='source \"\$HOME/vpn_on.sh\"'|" "$BASHRC"
sed -i "s|alias vpn_off='source \"\${_EZTO_VPN_DIR}/vpn_off.sh\"'|alias vpn_off='source \"\$HOME/vpn_off.sh\"'|" "$BASHRC"
grep -n 'vpn' "$BASHRC"
