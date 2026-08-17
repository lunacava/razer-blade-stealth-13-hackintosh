/*
 * SSDT-AWAC-DISABLE — Razer Blade Stealth 13 (RZ09-02812E71, i7-8565U)
 *
 * WHY THIS IS MANDATORY (verified against the real DSDT dump):
 *
 *   This is a 300-series (Cannon Point-LP) PCH, so the firmware ships the
 *   ACPI000E "Time and Alarm Device" (AWAC) alongside the legacy PNP0B00 RTC
 *   and picks between them with a single NVRAM byte, STAS.  From
 *   dumps/acpi/DSDT-ALASKA-A_M_I_-01072009.dsl:
 *
 *     20456:  Device (RTC)    _HID PNP0B00
 *               _STA: If ((STAS == One))  { Return (0x0F) } Else { Return (0) }
 *
 *     20515:  Device (AWAC)   _HID "ACPI000E"
 *               _STA: If ((STAS == Zero)) { Return (0x0F) } Else { Return (0) }
 *
 *   The two are exact inverses of each other.  STAS is declared once at line
 *   1456 (an 8-bit field in the firmware's NVRAM OperationRegion) and is read
 *   in exactly those two places -- grep finds NO assignment anywhere in the
 *   DSDT.  It therefore stays 0, which means:
 *
 *       AWAC = enabled,  legacy RTC = DISABLED.
 *
 *   macOS has no ACPI000E driver.  AppleRTC finds nothing, and Dortania lists
 *   this stall as "Stuck on RTC..., PCI Configuration Begins, Previous
 *   Shutdown..., HPET, HID: Legacy...".  Our boot prints
 *   "Previous shutdown cause: 5" and then stops.
 *
 *   Forcing STAS = 1 in \_INI (which runs before any _STA is evaluated) flips
 *   the pair: RTC comes back and AWAC disappears.  This is the approach
 *   Docs/AcpiSamples/Source/SSDT-AWAC-DISABLE.dsl prescribes, and it is
 *   preferred over an RTC _STA binary patch ("Do not use RTC ACPI patch").
 *
 * WINDOWS SAFETY:
 *
 *   Guarded by _OSI("Darwin"), so Windows keeps using AWAC exactly as before.
 *   Nothing about the dual-boot side changes.
 *
 * WHY THIS USES _OSI AND NOT XOSI:
 *
 *   Configuration.pdf: "Perform binary patches in ACPI tables BEFORE table
 *   addition or removal."  Our _OSI->XOSI rename would otherwise rewrite the
 *   call below, and SSDT-XOSI deliberately returns Zero for "Darwin" -- STAS
 *   would never be assigned and this table would silently do nothing.  The
 *   rename is now pinned to TableSignature "DSDT".  Do not un-pin it.
 */
DefinitionBlock ("", "SSDT", 2, "RZRMAC", "NOAWAC", 0x00000000)
{
    External (STAS, IntObj)

    Scope (\)
    {
        Method (_INI, 0, NotSerialized)  // _INI: Initialize
        {
            If (_OSI ("Darwin"))
            {
                STAS = One
            }
        }
    }
}
