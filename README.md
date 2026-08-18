# Razer Blade Stealth 13 (RZ09-02812E71) — macOS Sonoma / OpenCore

OpenCore configuration and engineering notes for running **macOS Sonoma 14.6.1**
on a **Razer Blade Stealth 13 late-2018 (RZ09-02812E71)**, dual-booting with
Windows 11 on the same NVMe SSD.

Everything here was derived from *this* machine's own firmware dumps and boot
logs, not copied from a guide for a different laptop. Where a setting is
non-obvious, the code comment next to it cites the evidence (DSDT line numbers,
OpenCore log lines, or the upstream doc that mandates it). If you have this
model, the two findings in [Key findings](#key-findings) are probably what you
are looking for.

> **Status:** boots to a working macOS userland (RTC, EC/battery, Wi-Fi, audio,
> Ethernet, NVMe, trackpad). Installed with `-igfxvesa` (unaccelerated
> framebuffer); real iGPU acceleration is still open. See
> [Current state](#current-state).

## Hardware

| | |
|---|---|
| Model | Razer Blade Stealth 13, RZ09-02812E71 (late 2018) |
| CPU | Intel Core i7-8565U (Whiskey Lake-U, 4C/8T) |
| iGPU | Intel UHD Graphics 620 |
| dGPU | NVIDIA GeForce MX150 — **disabled via ACPI** (no macOS driver exists) |
| Wi-Fi / BT | Intel Wireless-AC 9560 (CNVi) |
| Audio | Realtek ALC298 (`alcid=30`) |
| Trackpad | I²C HID via VoodooI2C |
| Firmware | AMI, **BIOS 1.01 (2018/11/12)** |
| SMBIOS | `MacBookPro15,2` |

### ⚠ Do not update the BIOS

This config is built and tested against **BIOS 1.01**. Multiple owners of this
model have reported that **BIOS 3.02 breaks booting**. Decline Windows Update
and Razer Synapse offers to flash firmware. See `docs/bios-settings.md` for the
required setup screens.

## Key findings

These two are the reason this repo exists. Both are specific to this firmware
and neither is obvious from a generic Whiskey Lake guide. Together they were the
difference between a boot that died a few seconds after `DSMOS has arrived` and
a full userland.

### 1. There is no `Device (EC)` — you must add one, and must *not* rename

This DSDT declares **two** `PNP0C09` embedded controllers and neither is named
`EC`:

```
58510:  Device (H_EC)   _HID PNP0C09  _UID 1   _STA -> Return (Zero)     ; disabled stub
59830:  Device (EC0)    _HID PNP0C09           _STA -> Return (0x0F)     ; the live one
```

`AppleACPIEC` looks for a device literally named `EC`, finds nothing, and never
attaches. Fix: **add a fake `Device (EC)` with `_HID "ACID0001"`**
(`build/ACPI-src/SSDT-EC.dsl`) and leave `EC0` completely alone.

Do **not** rename `EC0` → `EC`. Upstream `SSDT-EC.dsl` is explicit: *"Try NOT to
rename EC0, H_EC, etc. to EC. These devices are incompatible with macOS and may
break at any time."*

Also, unlike the desktop instructions, **`EC0` must stay enabled** on this
laptop: `SMCBatteryManager` reads real capacities through `EC0`'s region, and
`ECEnabler.kext` is loaded specifically to make its 16-bit EC field reads work.
Disabling `EC0` kills battery reporting.

### 2. `STAS` is never assigned, so the legacy RTC is disabled

On this 300-series PCH the firmware ships both the legacy `PNP0B00` RTC and the
ACPI000E "Time and Alarm Device" (AWAC), and selects between them with one NVRAM
byte, `STAS`. Their `_STA` methods are exact inverses:

```
20456:  Device (RTC)   _HID PNP0B00    _STA: STAS == One  -> 0x0F, else 0
20515:  Device (AWAC)  _HID ACPI000E   _STA: STAS == Zero -> 0x0F, else 0
```

`STAS` is declared once (line 1456, an 8-bit field in the firmware NVRAM region)
and read in exactly those two places — **there is no assignment anywhere in the
DSDT**. It stays `0`, so AWAC is enabled and the legacy RTC is disabled. macOS
has no ACPI000E driver.

Fix: force `STAS = One` in `\_INI`, which runs before any `_STA` is evaluated
(`build/ACPI-src/SSDT-AWAC-DISABLE.dsl`). Guarded by `_OSI("Darwin")`, so
Windows keeps using AWAC unchanged.

### 3. The `_OSI` → `XOSI` rename must be pinned to `TableSignature = DSDT`

A trap worth documenting, because failing to do this looks exactly like "my
SSDTs didn't work".

`Configuration.pdf` states: *"Perform binary patches in ACPI tables **before**
table addition or removal."* An unpinned `_OSI` → `XOSI` rename therefore
rewrites **your own injected SSDTs too**. Since `SSDT-XOSI` deliberately returns
`Zero` for `"Darwin"`, the `_OSI("Darwin")` guards in both SSDTs above would
silently become no-ops — the tables load and do nothing.

This is not theoretical; it is visible in this machine's own DEBUG log, where
the unpinned rename hit a Razer Optimus firmware table (`006C62615474704F` =
ASCII `OptTabl`):

```
OCA: Patching SSDT (OEM 006C62615474704F) of 7949 bytes ... replaced 1 of 0
```

Every `OSYS` gate the rename actually exists for lives in the DSDT, so pinning
`TableSignature` to `"DSDT"` (`44534454`) costs nothing.

### Other notes

- **`igfxonln=1` is harmful here.** `force-online` marks all three connectors
  (internal eDP + DP×2) connected; with no external display attached, macOS
  tries to initialize displays that do not exist.
- **`AirportItlwm` works on Sonoma 14.6.1.** `itlwm` + HeliPort is not needed.
  The `en0: Error configuring antenna diversity (index = -1)` message is a known
  harmless one for CNVi 9560.
- **Do not add an HDAS→HDEF rename** — it breaks the `CondRefOf HDAS.PS0X` hook
  that `SSDT-HDAS-CDEC` relies on.
- Benign log noise: `Forcing CS_RUNTIME for entitlement` (normal system
  sealing), `vm_shared_region_start_address() failed`, `AppleKeyStore: operation
  failed` (no T2), `IO8O211APIUserClient failed MACF`.

## What is in this repo

```
build/gen/mkconfig.py    Generates OC/config.plist.  The primary artifact --
                         every quirk, kext and patch with its rationale inline.
build/ACPI-src/*.dsl     ACPI sources (+ compiled .aml) for the 8 SSDTs.
docs/hardware-findings.md  Per-device investigation log: what was tried, what the
                         machine actually reported, what the conclusion was.
docs/install-runbook.md  Step-by-step install procedure, incl. component versions
                         and SHA-256 hashes.
docs/bios-settings.md    Required BIOS screens.
docs/network-sharing.md  Internet-sharing setup used to drive the install remotely.
dumps/acpi/              This machine's ACPI tables (DSDT/SSDT, AML + decompiled).
                         The evidence base for everything above.
logs/                    OpenCore DEBUG log (source of the OptTabl finding).
bin/mkusb                Builds the install USB.
bin/rzps                 Runs PowerShell on the Windows side over SSH.
tools/share-{on,off}.sh  Mac-side NAT/DHCP for the install network.
```

The assembled `EFI/` trees, upstream kext zips, and the USB backup are **not**
committed (see `.gitignore`) — they are large and reproducible, and the backup
contains personal files.

## Building

```sh
cp build/gen/smbios.local.py.example build/gen/smbios.local.py
$EDITOR build/gen/smbios.local.py      # your own GenSMBIOS values
python3 build/gen/mkconfig.py          # -> build/EFI/OC/config.plist
```

You must supply your own SMBIOS identity. The serial / MLB / UUID / ROM are
per-machine values macOS sends to Apple; reusing someone else's causes
collisions that break iMessage, FaceTime and App Store sign-in **on both
machines**. Generate them with
[GenSMBIOS](https://github.com/corpnewt/GenSMBIOS) for `MacBookPro15,2`.

`mkconfig.py` writes only `build/EFI/OC/config.plist`. Copy it to
`build/EFI/BOOT/` and to the USB tree yourself; keep `EFI\BOOT\` self-contained.

Kexts, drivers and OpenCore itself are **not** vendored. Get them from the
official upstream GitHub releases only — OpenCore is the first thing that
executes at boot, so provenance matters. Versions used:

| Component | Version |
|---|---|
| OpenCore | 1.0.7 |
| Lilu | 1.7.2 |
| VirtualSMC | 1.3.7 |
| WhateverGreen | 1.7.0 |
| AppleALC | 1.9.7 |
| ECEnabler | 1.0.6 |
| NVMeFix | 1.1.3 |
| RestrictEvents | 1.1.6 |
| VoodooI2C | 2.9.1 |
| AirportItlwm | 2.3.0 (Sonoma 14.4 build) |
| IntelBluetooth | 2.4.0 |

Validate with `ocvalidate` before every deploy. Current config: *No issues
found.*

## Current state

Daily-driver usable. macOS Sonoma 14.8.9 (23J631), SMBIOS `MacBookPro15,2`,
OpenCore 1.0.7, BIOS 1.01 (never flashed).

Boot-args: `-v debug=0x100 keepsyms=1 alcid=30 -igfxblt -btlfxboardid`

### Working

| Area | Notes |
|---|---|
| NVMe / APFS / RTC | Dual-boot with Windows 11 on the same disk |
| Battery percentage | ECEnabler — the 16-bit EC field is the cause (finding 4) |
| Wi-Fi | AirportItlwm (native UI). No AirDrop/Handoff/Sidecar — Broadcom-only features |
| Audio | AppleALC `alcid=30` |
| Trackpad | VoodooI2C + VoodooI2CHID. Force Click disabled so deep presses register as normal clicks |
| USB | USBToolBox + UTBMap, 9 ports on `XHC`. External USB-A corrected from `UsbConnector 255` to `3` |
| **iGPU acceleration** | Metal 3 on UHD 620. Layout `0x3EA50009`, `framebuffer-camellia = 0`, `stolenmem`/`fbmem` in place of a BIOS DVMT mod, `-igfxblt` |
| **Display sleep** | Works. `-igfxblr` is silently dead on Sonoma; `-igfxblt` is the replacement |
| **S3 system sleep** | Works on AC and on battery, including with an external display attached. `RWAK` LIDS patch applied at DSDT `0x16796` |
| **Lid close** | Sleeps. `AppleClamshellCausesSleep` tracks `pmset sleep`, so it reads `No` whenever sleep is disabled |
| **Brightness keys** | `tools/brtd` — a small LaunchAgent daemon. The keys and their HID usages were fine all along; macOS simply has no handler for Consumer `0x6F`/`0x70` here (finding 22) |
| **External display** | Left USB-C, 1920x1080@60, 30-bit, extended desktop, survives S3. This is the issue the Reddit report for this exact laptop left open for six years (finding 23) |

### Open / phase 2

- **Right USB-C carries no video**, and that is our own trade-off rather than a
  fault: its DP alt mode is muxed inside the Alpine Ridge JHL6240, which BIOS
  `Thunderbolt = Disabled` leaves unpowered. Untested experiment — enable it in
  BIOS but *keep* the `AppleThunderboltNHI` block, since the old hard reset was
  NHI allocating DMA rings against a powered-down device. Fully revertible from
  within BIOS. Would also allow two external displays.
- Clamshell operation. Measured requirement: AC plus external input, because
  `PMRD` re-enables clamshell sleep at `ac 0`.
- Resolutions above 1080p60, and DisplayPort audio.
- Whether `enable-dpcd-max-link-rate-fix` / `dpcd-max-link-rate` are still
  needed now that the framebuffer layout is correct. Failure mode is a boot
  panic, so test alone with a revert script.
- CodecCommander; optional `_WAK` hook to re-off the dGPU after resume.
- TB3 xHCI (`8086:15DB`, 4 ports) is deliberately unmapped, so those ports run
  untyped.

Decided against, with measurements: CPUFriend (finding on the 4.1 GHz
question), an HDAS→HDEF rename (would break the `CondRefOf HDAS.PS0X` hook),
`igfxonln=1`, and a `framebuffer-con1/con2-type` patch (the stock DP+DP layout
already matches — later confirmed by DP coming up with no patch at all).

## Credits

Built on [OpenCorePkg](https://github.com/acidanthera/OpenCorePkg) and the
acidanthera kext ecosystem, following the
[Dortania OpenCore Install Guide](https://dortania.github.io/OpenCore-Install-Guide/).
The EC / RTC symptom cluster that led to findings 1 and 2 is described on
Dortania's *Kernel issues* page.

## License / disclaimer

Notes and configuration provided as-is, for reference by owners of this specific
machine. Hackintoshing can leave a machine unbootable and may violate the macOS
EULA in your jurisdiction. Back up Windows first; verify every value against
your own firmware dumps rather than trusting these.
