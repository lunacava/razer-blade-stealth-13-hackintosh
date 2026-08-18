#!/usr/bin/env python3
"""
Generate OC/config.plist for Razer Blade Stealth 13 (RZ09-02812E71, i7-8565U).

Every non-obvious value below is traceable to evidence gathered from the
live machine (see docs/hardware-findings.md) rather than copied from a guide
for a different model.
"""
import plistlib, base64, pathlib

B = lambda h: base64.b16decode(h.replace(" ", "").upper())
D = lambda h: plistlib.Data(B(h)) if hasattr(plistlib, "Data") else B(h)

# ---------------------------------------------------------------- kexts
# Order matters: Lilu first, then its plugins; VirtualSMC before its sensors;
# VoodooI2C before VoodooI2CHID.
KEXTS = [
    ("Lilu.kext",                   "Contents/MacOS/Lilu"),
    ("VirtualSMC.kext",             "Contents/MacOS/VirtualSMC"),
    ("SMCProcessor.kext",           "Contents/MacOS/SMCProcessor"),
    ("SMCBatteryManager.kext",      "Contents/MacOS/SMCBatteryManager"),
    # ECEnabler: this DSDT's BAT0._BIF/_BST read 16-bit EC fields
    # (BIF0..BIF8, BST0..BST3 are all width 16 in Field(ERAM)), plus
    # BADN=128 / ECVR=32 / ECCM=256.  macOS's AppleACPIEC only performs
    # 8-bit EC reads, so those reads return garbage and the battery
    # reports nothing.  ECEnabler splits wide reads at runtime, which
    # avoids having to patch the DSDT by hand.
    ("ECEnabler.kext",              "Contents/MacOS/ECEnabler"),
    ("WhateverGreen.kext",          "Contents/MacOS/WhateverGreen"),
    ("AppleALC.kext",               "Contents/MacOS/AppleALC"),
    ("NVMeFix.kext",                "Contents/MacOS/NVMeFix"),
    ("RestrictEvents.kext",         "Contents/MacOS/RestrictEvents"),
    ("AirportItlwm.kext",           "Contents/MacOS/AirportItlwm"),
    ("IntelBluetoothFirmware.kext", "Contents/MacOS/IntelBluetoothFirmware"),
    ("IntelBTPatcher.kext",         "Contents/MacOS/IntelBTPatcher"),
    ("BlueToolFixup.kext",          "Contents/MacOS/BlueToolFixup"),
    # USB port map.  This PCH xHCI (8086:9DED, \_SB.PCI0.XHC) declares 18 ports
    # but macOS only accepts 15, so the ports have to be declared explicitly
    # rather than relying on XhciPortLimit (which is a Catalina-era hack and is
    # left False below).  UTBMap.kext is codeless -- Info.plist only -- and
    # declares OSBundleLibraries on com.dhinakg.USBToolBox.kext, so
    # USBToolBox.kext MUST be injected first.
    #
    # The nine ports in the map come from the ACPI _UPC/_PLD data that
    # USBToolBox's usbdump reads on the Windows side (see docs/hardware-
    # findings.md 発見 16), NOT from guessing:
    #   HS01=1  SS01=13  UsbConnector 9   USB-C          (_PLD type_c, guessed 9)
    #   HS02=2  SS02=14  UsbConnector 3   USB-A #1
    #   HS03=3  SS03=15  UsbConnector 3   USB-A #2
    #   HS04=6           UsbConnector 255 camera         13D3:56D5
    #   HS05=8           UsbConnector 255 keyboard/Chroma 1532:0239
    #   HS06=10          UsbConnector 255 Bluetooth      8087:0AAA
    # Every other port on the controller reports user_connectable false with no
    # device ever seen, so it is deliberately absent -- with a map applied,
    # anything not listed is disabled, which is the point.
    #
    # NOT covered: the TB3 controller (8086:15DB, RP09/PXSX, 4 ports).  It has
    # no personality here because IOThunderboltFamily is blocked below; if that
    # Block is ever lifted, that controller needs its own map.
    ("USBToolBox.kext",             "Contents/MacOS/USBToolBox"),
    ("UTBMap.kext",                 ""),
    # VoodooI2C ships its dependencies inside Contents/PlugIns.  OpenCore does
    # NOT walk PlugIns -- it injects exactly the bundles listed here -- so each
    # plugin needs its own entry or VoodooI2C dies at boot with
    #   "Can't load kext com.alexandred.VoodooI2C - failed to resolve library
    #    dependencies" / "error 0xdc008016" and no trackpad/keyboard.
    # Order: the two libraries VoodooI2C declares in OSBundleLibraries
    # (com.alexandred.VoodooI2CServices, org.coolstar.VoodooGPIO) must precede
    # it; VoodooInput is required by VoodooI2CHID's multitouch path.
    ("VoodooI2C.kext/Contents/PlugIns/VoodooI2CServices.kext",
                                    "Contents/MacOS/VoodooI2CServices"),
    ("VoodooI2C.kext/Contents/PlugIns/VoodooGPIO.kext",
                                    "Contents/MacOS/VoodooGPIO"),
    ("VoodooI2C.kext/Contents/PlugIns/VoodooInput.kext",
                                    "Contents/MacOS/VoodooInput"),
    ("VoodooI2C.kext",              "Contents/MacOS/VoodooI2C"),
    ("VoodooI2CHID.kext",           "Contents/MacOS/VoodooI2CHID"),
    # itlwm: fallback for AirportItlwm, shipped DISABLED.
    # AirportItlwm links against IO80211Family's private API, so its binaries
    # are cut per-OS-version; the newest build is Sonoma 14.4 (v2.3.0, 2024-06)
    # while the recovery image Apple hands out for MacBookPro board IDs is now
    # 14.6.1.  If AirportItlwm refuses to load there, enable itlwm instead --
    # it bypasses IO80211Family entirely (LSMinimumSystemVersion 10.9) and
    # presents the card as Ethernet, driven from userspace by HeliPort.
    # Never enable both: they claim the same PCI device.
    ("itlwm.kext",                  "Contents/MacOS/itlwm"),
]

# Kexts that ship present-but-disabled, to be flipped on the machine if needed.
DISABLED_KEXTS = {"itlwm.kext"}

def kext(path, exe, minkern="", maxkern=""):
    return {
        "Arch": "x86_64", "BundlePath": path, "Comment": "",
        "Enabled": True, "ExecutablePath": exe,
        "MaxKernel": maxkern, "MinKernel": minkern,
        "PlistPath": "Contents/Info.plist",
    }

# ---------------------------------------------------------------- blocked kexts
# The TB3 controller (JHL6240 Alpine Ridge LP) is set to Disabled in BIOS but
# still enumerates on PCI with no power, so every register read comes back as
# 0xffffffff:
#   Thunderbolt 255 PCI - ... RT=0xffffffff NLRT=0xffffffff LWRT=0xffffffff
# AppleThunderboltNHI then tries to allocate DMA rings against that dead device
# and the box hard-resets (no panic screen, just back to the picker; the next
# boot logs "Previous shutdown cause: 5").  Reproduced twice, dying at the same
# two lines 40ms apart:
#   AppleThunderboltNHITransmitRingManager::allocateTransmitRing Flags: 0x1
#   AppleThunderboltNHIReceiveRingManager::allocateReceiveRing  Flags: 0x1
# Strategy Disable (not Exclude) per Configuration.pdf:1449 -- Exclude drops the
# plist entry entirely and is risky for something other kexts depend on.
# Revisit in phase 2 when re-testing Thunderbolt.
BLOCKED_KEXTS = [
    "com.apple.iokit.IOThunderboltFamily",
    "com.apple.driver.AppleThunderboltNHI",
]

