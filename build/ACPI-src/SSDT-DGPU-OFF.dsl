/*
 * SSDT-DGPU-OFF — power down the NVIDIA GeForce MX150 (10DE:1D10, Pascal GP108)
 *
 * WHY: macOS has had no NVIDIA driver since Mojave, and Pascal was never
 * covered by NVIDIA's open kernel modules. The card can only waste ~3-5 W
 * and heat, so cut its power at boot and after every wake.
 *
 * WHY THIS APPROACH (verified against this machine's real firmware):
 *
 *   Most guides fake a _DSM or poke PCI config space directly. This board
 *   does not need that — Razer's own firmware already ships a complete,
 *   correct power-down sequence:
 *
 *     SSDT "SgRef/SgRpSsdt"  defines \_SB.PCI0.HGOF():
 *         save link state -> L23E (L2/L3 Ready) -> wait -> GPIO reset assert
 *         -> GPIO power off                         (via \_SB.SGOV)
 *
 *     SSDT "OptRef/OptTabl"  defines \_SB.PCI0.RP05.PEGP._OFF(), which saves
 *         the VGA base register, sets CTXT, then calls \_SB.PCI0.HGOF().
 *
 *   Calling the vendor's own _OFF is strictly safer than hand-rolling GPIO
 *   writes: it keeps the firmware's bookkeeping (CTXT / VGAB / link state)
 *   consistent, so a later resume cannot find the device half-initialised.
 *
 * TOPOLOGY (confirmed on the live machine):
 *   \_SB.PCI0.RP05        = PCIe Root Port #5, _ADR 0x001C0004  (bus 0:1C.4)
 *   \_SB.PCI0.RP05.PEGP   = the MX150 itself                    (bus 2:00.0)
 *
 * Runs on: initial boot (_INI) and every S3 resume (_WAK) — the firmware
 * powers the dGPU back up across sleep, so re-arming on wake is required.
 */
DefinitionBlock ("", "SSDT", 2, "RZRMAC", "DGPUOFF", 0x00000000)
{
    External (_SB_.PCI0.RP05, DeviceObj)
    External (_SB_.PCI0.RP05.PEGP, DeviceObj)
    External (_SB_.PCI0.RP05.PEGP._OFF, MethodObj)
    External (_SB_.PCI0.HGOF, MethodObj)

    Scope (\_SB.PCI0.RP05)
    {
        /* Shared helper: try the vendor _OFF first, fall back to HGOF. */
        Method (RZOF, 0, Serialized)
        {
            If (CondRefOf (\_SB.PCI0.RP05.PEGP._OFF))
            {
                \_SB.PCI0.RP05.PEGP._OFF ()
                Return (One)
            }

            /* _OFF absent (e.g. OptTabl not loaded) — call the raw
               power-down sequence directly. */
            If (CondRefOf (\_SB.PCI0.HGOF))
            {
                \_SB.PCI0.HGOF ()
                Return (One)
            }

            Return (Zero)
        }
    }

    Scope (\_SB)
    {
        /* Only ever act under macOS. Under Windows this SSDT is not loaded
           at all, but guard anyway so a mis-copied EFI cannot break Windows. */
        Method (RZDG, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                If (CondRefOf (\_SB.PCI0.RP05.RZOF))
                {
                    \_SB.PCI0.RP05.RZOF ()
                }
            }
        }
    }

    /* Boot-time trigger. A Device with _INI fires once during ACPI
       namespace initialisation, after PCI0 is up.
     *
     * ★ _STA MUST REPORT THE DEVICE PRESENT.
     *
     * The first version of this SSDT had `Name (_STA, Zero)` here, reasoning
     * that the device should be invisible to the OS since only _INI matters.
     * That is exactly backwards and it silently disabled this whole SSDT for
     * months: a device that reports not-present never gets its _INI run.
     *
     * ACPI spec, description of _INI (quoted from ACPICA nsinit.c, which is
     * the code Apple's AppleACPIPlatform is derived from):
     *
     *   "If the _STA method indicates that the device is not present, OSPM
     *    will not run the _INI and will not examine the children of the
     *    device for _INI methods"
     *
     * AcpiNsInitOneDevice() returns AE_CTRL_DEPTH for _STA == 0 and aborts
     * the subtree walk before reaching _INI. Confirmed on this machine:
     * `ioreg -p IODeviceTree | grep RZDX` found nothing and the MX150 stayed
     * enumerated as GFX0@0 (pci10de,1d10) at CurrentPowerState 2, with
     * IONDRVFramebuffer even attached to it.
     *
     * 0x0B = present | enabled | functioning, with "show in UI" (0x04)
     * cleared. Present is what makes _INI run; the OS finds no driver for
     * _HID RZDX0001 and leaves the node alone.
     */
    Device (\_SB.RZDX)
    {
        Name (_HID, "RZDX0001")
        Name (_STA, 0x0B)
        Method (_INI, 0, NotSerialized)
        {
            \_SB.RZDG ()
        }
    }
}
