/*
 * SSDT-PMC — Razer Blade Stealth 13 (RZ09-02812E71, i7-8565U)
 *
 * WHY THIS IS MANDATORY ON THIS MACHINE:
 *
 *   This is a 300-series PCH (Cannon Point-LP).  From Z390/300-series onward
 *   the PMC (D31:F2) is reachable only through MMIO, and there is no standard
 *   ACPI device for it, so Apple invented the _HID "APP9876" that
 *   AppleIntelPCHPMC binds to.  This firmware does not provide it: grep finds
 *   no Device (PMCR) and no "APP9876" anywhere in
 *   dumps/acpi/DSDT-ALASKA-A_M_I_-01072009.dsl.  It only exposes the generic
 *   reservation, Device (PRRE) at line 15370 with _HID PNP0C02 and
 *   _UID "PCHRESV", which Windows uses instead.
 *
 *   Docs/AcpiSamples/Source/SSDT-PMC.dsl states the consequence:
 *     "On certain implementations, including APTIO V, PMC initialisation is
 *      required for NVRAM access.  Otherwise it will freeze in SMM mode."
 *   This machine's ACPI OEM is ALASKA / A M I (APTIO), i.e. exactly that case.
 *
 *   Observed symptom this fixes: the Sonoma installer freezes at "about 18
 *   minutes remaining" -- twice, at the same point -- with the pointer, the
 *   keyboard (Caps Lock LED dead) and the display all frozen at once.  A
 *   whole-machine freeze like that is what an SMM hang looks like, because SMM
 *   preempts the kernel entirely.  Dortania's userspace-issues page lists
 *   "Stuck at 2 minutes remaining" as NVRAM-write related and prescribes
 *   SSDT-PMC specifically for 300-series.  The installer writes NVRAM
 *   variables in its final phase, which is where we stop.
 *
 * ADDRESS VERIFIED AGAINST THIS FIRMWARE (not copied on faith):
 *
 *   PRRE._CRS's BUF0 was decoded by hand; its Memory32Fixed descriptors are
 *     0xFD000000 +0x6A0000     0xFD6F0000 +0x910000
 *     0xFE000000 +0x020000  <- PMC MBAR (0xFE000000) + SPI BAR0 (0xFE010000)
 *     0xFE200000 +0x600000     0xFF000000 +0x1000000 (ReadOnly)
 *   So the sample's base 0xFE000000 / length 0x10000 is correct here: it is
 *   the PMC MBAR half of that reservation, and deliberately excludes SPI BAR0
 *   (AppleIntelPCHPMC only uses the PMC region).
 *
 * WINDOWS SAFETY:
 *
 *   Guarded by _OSI("Darwin"), returning Zero for every other OS, so Windows
 *   keeps using PRRE/PCHRESV exactly as before.  We add a device; we do not
 *   modify or disable PRRE.
 *
 * WHY IT LIVES UNDER LPCB:
 *
 *   Per the sample: "PMC device has nothing to do to LPC bus, but is added to
 *   its scope for faster initialisation.  If we add it to PCI0, where it
 *   normally exists, it will start in the end of PCI configuration, which is
 *   too late for NVRAM support."  LPCB exists here at DSDT line 4691.
 *
 * WHY THIS USES _OSI AND NOT XOSI:
 *
 *   Same reason as SSDT-EC / SSDT-AWAC-DISABLE: ACPI binary patches run
 *   BEFORE table addition, and SSDT-XOSI returns Zero for "Darwin", so an
 *   unpinned _OSI->XOSI rename would silently turn this _STA into a no-op.
 *   The rename is pinned to TableSignature "DSDT".  Do not un-pin it.
 *
 * NOTE: _STA returns 0x0B, not 0x0F -- this matches the official sample.
 *   Bit 2 (0x04, "device is functioning properly") is intentionally clear.
 */
DefinitionBlock ("", "SSDT", 2, "RZRMAC", "PMCR", 0x00000000)
{
    External (_SB_.PCI0.LPCB, DeviceObj)

    Scope (\_SB.PCI0.LPCB)
    {
        Device (PMCR)
        {
            Name (_HID, EisaId ("APP9876"))  // _HID: Hardware ID
            Method (_STA, 0, NotSerialized)  // _STA: Status
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0B)
                }
                Else
                {
                    Return (Zero)
                }
            }
            Name (_CRS, ResourceTemplate ()  // _CRS: Current Resource Settings
            {
                Memory32Fixed (ReadWrite,
                    0xFE000000,         // Address Base — PMC MBAR, verified
                    0x00010000,         // Address Length
                    )
            })
        }
    }
}
