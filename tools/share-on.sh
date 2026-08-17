#!/bin/sh
# Mac mini の Wi-Fi (en1) のインターネットを USB-LAN (en8) 経由で Razer に共有する。
# 既存 LAN が 192.168.2.0/24 なので、共有側は 10.42.0.0/24 にずらして衝突を回避する。
set -e
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
D=/Users/macmini/dev/Razer_mac/tools
B=$D/backup-netshare
mkdir -p "$B"

# --- backup (once) ---
for F in /etc/bootpd.plist /Library/Preferences/SystemConfiguration/com.apple.nat.plist; do
  N=$(basename "$F")
  [ -f "$B/$N" ] || { [ -f "$F" ] && cp -p "$F" "$B/$N" && echo "backed up $F"; }
done

# --- install configs ---
cp "$D/bootpd.plist" /etc/bootpd.plist
cp "$D/nat.plist"    /Library/Preferences/SystemConfiguration/com.apple.nat.plist
chown root:wheel /etc/bootpd.plist /Library/Preferences/SystemConfiguration/com.apple.nat.plist
chmod 644        /etc/bootpd.plist /Library/Preferences/SystemConfiguration/com.apple.nat.plist
echo "configs installed"

# --- static IP on the shared side (gateway the Razer will use) ---
ifconfig en8 inet 10.42.0.1 netmask 255.255.255.0 alias 2>/dev/null || true
sysctl -w net.inet.ip.forwarding=1 >/dev/null
echo "en8 = 10.42.0.1, ip forwarding on"

# --- start sharing ---
# macOS 26 renamed this service: com.apple.InternetSharing -> com.apple.NetworkSharing.
# bootpd is also disabled by default and must be explicitly enabled.
launchctl enable system/com.apple.NetworkSharing 2>/dev/null || true
launchctl kickstart -k system/com.apple.NetworkSharing 2>/dev/null || true

# bootpd cannot be started via launchctl: /System/Library/LaunchDaemons/bootps.plist
# has "Disabled" => true baked in AND uses inetdCompatibility (Wait=true), i.e. it is
# only started on-demand when a packet hits UDP/67 -- which never happens because
# nothing is listening.  Run it as our own always-on daemon instead.
cp "$D/bootpd-daemon.plist" /Library/LaunchDaemons/local.razer.bootpd.plist
chown root:wheel /Library/LaunchDaemons/local.razer.bootpd.plist
chmod 644        /Library/LaunchDaemons/local.razer.bootpd.plist
launchctl bootout system/local.razer.bootpd 2>/dev/null || true
launchctl bootstrap system /Library/LaunchDaemons/local.razer.bootpd.plist 2>/dev/null || true
sleep 3

# NAT: InternetSharing normally installs the pf anchor itself, but pf may be left
# disabled.  Enable pf and add an explicit nat rule as a fallback so 10.42.0.0/24
# is translated out via en1 regardless.
mkdir -p /etc/pf.anchors
printf 'nat on en1 from 10.42.0.0/24 to any -> (en1)\n' > /etc/pf.anchors/local.razer.share
chmod 644 /etc/pf.anchors/local.razer.share
pfctl -E 2>/dev/null || true
# pf enforces rule ORDER by category:
#   options -> normalization -> queueing -> translation -> filtering
# `nat-anchor` is translation, so it MUST come before `anchor "com.apple/*"`
# (filtering).  Appending to the end of pf.conf makes the WHOLE ruleset fail to
# parse ("Rules must be in order"), which silently leaves NAT unconfigured.
# So insert the nat-anchor right after the existing rdr-anchor line, and keep
# `load anchor` at the end (load is a directive, not an ordered rule).
cp -n /etc/pf.conf /etc/pf.conf.razer-orig 2>/dev/null || true
cp /etc/pf.conf.razer-orig /etc/pf.conf
/usr/bin/sed -i '' \
  's|^rdr-anchor "com.apple/\*"$|rdr-anchor "com.apple/*"\
nat-anchor "local.razer.share"|' /etc/pf.conf
printf 'load anchor "local.razer.share" from "/etc/pf.anchors/local.razer.share"\n' >> /etc/pf.conf

if pfctl -n -f /etc/pf.conf 2>&1 | grep -q "must be in order"; then
  echo "ERROR: pf.conf still out of order, reverting"
  cp /etc/pf.conf.razer-orig /etc/pf.conf
else
  pfctl -f /etc/pf.conf 2>/dev/null || true
  echo "pf.conf: nat-anchor inserted in correct position"
fi

echo "--- state ---"
sysctl net.inet.ip.forwarding
ifconfig en8 | grep "inet "
echo "pf: $(pfctl -s info 2>/dev/null | grep Status)"
echo "nat rules:"; pfctl -a local.razer.share -s nat 2>/dev/null | grep -v ALTQ || true
echo "listening on :67:"; lsof -nP -iUDP:67 2>/dev/null | tail -2 || true
ps aux | grep -E "bootpd|InternetSharing" | grep -v grep || true