block_list = [{
    "Arch": "Any",
    "Comment": f"stop {i} (TB3 JHL6240 resets during NHI ring alloc)",
    "Enabled": True, "Identifier": i,
    "MaxKernel": "", "MinKernel": "", "Strategy": "Disable",
} for i in BLOCKED_KEXTS]

kext_list = [kext(p, e) for p, e in KEXTS]
# BlueToolFixup replaces IntelBluetoothInjector from macOS 12 (kernel 21) up.
for k in kext_list:
    if k["BundlePath"] == "BlueToolFixup.kext":
        k["MinKernel"] = "21.0.0"
    if k["BundlePath"] in DISABLED_KEXTS:
        k["Enabled"] = False

# ---------------------------------------------------------------- ACPI
SSDTS = ["SSDT-XOSI.aml", "SSDT-PLUG.aml", "SSDT-PNLF.aml",
         "SSDT-USBX.aml", "SSDT-HDAS-CDEC.aml", "SSDT-DGPU-OFF.aml",
         # Both added after the boot stalled with "Previous shutdown cause: 5"
         # and no further output.  Dortania lists exactly that stall under
         # "Stuck on RTC..., PCI Configuration Begins, Previous Shutdown...,
         # HPET, HID: Legacy..." -> "Add EC SSDT" + fix the RTC.  Verified
         # against dumps/acpi/DSDT-ALASKA-A_M_I_-01072009.dsl:
         #   * no Device (EC) exists at all -- only H_EC (_STA 0) and EC0
         #     (_STA 0x0F), so AppleACPIEC has nothing to attach to.
         #   * RTC._STA needs STAS==1 and AWAC._STA needs STAS==0; STAS is
         #     declared once (line 1456) and never assigned, so it stays 0 =>
         #     legacy RTC disabled, AWAC (ACPI000E) enabled, which macOS
         #     cannot drive.
         # See the header comments in build/ACPI-src/SSDT-{EC,AWAC-DISABLE}.dsl
         # for the full derivation, including why EC0 is left enabled (battery)
         # and why these use _OSI rather than XOSI.
         "SSDT-EC.aml", "SSDT-AWAC-DISABLE.aml",
         # SSDT-PMC: added after the Sonoma installer froze twice at the same
         # point ("~18 minutes remaining") with pointer, keyboard (Caps Lock
         # LED dead) and display all dead at once -- i.e. the whole machine,
         # which is what an SMM hang looks like.  This is a 300-series PCH and
         # the official sample says it outright: "On certain implementations,
         # including APTIO V, PMC initialisation is required for NVRAM access.
         # Otherwise it will freeze in SMM mode."  This firmware's ACPI OEM is
         # ALASKA / A M I = APTIO, and it provides no Device (PMCR) / "APP9876"
         # at all -- only the generic PNP0C02 + _UID "PCHRESV" reservation
         # (Device (PRRE), DSDT line 15370) that Windows uses.  Dortania's
         # userspace-issues page prescribes SSDT-PMC for 300-series under
         # "Stuck at N minutes remaining", which is NVRAM-write related; the
         # installer writes NVRAM in its final phase.  The MMIO base was
         # verified by decoding PRRE._CRS by hand rather than trusting the
         # sample -- see the header of build/ACPI-src/SSDT-PMC.dsl.
         #
         # Deliberately NOT paired with NVRAM LegacyEnable/LegacyOverwrite
         # (the emulated-NVRAM path Dortania lists for non-300-series): native
         # NVRAM demonstrably works here -- the DEBUG log shows
         # "OC: Setting ROM ... - Success" / "Setting MLB ... - Success" with
         # WriteFlash=True -- so switching to nvram.plist would discard working
         # functionality to paper over a missing ACPI device.
         "SSDT-PMC.aml"]

acpi_add = [{"Comment": f"{s}", "Enabled": True, "Path": s} for s in SSDTS]

acpi_patch = [
    # --- 1. _OSI -> XOSI ------------------------------------------------
    # Required so \_SB.PCI0._INI raises OSYS above 0x07DC. Without it the
    # trackpad's _CRS returns SBFI (IRQ only, no I2C address) -> dead pad.
    # Count 0 = every occurrence (11 call sites in this DSDT).
    #
    # TableSignature MUST stay pinned to "DSDT".  Configuration.pdf: "Perform
    # binary patches in ACPI tables BEFORE table addition or removal", so an
    # unpinned rename also rewrites our own injected SSDTs.  SSDT-XOSI
    # deliberately returns Zero for _OSI("Darwin") (see its header), so
    # SSDT-EC's Device(EC)._STA and SSDT-AWAC-DISABLE's STAS=One would both
    # silently become no-ops -- the tables would load and do nothing, which
    # looks identical to "the fix didn't work".  Every OSYS gate this rename
    # exists for (\_SB.PCI0._INI, TPD0._INI, TPD0._CRS) lives in the DSDT, so
    # pinning costs nothing.
    {
        "Base": "", "BaseSkip": 0, "Comment": "_OSI to XOSI (trackpad + OSYS gating)",
        "Count": 0, "Enabled": True, "Find": D("5f4f5349"),
        "Limit": 0, "Mask": D(""), "OemTableId": D(""),
        "Replace": D("584f5349"), "ReplaceMask": D(""),
        "Skip": 0, "TableLength": 0, "TableSignature": D("44534454"),
    },
    # --- 2. LID-always-open inside RWAK --------------------------------
    # Store(Zero,LIDS) -> Store(One,LIDS), ONLY in \RWAK (the S3 resume
    # path). Verified unique at DSDT offset 0x16796: the trailing
    # If(IGDS) PkgLength is 0x3A here vs 0x2C at the two EC0 sites, so this
    # 21-byte pattern matches exactly once. Same length -> safe in-place.
    # Purpose: stop macOS seeing a closed lid on wake and re-sleeping.
    {
        "Base": "", "BaseSkip": 0,
        "Comment": "RWAK: LIDS always open on resume (unique @0x16796)",
        "Count": 1, "Enabled": True,
        "Find":    D("70004c494453a0086070014c494453a03a49474453"),
        "Limit": 0, "Mask": D(""), "OemTableId": D(""),
        "Replace": D("70014c494453a0086070014c494453a03a49474453"),
        "ReplaceMask": D(""), "Skip": 0, "TableLength": 0,
        "TableSignature": D("44534454"),   # DSDT only
    },
]

