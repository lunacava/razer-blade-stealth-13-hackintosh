#!/bin/sh
# インターネット共有を止めて元の設定に戻す。
set -e
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
B=/Users/macmini/dev/Razer_mac/tools/backup-netshare
launchctl kill TERM system/com.apple.NetworkSharing 2>/dev/null || true
launchctl disable system/com.apple.NetworkSharing 2>/dev/null || true
launchctl bootout system/local.razer.bootpd 2>/dev/null || true
rm -f /Library/LaunchDaemons/local.razer.bootpd.plist
[ -f "$B/bootpd.plist" ] && cp -p "$B/bootpd.plist" /etc/bootpd.plist && echo "restored bootpd.plist"
[ -f "$B/com.apple.nat.plist" ] && cp -p "$B/com.apple.nat.plist" \
   /Library/Preferences/SystemConfiguration/com.apple.nat.plist && echo "restored nat.plist"
# remove our pf additions
if [ -f /etc/pf.conf.razer-orig ]; then
  cp /etc/pf.conf.razer-orig /etc/pf.conf && echo "restored /etc/pf.conf"
fi
rm -f /etc/pf.anchors/local.razer.share
pfctl -f /etc/pf.conf 2>/dev/null || true
ifconfig en8 inet 10.42.0.1 -alias 2>/dev/null || true
sysctl -w net.inet.ip.forwarding=0 >/dev/null
echo "sharing off, forwarding off"
