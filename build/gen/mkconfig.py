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
# ig-platform-id 00009B3E is the Dortania-recommended laptop framebuffer for
# Coffee Lake Plus / Whiskey Lake. device-id is spoofed to 3E9B because Apple's
# drivers ship no entry for 3EA0.
igpu = {
    "AAPL,ig-platform-id":      D("00009B3E"),
    "device-id":                D("9B3E0000"),
    "framebuffer-patch-enable": D("01000000"),
    # The 0x3E9B0000 framebuffer wants 57 MB stolen (58 MB total) but this
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
    # No connector-type patch: 0x3E9B0000 already ships [0] LVDS + [1] DP +
    # [2] DP (type 0x00000400 -> 00040000 LE), which matches this machine
    # exactly -- internal eDP panel plus USB-C and Thunderbolt 3, no HDMI.
    # Forcing con1/con2 to DP would be a no-op, so it is omitted rather than
    # carried as dead config.
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
    # 0x14 = HBR2, 5.4 Gbps/lane.  The panel is 1920x1080 @ 60 Hz 24-bit,
    # ~3.2 Gbps of payload, so a single lane at this rate already covers it and
    # link training negotiates down from here -- the value is a ceiling, not a
    # demand.  Set explicitly instead of relying on WhateverGreen's internal
    # default so the value is visible in the config.
    #
    # CONFIRMED ON HARDWARE 2026-08-18.  With this pair added and -igfxblt kept,
    # the machine booted to the desktop and stayed up with no panic, where the
    # identical config without them panicked ~30 s after EXITBS twice in a row.
    # VRAM went 7 MB -> 1536 MB, Metal 3 came up, and all three framebuffers
    # (internal eDP + 2x DP) enumerated -- i.e. nothing was traded away for the
    # fix.  The kernel log now shows the divisor arriving as a sane value:
    #   (AppleIntelCFLGraphicsFramebuffer) [DPCD_Info] FB0: Display port config
    #     ver is 1.4
    #   ... [DPCD_Info] FB0 Maximum link rate is 0x14
    #   ... [DPCD_Info] FB0: Maximum lanes is 2
    # Note the log cannot distinguish WhateverGreen's injected 0x14 from a
    # native read of 0x14, so this is evidence the divisor is no longer zero,
    # not proof of which code path supplied it.  The causal link is still solid:
    # -igfxblt alone panicked reproducibly, -igfxblt plus these two keys does
    # not.  Do not drop them on the theory that the panel "reports 0x14 anyway".
    "enable-dpcd-max-link-rate-fix": D("01000000"),
    "dpcd-max-link-rate":            D("14000000"),
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
