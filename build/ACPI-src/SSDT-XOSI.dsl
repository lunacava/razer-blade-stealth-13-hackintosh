/*
 * SSDT-XOSI — Razer Blade Stealth 13 (RZ09-02812E71, i7-8565U)
 *
 * WHY THIS IS MANDATORY ON THIS MACHINE (verified against the real DSDT):
 *
 *   \_SB.PCI0._INI sets OSYS = 0x03E8 by default, then raises it only via
 *   _OSI("Windows ...") probes.  macOS answers _OSI("Darwin") and returns
 *   FALSE for every Windows string, so OSYS stays 0x03E8.
 *
 *   \_SB.PCI0.I2C1.TPD0 (the trackpad) then breaks in two places:
 *
 *     Method (_INI) { If ((OSYS < 0x07DC)) { SRXO (GPDI, One) } ... }
 *     Method (_CRS) { If ((OSYS < 0x07DC)) { Return (SBFI) }    ... }
 *
 *   SBFI is an IRQ-only resource template with NO I2C serial-bus descriptor,
 *   so VoodooI2C would never learn the bus address -> trackpad dead.
 *   The correct path returns ConcatenateResTemplate(I2CM(...), SBFG), where
 *   SBFG carries the GpioInt tied to \_SB.PCI0.GPI0.
 *
 *   0x07DC == "Windows 2012" (Windows 8).  Reporting Windows 2015 gives
 *   OSYS = 0x07DF, clearing every OSYS gate in the trackpad path.
 *
 * Pair this with an OpenCore ACPI rename: _OSI -> XOSI (all occurrences).
 */
DefinitionBlock ("", "SSDT", 2, "RZRMAC", "XOSI", 0x00000000)
{
    Method (XOSI, 1, NotSerialized)
    {
        /* Strings a real Windows 8.1/10 box would acknowledge.
           Ordered oldest -> newest; ANY match returns TRUE. */
        Local0 = Package (0x09)
            {
                "Windows 2001",       /* Windows XP            -> OSYS 0x07D1 */
                "Windows 2001 SP1",   /* XP SP1                -> 0x07D1 */
                "Windows 2001 SP2",   /* XP SP2                -> 0x07D2 */
                "Windows 2001.1",     /* Server 2003           -> 0x07D3 */
                "Windows 2006",       /* Vista                 -> 0x07D6 */
                "Windows 2009",       /* Windows 7             -> 0x07D9 */
                "Windows 2012",       /* Windows 8             -> 0x07DC */
                "Windows 2013",       /* Windows 8.1           -> 0x07DD */
                "Windows 2015"        /* Windows 10            -> 0x07DF */
            }
        If (Arg0 == "Darwin")
        {
            /* Never claim Darwin here: doing so would re-enter the same
               OSYS-gated paths we are trying to avoid. */
            Return (Zero)
        }

        Return (LNotEqual (Match (Local0, MEQ, Arg0, MTR, Zero, Zero), Ones))
    }
}
