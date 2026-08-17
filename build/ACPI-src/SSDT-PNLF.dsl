/*
 * SSDT-PNLF — backlight control for Intel UHD 620 (Whiskey Lake / CFL+)
 *
 * Verified against the real DSDT: there is NO existing PNLF device and no
 * _BCM/_BCL methods anywhere, so this is a clean add (no rename needed).
 *
 * WhateverGreen looks for a device with _HID "APP0002" to attach its
 * backlight handling to.  For Coffee Lake and newer (Whiskey Lake is a
 * CFL derivative, iGPU 8086:3EA0) the correct nits/levels come from
 * WhateverGreen itself, so PNLF only needs to exist and report present.
 */
DefinitionBlock ("", "SSDT", 2, "RZRMAC", "PNLF", 0x00000000)
{
    External (_SB_.PCI0.GFX0, DeviceObj)

    Device (_SB.PCI0.GFX0.PNLF)
    {
        /* _HID only — an ACPI device must not carry both _HID and _ADR
           (iasl warning 3073). PNLF is a pseudo-device, so _HID is correct. */
        Name (_HID, EisaId ("APP0002"))
        Name (_CID, "backlight")
        Name (_UID, 0x0A)    /* 10 = Coffee Lake+ backlight profile */
        Name (_STA, 0x0B)
    }
}
