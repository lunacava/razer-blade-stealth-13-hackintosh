# OpenCore DEBUG logs

Captured from the USB ESP (`EFI/OC/opencore-*.txt`) with `Misc/Debug/Target`
including file output.

`opencore-2026-08-17-195336.txt` is the log that produced the
`TableSignature`-pinning finding described in the README:

```
OCA: Patching SSDT (54445353) (OEM 006C62615474704F) of 7949 bytes ... replaced 1 of 0
```

`006C62615474704F` is ASCII `OptTabl` — Razer's Optimus firmware SSDT. An
unpinned `_OSI` → `XOSI` rename measurably modified a non-DSDT table on real
hardware.

## Redaction

Three values were replaced with equal-length `X` placeholders, so byte offsets
in the file are unchanged:

| Original | Placeholder | Lines |
|---|---|---|
| SMBIOS `SystemSerialNumber` | `XXXXXXXXXXXX` | `OC: Setting SSN ...` |
| SMBIOS `MLB` | `XXXXXXXXXXXXXXXXX` | `OC: Setting MLB ...` |
| `ROM` / `HW_ROM` MAC | `XX:XX:XX:XX:XX:XX` | `OC: Setting ROM ...` |

Nothing else in the file was altered. These logs are CRLF ASCII — pipe through
`tr -d '\r'` before grepping (do **not** try to convert them as UTF-16, it
produces mojibake).
