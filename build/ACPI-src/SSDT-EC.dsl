/*
 * SSDT-EC — Razer Blade Stealth 13 (RZ09-02812E71, i7-8565U)
 *
 * WHY THIS IS MANDATORY (verified against the real DSDT dump):
 *
 *   dumps/acpi/DSDT-ALASKA-A_M_I_-01072009.dsl declares TWO PNP0C09 embedded
 *   controllers and NOT ONE of them is named "EC":
 *
 *     58510:  Device (H_EC)   _HID PNP0C09  _UID 1   _STA -> Return (Zero)
 *     59830:  Device (EC0)    _HID PNP0C09           _STA -> Return (0x0F)
 *
 *   So the live controller is EC0 and H_EC is a disabled stub.  macOS looks for
 *   a device literally named EC and, not finding one, AppleACPIEC never gets a
 *   nub to attach to.  Dortania lists the resulting stall under
 *   "Stuck on RTC..., PCI Configuration Begins, Previous Shutdown..., HPET,
 *   HID: Legacy..." with the fix "Add EC SSDT" -- and our boot does print
 *   "Previous shutdown cause: 5" right before it dies.
 *
 * WHY WE DO NOT RENAME EC0 -> EC:
 *
 *   Docs/AcpiSamples/Source/SSDT-EC.dsl is explicit:
 *     "Try NOT to rename EC0, H_EC, etc. to EC.  These devices are
 *      incompatible with macOS and may break at any time."
 *   Renaming would bind AppleACPIEC to real Razer EC hardware.  Instead we add
 *   a separate fake device with _HID "ACID0001" that AppleACPIEC can own
 *   harmlessly, and leave EC0 completely untouched.
 *
 * WHY EC0 MUST STAY ENABLED (differs from the desktop instructions):
 *
 *   The sample's commented-out block disables the existing EC0 -- correct on
 *   desktops.  On THIS laptop SMCBatteryManager reads real capacities through
 *   EC0's region ("binfo: 0 battery 0 ... (4602/4743)" in the boot log), and
 *   ECEnabler.kext is loaded specifically to make those 16-bit EC field reads
 *   work.  Disabling EC0 would kill battery reporting.  So we ADD ONLY.
 *
 * WHY THIS USES _OSI AND NOT XOSI:
 *
 *   Configuration.pdf: "Perform binary patches in ACPI tables BEFORE table
 *   addition or removal."  Our _OSI->XOSI rename therefore hits this SSDT too,
 *   and SSDT-XOSI deliberately returns Zero for "Darwin", which would silently
 *   turn the check below into a no-op.  The rename is now pinned to
 *   TableSignature "DSDT" (where the only OSYS gates live) so the _OSI call
 *   here survives as a genuine _OSI.  Do not un-pin it.
 */
DefinitionBlock ("", "SSDT", 2, "RZRMAC", "SsdtEC", 0x00000000)
{
    External (_SB_.PCI0.LPCB, DeviceObj)

    Scope (\_SB.PCI0.LPCB)
    {
        Device (EC)
        {
            Name (_HID, "ACID0001")  // _HID: Hardware ID
            Method (_STA, 0, NotSerialized)  // _STA: Status
            {
                If (_OSI ("Darwin"))
                {
                    Return (0x0F)
                }
                Else
                {
                    Return (Zero)
                }
            }
        }
    }
}
