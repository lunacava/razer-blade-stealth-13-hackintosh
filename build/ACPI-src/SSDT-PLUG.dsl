/*
 * SSDT-PLUG — enable XCPM (native Intel power management) on the CPU object
 *
 * Verified on this machine: the CPU objects are ACPI Processor() declarations
 * named PR00..PR07 under \_SB (NOT Device(CPU0) style), and the DSDT ships
 * no _PSS / _CST at all — P-states come from XCPM once plugin-type=1 is set.
 *
 * Whiskey Lake (i7-8565U, CPUID 0x0806E0) is XCPM-capable, so this is the
 * correct approach; only pre-Ivy Bridge chips need the legacy route.
 */
DefinitionBlock ("", "SSDT", 2, "RZRMAC", "CpuPlug", 0x00000000)
{
    External (_SB_.PR00, ProcessorObj)

    Method (_SB.PR00._DSM, 4, NotSerialized)
    {
        If (!Arg2)
        {
            Return (Buffer (One) { 0x03 })
        }

        Return (Package (0x02)
        {
            "plugin-type",
            One
        })
    }
}