# ---------------------------------------------------------------- DeviceProperties
# iGPU: Intel UHD 620 on Whiskey Lake, PCI 8086:3EA0 @ 00:02.0 -> PciRoot(0x0)/Pci(0x2,0x0)
# This CPU is an i7-8565U -- Whiskey Lake-U, UHD 620, real PCI id 8086:3EA0.
# Apple ships no driver entry for 3EA0, so device-id must be spoofed.
#
# CHANGED 2026-08-18 from 0x3E9B0000 / device-id 0x3E9B to 0x3EA50009 / 0x3EA5.
#
# The old pair was carried here with a comment claiming 0x3E9B0000 was "the
# Dortania-recommended laptop framebuffer for Coffee Lake Plus / Whiskey Lake".
# That was wrong on both halves.  WhateverGreen's own FAQ.IntelHD is explicit:
#   Recommended framebuffers:
#     Desktop:  0x3EA50000 (default), 0x3E9B0007 (recommended)
#     Laptop:   0x3EA50009 (default)
#   "For UHD620 (Whiskey Lake) fake device-id A53E0000 for IGPU."
# 0x3E9B0000 does appear in the CFL/CML list as "mobile" with 3 connectors, so
# it is not a desktop layout -- but it is not the laptop default either, and
# 0x3E9B is not the documented fake for Whiskey Lake.  We were running the
# wrong half of two different recipes.
#
# WHY THIS MATTERS -- IT IS THE eDP LINK-TRAINING FAILURE.
#
# With 0x3E9B0000 the panel lights at boot and never comes back once the
# display is powered off.  Full trace of one failed wake (07:17:02, log show on
# AppleIntelCFLGraphicsFramebuffer) shows the driver doing everything right and
# the sink refusing to lock:
#   Panel power ON time was 228 ms          <- panel really is powered
#   PP_STATUS=0x80000008
#   SetupOptimalLaneCount: Optimal - LaneCount=2, BitRate=0xa
#   SetupDPTimings: pixelClock=138500000, linkSymbolClock=270000000,
#                   colorDepth=24, noLanes=2
#   EnableClocks: PLL successfully enabled
#   ConfigureBufferTranslation: BT: Using eDP eye
#   [Link_Training] Config : ASREnabled 1 noLanes 2 bitRate a enhanced framing 1
#   ... Clock Recovery Initated, Retry Count = 0    HW strength setting=0
#       laneStatus=0   (request01=0,    ...) Voltage=0, Pre-Emphasis=0
#   ... Clock Recovery Initated, Retry Count = 1    HW strength setting=0
#       laneStatus=0   (request01=0x11, ...) Voltage=1, Pre-Emphasis=0
#   ...                                            HW strength setting=0x4
#       laneStatus=0   (request01=0x22, ...) Voltage=2, Pre-Emphasis=0
#   ...                                            HW strength setting=0x87
#       laneStatus=0   (request01=0x33, ...) Voltage=3, Pre-Emphasis=0
#   ... four more retries, all laneStatus=0 at Voltage=3
#   [WARNING] Failed Phase 1 of Link Training
#   [ERROR  ] Link training failed - notifying AGDC to take display offline
#   [ERROR  ] [Modeset] Not successful. Disabling display
#
# Every AUX transaction in that sequence returned Status:0, and the sink filled
# in ADJUST_REQUEST (0x11 -> 0x22 -> 0x33) asking for more swing, so the panel
# is powered, addressable and responding.  It simply never asserts CR_DONE:
# laneStatus stays 0 through all four voltage levels and every retry.  That is
# the signature of the wrong electrical/connector configuration for this port
# -- ConfigureBufferTranslation picks its "eDP eye" values from the framebuffer
# layout, so the layout choice is exactly what is being tested here -- not a
# bandwidth problem (0x14 and 0x0A both fail identically) and not a backlight
# problem (the panel shows nothing at all under a flashlight).
#
# It is consistent that boot works and only re-enable fails: the firmware
# trains the link before macOS starts, so the first screen is inherited and
# never re-trained.
#
# THIS LAYOUT DOES NOT FIX THE BLACK-SCREEN-AFTER-DISPLAY-SLEEP BUG.
# KEEP IT ANYWAY (it fixes a different, real problem -- see below), BUT READ
# THE WHOLE NOTE BEFORE TRUSTING ANY CLAIM IN IT.
#
# THE ACTUAL ROOT CAUSE, measured 2026-08-18 14:00-14:10:
#
#     [IGFB][ERROR  ] hwSetPanelPower : Timeout powering ON the panel!!
#
# Every single panel power-on since boot timed out -- 7 out of 7.  The shape is
# identical every time:
#     hwSetPanelPower (state=0)          <- panel off
#     hwSetPanelPowerConfig (value=1)
#       ... 4-6 s later
#     hwSetPanelPower (state=2)          <- request power ON
#       ... 2.20 s later
#     [ERROR] hwSetPanelPower : Timeout powering ON the panel!!
#     hwSetPanelPower (state=2)          <- re-requested, then carries on anyway
# Time-to-timeout across the 7: 2.170 / 2.248 / 2.255 / 2.250 / 2.253 / 2.184 /
# 2.197 s.  A fixed ~2.2 s timeout is expiring; this is not jittery hardware.
# The driver writes the request to the panel power sequencer (PP_CONTROL) and
# polls PP_STATUS for completion, which never arrives.
#
# THAT IS ALSO WHY ONLY THE BOOT SCREEN WORKS.  The boot-time log (08:18:55)
# contains only hwSetPanelPowerConfig -- there is no state=0 -> state=2
# transition at all, because firmware already powered the panel and macOS
# inherits it.  The broken path is never taken until something turns the panel
# off.
#
# So the operative rule for this machine is: THE PANEL NEVER COMES BACK ONCE
# IT IS POWERED OFF (7/7), AND NEVER DIES IF IT IS NOT.  Between 08:29:39 and
# 14:06 there were zero graphics events in the log, because nothing except my
# own test commands was turning the panel off.  The mitigation is therefore
# "do not let it power off", not "recover it" -- see MITIGATION below.
#
# THREE EARLIER CONCLUSIONS IN THIS FILE ARE HEREBY RETRACTED:
#
#  1. laneStatus=0x77 IS NOT EVIDENCE OF SUCCESS.  0x77 appeared at 08:29:39 and
#     the screen did NOT come back; the same cycle also logged the
#     hwSetPanelPower timeout, and no link training ran for the next 5.5 h.  A
#     trained link into an unpowered panel shows nothing.
#  2. THE "RETRY RECOVERS" PROCEDURE DOES NOT WORK.  It was built on reading
#     0x77 as success and has never restored the picture on hardware.  The
#     "picture came back on the third cycle" note was inferred from the log, not
#     observed.  There is currently NO over-SSH recovery; a dark panel needs a
#     power-button short press (clean shutdown) and a power-on.
#  3. THE DURATION DEPENDENCE IS NOT SUPPORTED.  TEST A's "success" below was
#     also a log-only judgement.  What is invariant is the panel power timeout,
#     not how long the panel was off.  (Retained for the record:
#         TEST A -- display off  15 s -> laneStatus=0x77   "SUCCESS" (unverified)
#         TEST B -- display off 180 s -> laneStatus=0x7    BLACK SCREEN
#     Both ran with `pmset -a sleep 0`, so S3 was not involved in either.  An
#     intermediate diagnosis blamed S3; that was a grep artifact -- the
#     predicate `eventMessage CONTAINS "Entering Sleep state"` matched
#     `log show`'s own command line being logged.  There was no S3.)
#
# A METHOD ERROR WORTH KEEPING: the ERROR-level graphics log was never read
# until the very end.  Filtering on "[IGFB][ERROR" surfaced the true cause in
# one line.  Hours were spent chasing LOG-level laneStatus values instead.
# Compounding it, `ssh host 'log show ...'` returns 0 lines silently, because
# zsh has a `log` builtin that shadows /usr/bin/log -- which is what produced
# the false "link training never ran this boot" reading.  Always use the
# absolute path.  See docs/hardware-findings.md finding 13.
#
# A separate driver-side defect, still real and still visible in one line:
#     [LINK_TRAINING] Failed to fast link train, err = 0x0
# It DETECTS that fast link training failed and then does not fall back to full
# link training -- it proceeds straight to EnablePipe with a partially trained
# link.  That is why "Failed Phase 1 of Link Training" never appears in this
# failure mode: full training is never attempted.
#
# The partial lock is per-lane and random:
#     laneStatus=0x77  both lanes locked          -> picture
#     laneStatus=0x07  lane0 only (0x01|0x02|0x04) -> black
#     laneStatus=0x70  lane1 only (0x10|0x20|0x40) -> black
# One lane at HBR carries 2.7 Gbps, and this panel needs 4.155 Gbps, so a
# one-lane link cannot display anything.  The lane bits are a correct decode --
# but see retraction 1 above: even 0x77 shows nothing while the panel power
# sequence has timed out, so this table cannot be used to judge success.
#
# WHY KEEP THIS LAYOUT ANYWAY.  Before it, the link could not be trained at all:
# 8 clock-recovery retries, drive strength escalated to voltage=3 / 0x87,
# laneStatus=0 every single time, ending in "Link training failed - notifying
# AGDC to take display offline" / "[Modeset] Not successful. Disabling display".
# Now the link reaches 0x77 at voltage=0 on the first attempt.  That is a real
# improvement to a real defect; it simply is not the defect that blanks the
# screen.  There is no reason to revert it.
#
# MITIGATION -- the only thing that actually works: never let the panel power
# off.  `caffeinate` is NOT adequate because it dies on reboot; `pmset -a`
# persists, so one invocation is enough:
#     sudo pmset -a displaysleep 0 sleep 0
# and two non-sudo paths that also power the panel off must be closed:
#     defaults write com.apple.dock wvous-tr-corner -int 1 && killall Dock
#     defaults -currentHost write com.apple.screensaver idleTime -int 0
# Applied on hardware 2026-08-18: wvous-tr-corner 10 -> 1, idleTime already 0.
# With all three in place the mitigation is complete and verified: after a
# reboot, `hwSetPanelPower` logs only hwSetPanelPowerConfig at 14:20:36 -- no
# state=0 -> state=2 transition exists, so the broken path is never entered,
# and there are zero timeouts and zero laneStatus lines for the whole boot.
#
# LID CLOSE IS SAFE, contrary to what this note previously claimed.  Measured
# 2026-08-18: lid closed 14:26:55, opened 14:27:17 (ioreg AppleClamshellState
# No -> Yes -> No, so the sensor does fire), and across that window there were
# zero hwSetPanelPower transitions, zero timeouts, zero laneStatus lines and no
# "Entering Sleep state"; afterwards IODisplayWrangler was still
# CurrentPowerState=4 with bklt=65535, and the user confirmed the picture never
# went away.  Lid close is simply not wired to a panel power-down on this
# machine, which is consistent with AppleClamshellCausesSleep = No.  Caveat:
# the lid was closed for 22 s; a long close is untested, but with
# displaysleep 0 there is no idle timer left to fire.
#
# WHERE THE REAL FIX WOULD HAVE TO LIVE, and why WhateverGreen cannot reach it.
# The failing cycle logs "Using the default EDP panel timings" and "Override
# power up delays to optimize" just before the timeout: the driver uses
# platform-default eDP timings and then shortens the power-up delay.  Intel's
# panel power sequencer clocks T1..T12 out of PP_ON_DELAYS / PP_OFF_DELAYS /
# PP_DIVISOR, and PP_DIVISOR is a divide-down of the reference clock; if that
# assumption is wrong for this board the sequence cannot complete inside 2.2 s.
# Searched for a knob and there is none:
#   * framebuffer-featurecontrol-maximumselfrefreshlevel is UNUSABLE here.  In
#     WhateverGreen/kern_igfx.hpp that field lives in
#     FramebufferWestmerePatchFlagBits -- first-generation (Westmere/Arrandale)
#     only.  The whole framebuffer-featurecontrol-* / framebuffer-fbccontrol-*
#     family is Westmere-only, so there is no PSR or FBC knob for CFL at all.
#   * enable-backlight-registers-alternative-fix (-igfxblt) IS ALREADY APPLIED
#     (see boot-args below).  The FAQ's "3-minute black screen issue on KBL/CFL"
#     section matches this machine's conditions exactly -- CFL framebuffer
#     driver, macOS >= 13.4 so the older -igfxblr is dead, WEG 1.7.0,
#     SSDT-PNLF.aml injected -- and it still does not fix this.  -igfxblt
#     rewrites the PWM side (BLC_PWM_*); the timeout is on the panel power side
#     (PP_CONTROL / PP_STATUS).  Different registers.
#   * enable-dbuf-early-optimizer (-igfxdbeo) is ICL-only, and this machine logs
#     zero "Pipe Underrun" / "DBuf" messages, so the symptom does not match.
#
# The measurement that produced the original (short-cycle) success reads:
#     [Modeset] FB0: Complete modeset
#     [Modeset] Lighting up eDP
#     IG:: EnableClocks:12937 PLL successfully enabled
#     [LINK_TRAINING] Running fast link training
#     [LINK_TRAINING] noLanes=2, ASR=1, downspread=0 BitRate = 10
#     [LINK_TRAINING] voltage=0, preEmphasis=0
#     [LINK_TRAINING] laneMask=0xff, laneStatus=0x77
# Every difference matters:
#   * "fast link training", not "regular Link Training" -- the driver now
#     trusts the cached link parameters instead of renegotiating from scratch,
#     which is the correct eDP path.
#   * laneStatus=0x77, not 0.  0x77 is CR_DONE|CHANNEL_EQ_DONE|SYMBOL_LOCKED
#     set for lane0 (0x01|0x02|0x04) and lane1 (0x10|0x20|0x40) -- a fully
#     locked 2-lane link.
#   * voltage=0, preEmphasis=0 on the FIRST attempt, no retries.  Previously
#     the driver escalated to voltage=3 / HW strength 0x87 across 8 attempts
#     and still got laneStatus=0.  Succeeding at the lowest drive strength
#     means the eDP eye parameters from this layout are the right ones, not
#     merely tolerable.
#   * "Failed Phase 1 of Link Training", "Link training failed - notifying
#     AGDC to take display offline" and "[Modeset] Not successful. Disabling
#     display" are all absent -- zero occurrences for that whole boot.  Their
#     absence proves very little: the failure mode above produces none of them
#     either, because it fails in fast link training and never reaches full
#     training -- and the panel-power timeout produces none of them at all.
#     Read the ERROR-level log ("[IGFB][ERROR"), not the absence of strings.
#   * BitRate = 10 is decimal for the injected 0x0A, so the DPCD property below
#     is being honoured at the same time.
# Acceleration survived the switch: Device ID 0x3ea5, VRAM 1536 MB, Metal 3,
# 3 framebuffers enumerated, display Online / Main Display Yes, no new panics.
#
# Still untried: the other two 3-connector mobile layouts 0x3E920009 /
# 0x3E9B0009, on the chance their platform data carries different panel power
# delays.  That is a long shot -- the likely home of the fix is the VBT, which
# WhateverGreen's Intel knobs do not reach.  What is actually deployed is the
# workaround: never power the panel off.  See docs/hardware-findings.md.
igpu = {
    "AAPL,ig-platform-id":      D("0900A53E"),   # 0x3EA50009, laptop default
    "device-id":                D("A53E0000"),   # 0x3EA5, WHL fake per FAQ
    "framebuffer-patch-enable": D("01000000"),
    # The framebuffer wants 57 MB stolen (58 MB total) but this
    # BIOS pre-allocates only 32 MB DVMT and exposes no setting to raise it
    # (verified: registry HardwareInformation.MemorySize, and no DVMT item in
    # BIOS 1.01).  WhateverGreen's manual is explicit that without the
    # stolenmem/fbmem semantic patches this combination panics.
    #   stolenmem 0x01300000 = 19 MB, fbmem 0x00900000 = 9 MB
    # These are the exact values Dortania specifies for the DVMT-32MB case,
    # so no BIOS mod is needed.  (The Reddit report for this same laptop
    # instead flashed a modded 1.06 BIOS for 64 MB DVMT -- we deliberately
    # avoid flashing, since BIOS 3.02 is known to brick this model.)
    "framebuffer-stolenmem":    D("00003001"),
    "framebuffer-fbmem":        D("00009000"),
    # No connector-type patch.  0x3EA50009 is a 3-connector mobile layout
    # ([0] internal panel + [1] DP + [2] DP), which matches this machine
    # exactly -- internal eDP panel plus USB-C and Thunderbolt 3, no HDMI --
    # so forcing con1/con2 to DP would be a no-op and is omitted rather than
    # carried as dead config.  Re-checked after the switch, 2026-08-18:
    # ioreg -c AppleIntelFramebuffer still counts 3, so the new layout
    # enumerates the same number of connectors as the old one.
    #
    # DPCD maximum-link-rate fix.  Without this, enabling acceleration panics
    # the machine the instant WindowServer programs the internal panel:
    #
    #   panic(cpu 6 caller ...): Kernel trap at ..., type 0=divide error
    #   ... RBX: 0x0, RDX: 0x0 ...
    #   Panicked task ...: pid 149: WindowServer
    #   com.apple.driver.AppleIntelCFLGraphicsFramebuffer :
    #     AppleIntelFramebufferController::SetupDPTimings(...) + 0x19b
    #     <- AppleIntelFramebufferController::SetupClocks(..., CRTCParams*)
    #
    # (Reproduced identically twice: Kernel-2026-08-18-005635.panic and
    # Kernel-2026-08-18-011253.panic.  Roughly 30 s after EXITBS, which is why
    # it looked like a "reboot loop" rather than a graphics fault -- and why
    # debug=0x100 did not hold a panic screen the user could read.)
    #
    # RBX and RDX are both zero at the trap, so the rate that SetupDPTimings
    # divides by arrived as zero: the DPCD read for this panel did not yield a
    # usable maximum link rate on the path that feeds it.  WhateverGreen hooks
    # AppleIntelFramebufferController::GetDPCDInfo -- the call that feeds that
    # divisor -- and substitutes a valid rate.  Verified against the shipped
    # binary rather than from documentation: WhateverGreen 1.7.0's __TEXT
    # contains "enable-dpcd-max-link-rate-fix", "dpcd-max-link-rate", the
    # mangled symbol ...GetDPCDInfo..., and the log string
    #   "MLR: [COMM] ProbeMaxLinkRate() Failed to read supported link rates
    #    from DPCD."
    #
    # THE VALUE MATTERS -- IT IS NOT A HARMLESS CEILING.
    #
    # This was first set to 0x14 (HBR2, 5.4 Gbps/lane) on the reasoning that the
    # rate is only an upper bound that link training negotiates down from.  That
    # reasoning was wrong, and it cost us a second bug: with 0x14 the machine
    # booted and ran fine, but the moment the display went to DPMS off it went
    # black and never came back -- not dark-but-visible under a flashlight (so
    # not a backlight fault), not recoverable with the brightness keys, and not
    # recoverable by closing and reopening the lid.  The firmware brings the eDP
    # link up at the panel's real rate before macOS starts, so the first screen
    # is inherited and works; every subsequent re-enable retrains the link at
    # whatever this property says, and a rate the sink cannot do fails training
    # every time -- which is exactly why the lid trick never helped.
    #
    # The FAQ's own guidance is per-resolution, not "highest wins":
    #   "Typically use 0x14 for 4K display and 0x0A for 1080p display.  All
    #    possible values are 0x06 (RBR), 0x0A (HBR), 0x14 (HBR2), 0x1E (HBR3)."
    #
    # This panel is a Sharp LQ133M1JW41, 13.3" 1920x1080, decoded from the live
    # EDID (ioreg AppleBacklightDisplay -> IODisplayEDID, descriptor string
    # "LQ133M1JW41").  Sharp eDP panels are the family the FAQ singles out for
    # this very fix ("Dell Inspiron 7590 with Sharp display").  0x0A is provably
    # sufficient here, from that same EDID's detailed timing block:
    #   pixel clock  = 0x361A = 13850 -> 138.50 MHz
    #   payload      = 138.50 MHz * 24 bpp        = 3.324 Gbps
    #   with 8b/10b  = 3.324 / 0.8                = 4.155 Gbps needed
    #   2 lanes * 2.7 Gbps (HBR)                  = 5.400 Gbps available
    #   headroom                                  = 1.30x
    # and 0x0A is non-zero, so it cannot bring back the division-by-zero panic
    # that this property exists to prevent.
    #
    # Do NOT "upgrade" this to 0x14 or 0x1E.  Higher is not safer here.
    #
    # Careful about reading the DPCD dump as confirmation either way: WEG's fix
    # hooks the AUX read and GetDPCDInfo prints its dump afterwards, so
    #   [DPCD_Info] DPCD DUMP: Fb=0
    #    14 14 C2 41          <- 0x000 rev 1.4, 0x001 MAX_LINK_RATE, 0x002 lanes
    # shows the value we injected, not the panel's native capability.  The
    # panel's real maximum link rate has never been observed on this machine.
    #
    # If 0x0A still does not survive a display-sleep cycle, the next lever is to
    # remove this property entirely and keep only the enable flag: WEG 1.4.4+
    # probes a supported rate from the DPCD itself when no value is given, which
    # is the FAQ's preferred configuration.  It is deliberately not the first
    # thing tried, because a probe that returns something the driver rejects
    # panics, and the rescue USB is currently unplugged.
    #
    # CONFIRMED ON HARDWARE 2026-08-18 that the PAIR fixes the panic (this was
    # measured with 0x14; the panic fix comes from the divisor being non-zero,
    # which 0x0A satisfies equally).  With this pair added and -igfxblt kept,
    # the machine booted to the desktop and stayed up with no panic, where the
    # identical config without them panicked ~30 s after EXITBS twice in a row.
    # VRAM went 7 MB -> 1536 MB, Metal 3 came up, and all three framebuffers
    # (internal eDP + 2x DP) enumerated -- i.e. nothing was traded away for the
    # fix.  The kernel log shows the divisor arriving as a sane value:
    #   (AppleIntelCFLGraphicsFramebuffer) [DPCD_Info] FB0: Display port config
    #     ver is 1.4
    #   ... [DPCD_Info] FB0 Maximum link rate is 0x14   <- becomes 0x0A now
    #   ... [DPCD_Info] FB0: Maximum lanes is 2
    # The causal link for the panic fix is solid: -igfxblt alone panicked
    # reproducibly, -igfxblt plus these two keys does not.  Do not drop the pair.
    #
    # 0x0A CONFIRMED WORKING on hardware, 2026-08-18: no panic, and the link
    # trains at this rate on every display-sleep wake --
    #   [LINK_TRAINING] noLanes=2, ASR=1, downspread=0 BitRate = 10
    #   [LINK_TRAINING] laneMask=0xff, laneStatus=0x77
    # BitRate = 10 is decimal for 0x0A, and 0x77 is a fully locked 2-lane link,
    # so 2 lanes x HBR really does carry this panel's 138.50 MHz timing exactly
    # as the bandwidth arithmetic above predicted.
    #
    # BUT BE CLEAR ABOUT WHAT THIS DID AND DID NOT FIX.  Changing 0x14 -> 0x0A
    # did NOT fix the black-screen-after-display-sleep bug: with 0x0A and the
    # old 0x3E9B0000 framebuffer the panel still died on every DPMS off, with
    # laneStatus=0 through 8 clock-recovery retries.  The real cause was the
    # framebuffer layout (see the igpu block above).  0x0A is retained because
    # it is the FAQ's correct value for a 1080p panel, it is provably sufficient
    # here, and it is what the working link is actually running at -- not
    # because it was the fix.  The earlier note claiming otherwise was wrong.
    #
    # STILL OPEN: whether this pair is needed at all now that the layout is
    # correct.  The pair was introduced to stop a divide-by-zero panic under
    # -igfxblt, and that panic was diagnosed while the wrong layout was in
    # place, so it may have been a symptom of the same root cause.  Worth
    # testing by removing both keys -- separately from any other change, with
    # a revert script staged, because the failure mode is a boot panic.
    "enable-dpcd-max-link-rate-fix": D("01000000"),
    "dpcd-max-link-rate":            D("0A000000"),
}

