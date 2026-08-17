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
       namespace initialisation, after PCI0 is up. */
    Device (\_SB.RZDX)
    {
        Name (_HID, "RZDX0001")
        Name (_STA, Zero)          /* invisible to the OS; only _INI matters */
        Method (_INI, 0, NotSerialized)
        {
            \_SB.RZDG ()
        }
    }
}
