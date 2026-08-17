/*
 * SSDT-USBX — USB power properties for Skylake and newer
 *
 * Supplies the per-port current limits macOS expects. Without this, USB
 * charging behaviour and some device wake paths misbehave. Values are the
 * standard Apple laptop set (Skylake+ / MacBookPro15,2 class).
 */
DefinitionBlock ("", "SSDT", 2, "RZRMAC", "USBX", 0x00000000)
{
    Device (_SB.USBX)
    {
        Name (_ADR, Zero)
        Method (_DSM, 4, NotSerialized)
        {
            If (!Arg2)
            {
                Return (Buffer (One) { 0x03 })
            }

            Return (Package (0x08)
            {
                "kUSBSleepPowerSupply",  0x13EC,
                "kUSBSleepPortCurrentLimit", 0x0834,
                "kUSBWakePowerSupply",   0x13EC,
                "kUSBWakePortCurrentLimit",  0x0834
            })
        }
    }
}
