/*
 * SSDT-HDAS-CDEC — Realtek ALC298 post-sleep recovery hook
 *
 * VERIFIED FIRMWARE HOOK: \_SB.PCI0.HDAS._PS0 ends with
 *
 *     If (CondRefOf (\_SB.PCI0.HDAS.PS0X)) { PS0X () }
 *
 * so we can attach to the D3->D0 transition by simply *defining* PS0X in an
 * SSDT — no DSDT byte patching of the audio path required.
 *
 * NOTE ON NAMING: this SSDT deliberately targets HDAS, matching the real
 * DSDT. Do NOT add an OpenCore HDAS->HDEF rename while using this file, or
 * the CondRefOf above will look for \_SB.PCI0.HDEF.PS0X and never find the
 * method defined here. AppleALC matches the controller by PCI ID
 * (8086:9DC8) plus layout-id, so the HDEF rename is not needed on this board.
 *
 * Codec: Realtek ALC298  (HDAUDIO\FUNC_01&VEN_10EC&DEV_0298&SUBSYS_1A581000)
 * layout-id 30 — reported working on this exact model (i7-8565U Blade
 * Stealth 13 Early 2019) by u/OpaqueWalrus; 29 is the 8550U value.
 *
 * CodecCommander.kext does the actual verb re-send; this SSDT only ensures
 * the power-state callback exists so the kext is driven at the right moment.
 */
DefinitionBlock ("", "SSDT", 2, "RZRMAC", "HDASCDEC", 0x00000000)
{
    External (_SB_.PCI0.HDAS, DeviceObj)

    Scope (\_SB.PCI0.HDAS)
    {
        /* Called by the stock _PS0 when the controller returns to D0.
           Left intentionally minimal: CodecCommander hooks the same
           transition and replays the codec verbs. */
        Method (PS0X, 0, Serialized)
        {
            /* no-op body; existence is what the firmware checks */
        }

        /* Advertise the codec layout so AppleALC picks 30 without a
           boot-arg. Keeps alc-layout-id out of the config where it is
           easy to forget. */
        Method (_DSM, 4, NotSerialized)
        {
            If (!Arg2)
            {
                Return (Buffer (One) { 0x03 })
            }

            Return (Package (0x04)
            {
                "layout-id", Buffer (0x04) { 0x1E, 0x00, 0x00, 0x00 },  /* 30 */
                "built-in",  Buffer (One)  { 0x00 }
            })
        }
    }
}
