#!/bin/bash
#
# install.sh -- build and install brtd on the Razer, as a per-user LaunchAgent.
#
# Run this ON the Razer (it needs the local IOKit headers and it registers the
# agent in the user's GUI domain, which is the only domain where TCC can grant
# Input Monitoring).  Requires the Command Line Tools; no sudo, no SIP change.
#
# After the first run, grant the permission by hand -- macOS will not prompt a
# bare LaunchAgent binary reliably:
#
#   System Settings -> Privacy & Security -> Input Monitoring
#     enable "brtd", or press "+" then Cmd-Shift-G and type ~/brt
#
# Note that IOHIDManagerOpen() returns KERN_SUCCESS even while the permission
# is missing; macOS accepts the open and then silently drops every value.  The
# only reliable check is whether events actually arrive (see verify below).
#
# Uninstall:
#   launchctl bootout gui/$(id -u)/com.local.brtd
#   rm -f ~/Library/LaunchAgents/com.local.brtd.plist
#   rm -rf ~/brt
#   ...then remove the Input Monitoring entry in System Settings.
#
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/brt"
LABEL="com.local.brtd"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
U="$(id -u)"

mkdir -p "$DEST"
cp "$SRC_DIR/brtd.c" "$DEST/brtd.c"

echo "==> building"
clang -Wall -O2 -o "$DEST/brtd" "$DEST/brtd.c" \
      -framework IOKit -framework CoreFoundation

# Ad-hoc sign so the binary has a stable code identity for TCC to remember.
# Rebuilding changes the cdhash, which invalidates the grant -- re-enable the
# Input Monitoring toggle after any rebuild.
echo "==> signing (ad-hoc)"
codesign --force --sign - "$DEST/brtd"

echo "==> writing $PLIST"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOS
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$DEST/brtd</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>/tmp/brtd.out</string>
  <key>StandardErrorPath</key><string>/tmp/brtd.err</string>
</dict>
</plist>
EOS
plutil -lint "$PLIST"

echo "==> (re)loading agent"
launchctl bootout "gui/$U/$LABEL" 2>/dev/null || true
: > /tmp/brtd.out
: > /tmp/brtd.err
launchctl bootstrap "gui/$U" "$PLIST"
sleep 3
launchctl print "gui/$U/$LABEL" 2>/dev/null | grep -E '^[[:space:]]+(state|pid) ' || true
cat /tmp/brtd.out

cat <<'EOS'

==> verify
    Press the brightness keys, then:
        tail /tmp/brtd.out          # expect "brightness 1.0000 -> 0.9375"
        ~/brt/bklt.sh               # expect the value to track (0..65535)
    Nothing logged means Input Monitoring is still not granted.
EOS