dev_props = {
    "Add": {
        "PciRoot(0x0)/Pci(0x2,0x0)": igpu,
        # Tell macOS the NVMe drive is internal, not removable.
        "PciRoot(0x0)/Pci(0x1d,0x4)/Pci(0x0,0x0)": {"built-in": D("00")},
    },
    "Delete": {},
}

# ---------------------------------------------------------------- SMBIOS
# MacBookPro15,2 = MacBook Pro 13-inch 2018, Four Thunderbolt 3 Ports.
# Chosen because (a) it is the closest real Apple machine to this hardware
# (quad-core U-series + Iris/UHD + TB3) and (b) an owner of this exact Razer
# model reported sleep works ONLY with 15,2 (15,4 and 16,3 failed).
#
# The serial / MLB / UUID / ROM are DELIBERATELY NOT IN THIS FILE.  They are
# per-machine identities that macOS sends to Apple, so publishing a working set
# invites collisions: if two machines present the same serial, Apple can flag
# both and iMessage / FaceTime / App Store sign-in break on each of them.
#
# Generate your own with GenSMBIOS (acidanthera) for MacBookPro15,2 and put
# them in smbios.local.py next to this script:
#
#     SystemSerialNumber = "..."      # from GenSMBIOS
#     MLB                = "..."      # from GenSMBIOS
#     SystemUUID         = "..."      # any random UUID, e.g. uuidgen
#     ROM                = "..."      # 12 hex chars, e.g. your real NIC MAC
#
# smbios.local.py is listed in .gitignore.  See smbios.local.py.example.
import importlib.util as _ilu

_smbios_path = pathlib.Path(__file__).with_name("smbios.local.py")
if not _smbios_path.exists():
    raise SystemExit(
        f"\nERROR: {_smbios_path} not found.\n\n"
        "This file holds your machine's unique SMBIOS identity, which is\n"
        "intentionally not committed (reusing someone else's serial breaks\n"
        "iMessage/FaceTime for both machines).  Copy the template and fill it\n"
        "in with values generated by GenSMBIOS for MacBookPro15,2:\n\n"
        f"    cp {_smbios_path.name}.example {_smbios_path.name}\n")

_spec = _ilu.spec_from_file_location("smbios_local", _smbios_path)
_s = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_s)

SMBIOS = {
    "SystemProductName": "MacBookPro15,2",
    "SystemSerialNumber": _s.SystemSerialNumber,
    "MLB": _s.MLB,
    "SystemUUID": _s.SystemUUID,
    "ROM": D(_s.ROM),
}

config = {
"ACPI": {
    "Add": acpi_add, "Delete": [], "Patch": acpi_patch,
    "Quirks": {
        "FadtEnableReset": False, "NormalizeHeaders": False,
        "RebaseRegions": False, "ResetHwSig": False,
        "ResetLogoStatus": True, "SyncTableIds": False,
    },
},
"Booter": {
    "MmioWhitelist": [], "Patch": [],
    "Quirks": {
        "AllowRelocationBlock": False,
        "AvoidRuntimeDefrag": True,
        "ClearTaskSwitchBit": False,
        "DevirtualiseMmio": True,       # needed with TB3 + large MMIO
        "DisableSingleUser": False,
        "DisableVariableWrite": False,
        "DiscardHibernateMap": False,
        "EnableSafeModeSlide": True,
        # REQUIRED on this machine. The DEBUG log prints "OCABC: MAT support is 0",
        # i.e. this firmware has no Memory Attributes Table, so the modern
        # RebuildAppleMemoryMap path cannot be used and Lilu's in-place code
        # patching page-faults (Error code 0x3 = write to a present read-only
        # page) right after VirtualSMC starts. Configuration.tex:1631-1633 says to
        # pick between the two based on that exact log line. Mutually exclusive
        # with RebuildAppleMemoryMap / SyncRuntimePermissions below, and depends
        # on OC_FIRMWARE_RUNTIME from OpenRuntime.efi.
        "EnableWriteUnprotector": True,
        # Re-signs/patches Apple EFI images so they load under OC 1.0.7.
        "FixupAppleEfiImages": True,
        "ForceBooterSignature": False,
        "ForceExitBootServices": False,
        "ProtectMemoryRegions": False,
        "ProtectSecureBoot": False,
        # REQUIRED on this machine. BIOS 1.01 rewrites UEFI service pointers
        # while loading drivers, which corrupts gBS->StartImage and makes every
        # boot attempt fail with EFI_ALREADY_STARTED (Bootstrap, picker, and OS
        # launch alike). See docs/install-runbook.md.
        "ProtectUefiServices": True,
        "ProvideCustomSlide": True,
        "ProvideMaxSlide": 0,
        # Both must stay false: they touch the same memory attribute table as
        # EnableWriteUnprotector above and are only valid on MAT-capable
        # firmware (this one reports "OCABC: MAT support is 0").
        "RebuildAppleMemoryMap": False,
        "ResizeAppleGpuBars": -1,
        "SetupVirtualMap": True,
        "SignalAppleOS": False,
        "SyncRuntimePermissions": False,
    },
},
"DeviceProperties": dev_props,
"Kernel": {
    "Add": kext_list, "Block": block_list, "Force": [], "Patch": [],
    "Emulate": {"Cpuid1Data": D(""), "Cpuid1Mask": D(""),
                "DummyPowerManagement": False, "MaxKernel": "", "MinKernel": ""},
    "Scheme": {"CustomKernel": False, "FuzzyMatch": True,
               "KernelArch": "x86_64", "KernelCache": "Auto"},
    "Quirks": {
        "AppleCpuPmCfgLock": False,
        "AppleXcpmCfgLock": True,       # Whiskey Lake: MSR 0xE2 is locked
        "AppleXcpmExtraMsrs": False,
        "AppleXcpmForceBoost": False,
        "CustomPciSerialDevice": False,
        "CustomSMBIOSGuid": False,
        "DisableIoMapper": True,        # DMAR present (VT-d) -> must disable
        "DisableIoMapperMapping": False,
        "DisableLinkeditJettison": True,
        "DisableRtcChecksum": False,
        "ExtendBTFeatureFlags": False,
        "ExternalDiskIcons": False,
        "ForceAquantiaEthernet": False,
        "ForceSecureBootScheme": False,
        "IncreasePciBarSize": False,
        "LapicKernelPanic": False,
        "LegacyCommpage": False,
        "PanicNoKextDump": True,
        "PowerTimeoutKernelPanic": True,
        "ProvideCurrentCpuInfo": False,
        "SetApfsTrimTimeout": -1,
        "ThirdPartyDrives": False,
        "XhciPortLimit": False,         # false on Catalina+; USBMap instead
    },
},
"Misc": {
    "BlessOverride": [],
    "Boot": {
        "ConsoleAttributes": 0, "HibernateMode": "None",
        "HibernateSkipsPicker": False, "HideAuxiliary": False,  # true hides com.apple.recovery.boot entirely
        "InstanceIdentifier": "", "LauncherOption": "Disabled",
        "LauncherPath": "Default", "PickerAttributes": 17,
        "PickerAudioAssist": False, "PickerMode": "External",
        "PickerVariant": "Acidanthera\\GoldenGate",
        "PollAppleHotKeys": True, "ShowPicker": True,
        "TakeoffDelay": 0, "Timeout": 8,
    },
    "Debug": {
        "AppleDebug": True, "ApplePanic": True, "DisableWatchDog": True,
        "DisplayDelay": 0, "DisplayLevel": 2147483650,
        "LogModules": "*", "SysReport": False, "Target": 67,
    },
    "Entries": [],
    "Security": {
        "AllowSetDefault": True, "ApECID": 0, "AuthRestart": False,
        "BlacklistAppleUpdate": True, "DmgLoading": "Signed",
        "EnablePassword": False, "ExposeSensitiveData": 6,
        "HaltLevel": 2147483648, "PasswordHash": D(""), "PasswordSalt": D(""),
        "ScanPolicy": 0, "SecureBootModel": "Disabled",
        "Vault": "Optional",
    },
    "Serial": {"Init": False, "Override": False},
    "Tools": [{
        "Arguments": "", "Auxiliary": True, "Comment": "OpenShell",
        "Enabled": True, "Flavour": "Auto", "FullNvramAccess": False,
        "Name": "OpenShell", "Path": "OpenShell.efi",
        "RealPath": False, "TextMode": False,
    }],
},
"NVRAM": {
    "Add": {
        "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102": {
            # Force the internal panel to be treated correctly and keep
            # brightness state across boots.
            "rtc-blacklist": D(""),
        },
        "4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38E36": {
            "DefaultBackgroundColor": D("00000000"),
            "UIScale": D("01"),
        },
        "7C436110-AB2A-4BBB-A880-FE41995C9F82": {
            # -v            verbose boot (remove once stable)
            # debug=0x100   keep panic info on screen
            # keepsyms=1    symbolicate panics
            # alcid=30      ALC298 layout, confirmed working on this exact
            #               laptop model (i7-8565U Blade Stealth 13 2019)
            # -igfxblt      Backlight Registers fix, ALTERNATIVE variant.
            #               On macOS 13.4+ Apple inlined WriteRegister32 in
            #               the CFL framebuffer driver, so the older -igfxblr
            #               silently stops working.  Sonoma is 14.x, so the
            #               alternative fix (-igfxblt, WEG >= 1.6.5) is the
            #               correct one here and -igfxblr must NOT be used.
            #               Guards against the 3-minute black screen on boot.
            # -btlfxboardid BlueToolFixup board-id patch.  Without it Bluetooth
            #               never initialises at all: bluetoothd picks its HCI
            #               transport from the SMBIOS board-id, and we present
            #               Mac-827FB448E656EC26 (MacBookPro15,2), a T2 machine
            #               whose Bluetooth hangs off UART behind the T2.  So it
            #               waits for a serial port that does not exist here and
            #               respawns every ~16 s forever:
            #                 FindTransportType -- UART Transport
            #                 HCI Transport is set to H4BC
            #                 UART open(/dev/cu.BLTH) port failed to appear
            #                   after 15 seconds (Operation timed out)
            #                 Bluetooth error - restarting { reason=1201,
            #                   context="Transport layer initialization failed" }
            #               This machine's Bluetooth is Intel 8087:0aaa on USB.
            #
            #               Why a boot-arg is REQUIRED on Sonoma specifically --
            #               from BlueToolFixup.cpp (BrcmPatchRAM, read at
            #               REL-272-2026-03-20, matching the shipped 2.7.2):
            #                 if (getKernelVersion() >= KernelVersion::Sonoma) {
            #                     shouldPatchBoardId =
            #                         checkKernelArgument("-btlfxboardid");
            #                 } else {
            #                     ... auto-detect via boardIdsWithUSBBluetooth
            #                 }
            #               i.e. up to Ventura the kext decided by itself, but on
            #               Sonoma+ the board-id patch is opt-in and does nothing
            #               unless this boot-arg is present.  That is why having
            #               BlueToolFixup.kext loaded was not enough.
            #
            #               What it does: patches the in-memory pages of
            #               /usr/sbin/bluetoothd and /usr/sbin/BlueTool, finding
            #               boardIdsWithUSBBluetooth[0] ("Mac-F60DEB81FF30ACF6",
            #               Mac Pro 6,1) and substituting our own board-id, so
            #               FindTransportType resolves to USB.  Both strings are
            #               20 bytes, so the substitution is size-compatible, and
            #               the search target was confirmed present in the
            #               shipped binaries (1x in bluetoothd, 2x in BlueTool).
            #
            #               CONFIRMED EFFECTIVE 2026-08-18 for transport selection
            #               specifically: after adding it the log flipped to
            #                 HCI Transport is set to USB
            #               and system_profiler reports "Transport: USB" instead
            #               of UART.  bluetoothd's USB backend then runs and
            #               correctly finds the controller:
            #                 [bm3_usb][GetProductAndVendorID] -- Found USB Device
            #                     idVendor = 0x8087  idProduct = 0x0AAA
            #                     deviceClass = 0xE0 (224)   <- Wireless Controller
            #               So the earlier worry -- that our board-id also being
            #               present in bluetoothd's own 43-entry table might make
            #               the UART entry win -- did not materialise.
            "boot-args": "-v debug=0x100 keepsyms=1 alcid=30 -igfxblt -btlfxboardid",
            "csr-active-config": D("00000000"),
            "prev-lang:kbd": D("656E2D55533A30"),   # en-US:0
            "run-efi-updater": "No",
            #
            # Bluetooth internal-controller variables.  Fixing the transport was
            # necessary but not sufficient: with transport = USB, bluetoothd
            # found the right device and then still failed --
            #   [bm3_usb][GetProductAndVendorID] -- Use internal Bluetooth USB
            #     Host Controller
            #   [bm3_usb][IOThreadFunc] -- Can't obtain vendorID and productID
            #     -- try again
            # i.e. it fails on the *internal controller* check, immediately after
            # deciding to treat this as the built-in controller.
            #
            # BrcmPatchRAM's README requires exactly these two, under this GUID,
            # for macOS 12+ with BlueToolFixup, and states they are "required for
            # at least Intel Bluetooth to work":
            #   bluetoothExternalDongleFailed   = 00
            #   bluetoothInternalControllerInfo = 14 zero bytes
            # BlueToolFixup's -btlfxnvramcheck boot-arg is the alternative (it
            # NOPs the equivalent check inside bluetoothd, see
            # kSkipInternalControllerNVRAMCheck13_3 in BlueToolFixup.cpp, gated
            # to Sonoma and older) but the README calls it "much less efficient",
            # so set the variables instead.
            #
            # These go in Add ONLY, deliberately not in Delete.  Neither variable
            # exists in this machine's NVRAM (checked with `nvram -p | grep -i
            # bluetooth`, empty), and OpenCore's Add writes variables that do not
            # already exist -- so Add alone takes effect here.  Leaving them out
            # of Delete also lets macOS maintain its own values afterwards, which
            # is the normal steady state once Bluetooth works.
            #
            # NOT YET CONFIRMED WORKING on this machine.
            "bluetoothExternalDongleFailed":   D("00"),
            "bluetoothInternalControllerInfo": D("0000000000000000000000000000"),
        },
    },
    "Delete": {
        "4D1FDA02-38C7-4A6A-9CC6-4BCCA8B30102": ["rtc-blacklist"],
        "4D1EDE05-38C7-4A6A-9CC6-4BCCA8B38E36": ["DefaultBackgroundColor", "UIScale"],
        "7C436110-AB2A-4BBB-A880-FE41995C9F82": [
            "boot-args", "csr-active-config", "prev-lang:kbd", "run-efi-updater",
            # recovery-boot-mode: deleted unconditionally, and NOT paired with an
            # entry in Add -- we never want to request a recovery mode, only to
            # make sure a stale request cannot survive a reboot.
            #
            # boot.efi writes this itself when a boot fails repeatedly.  Observed
            # on 2026-08-17: after the kernel hard-reset ~30s past
            # EXITBS (accelerated iGPU config), the fourth boot logged
            #   AAPL: #[EB|R:SRBM] fde-recovery
            #   AAPL: #[EB|LW+]                       (login window, in EFI)
            #   AAPL: #[EB.CS.AUV|VU!] Err(0xF)       (unlock volume failed)
            #   AAPL: #[EB|RESET] 1
            #   AAPL: #[EB|LOG:RESET:FAIL]
            # i.e. boot.efi escalated to FileVault recovery, failed to unwrap
            # the volume encryption key, and reset.  (FileVault IS on here --
            # `fdesetup status` reports "FileVault is On" -- but on a modern
            # sealed-system-volume install only the Data volume is encrypted,
            # so the accompanying `fv_unwrap_vek: No kek blob provided for sys
            # disabled volume` is expected and is not itself the fault.)
            # That is self-sustaining: the variable survives the reset, so every
            # subsequent boot lands in the same EFI login window regardless of
            # what caused the original failure.  It looks exactly like a macOS
            # login loop, but it is pre-kernel -- the trackpad is dead because
            # VoodooI2C has not loaded yet, while the keyboard still works
            # because the firmware drives it.
            "recovery-boot-mode"],
    },
    "LegacyOverwrite": False, "LegacySchema": {}, "WriteFlash": True,
},
"PlatformInfo": {
    "Automatic": True, "CustomMemory": False, "UpdateDataHub": True,
    "UpdateNVRAM": True, "UpdateSMBIOS": True,
    "UpdateSMBIOSMode": "Create", "UseRawUuidEncoding": False,
    "Generic": {
        "AdviseFeatures": False, "MaxBIOSVersion": False,
        "ProcessorType": 0, "SpoofVendor": True,
        "SystemMemoryStatus": "Auto",
        "MLB": SMBIOS["MLB"], "ROM": SMBIOS["ROM"],
        "SystemProductName": SMBIOS["SystemProductName"],
        "SystemSerialNumber": SMBIOS["SystemSerialNumber"],
        "SystemUUID": SMBIOS["SystemUUID"],
    },
},
"UEFI": {
    "APFS": {
        "EnableJumpstart": True, "GlobalConnect": False,
        "HideVerbose": True, "JumpstartHotPlug": False,
        "MinDate": 0, "MinVersion": 0,
    },
    "AppleInput": {
        "AppleEvent": "Builtin", "CustomDelays": False,
        "GraphicsInputMirroring": True, "KeyInitialDelay": 0,
        "KeySubsequentDelay": 0, "PointerDwellClickTimeout": 0,
        "PointerDwellDoubleClickTimeout": 0, "PointerDwellRadius": 0,
        "PointerPollMask": -1, "PointerPollMax": 0, "PointerPollMin": 0,
        "PointerSpeedDiv": 1, "PointerSpeedMul": 1,
    },
    "Audio": {
        "AudioCodec": 0, "AudioDevice": "", "AudioOutMask": 1,
        "AudioSupport": False, "DisconnectHda": False,
        "MaximumGain": -15, "MinimumAssistGain": -30,
        "MinimumAudibleGain": -55, "PlayChime": "Auto",
        "ResetTrafficClass": False, "SetupDelay": 0,
    },
    "ConnectDrivers": True,
    "Drivers": [
        {"Arguments": "", "Comment": "HFS+ support", "Enabled": True,
         "LoadEarly": False, "Path": "HfsPlus.efi"},
        {"Arguments": "", "Comment": "OpenRuntime (required)", "Enabled": True,
         "LoadEarly": False, "Path": "OpenRuntime.efi"},
        {"Arguments": "", "Comment": "GUI picker", "Enabled": True,
         "LoadEarly": False, "Path": "OpenCanopy.efi"},
        {"Arguments": "", "Comment": "Reset NVRAM entry", "Enabled": True,
         "LoadEarly": False, "Path": "ResetNvramEntry.efi"},
        {"Arguments": "", "Comment": "Boot chime (unused)", "Enabled": False,
         "LoadEarly": False, "Path": "AudioDxe.efi"},
    ],
    "Input": {
        "KeyFiltering": False, "KeyForgetThreshold": 5, "KeySupport": True,
        "KeySupportMode": "Auto", "KeySwap": False, "PointerSupport": False,
        "PointerSupportMode": "", "TimerResolution": 50000,
    },
    "Output": {
        "ClearScreenOnModeSwitch": False, "ConsoleFont": "", "ConsoleMode": "",
        "DirectGopRendering": False, "ForceResolution": False,
        "GopBurstMode": False, "GopPassThrough": "Disabled",
        "IgnoreTextInGraphics": False, "InitialMode": "Auto",
        "ProvideConsoleGop": True, "ReconnectGraphicsOnConnect": False,
        "ReconnectOnResChange": False, "ReplaceTabWithSpace": False,
        "Resolution": "Max", "SanitiseClearScreen": False,
        "TextRenderer": "BuiltinGraphics", "UIScale": 0,
        "UgaPassThrough": False,
    },
    "ProtocolOverrides": {
        "AppleAudio": False, "AppleBootPolicy": False,
        "AppleDebugLog": False, "AppleEg2Info": False,
        "AppleFramebufferInfo": False, "AppleImageConversion": False,
        "AppleImg4Verification": False, "AppleKeyMap": False,
        "AppleRtcRam": False, "AppleSecureBoot": False,
        "AppleSmcIo": False, "AppleUserInterfaceTheme": False,
        "DataHub": False, "DeviceProperties": False,
        "FirmwareVolume": False, "HashServices": False,
        "OSInfo": False, "PciIo": False, "UnicodeCollation": False,
    },
    "Quirks": {
        "ActivateHpetSupport": False, "DisableSecurityPolicy": False,
        "EnableVectorAcceleration": True, "EnableVmx": False,
        "ExitBootServicesDelay": 0, "ForceOcWriteFlash": False,
        "ForgeUefiSupport": False, "IgnoreInvalidFlexRatio": False,
        "ReleaseUsbOwnership": True, "ReloadOptionRoms": False,
        "RequestBootVarRouting": True, "ResizeGpuBars": -1,
        "ResizeUsePciRbIo": False, "ShimRetainProtocol": False,
        "TscSyncTimeout": 0, "UnblockFsConnect": False,
    },
    "ReservedMemory": [],
    "Unload": [],
},
}

out = pathlib.Path("/Users/macmini/dev/Razer_mac/build/EFI/OC/config.plist")
with out.open("wb") as f:
    plistlib.dump(config, f, sort_keys=True)
print("written:", out, out.stat().st_size, "bytes")
