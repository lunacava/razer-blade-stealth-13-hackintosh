# Razer Blade Stealth 13 (RZ09-02812E71) — 実機調査結果

調査日: 2026-08-16 / 取得方法: SSH (管理者権限) + kernel32 GetSystemFirmwareTable + レジストリ HKLM\HARDWARE\ACPI

## システム識別

| 項目 | 値 |
|---|---|
| SKU | RZ09-02812E71 |
| モデル名 | Razer Blade Stealth |
| CPU | Intel Core i7-8565U (Whiskey Lake-U, CPUID 0x0806E0) |
| BIOS | **1.01 (2018/11/12)** ← 絶対に更新しない |
| ACPI OEM | ALASKA / A M I / rev 01072009 |
| OS | Windows 11 Home build **26200**（2026-08-18 実測。当初 26100 → Windows Update が走った） |
| 内蔵パネル | DISPLAY\SHP14B8 (Sharp) — "Integrated Monitor" |
| バッテリー | Razer (serial redacted), Li-Ion, 設計 53,153 mWh / 満充電 52,033 mWh = **劣化 2.1% のみ（極めて良好）** |
| S3 スリープ | **利用可能**（S0ix は非対応）→ macOS のスリープに好都合 |

## PCI デバイス完全マップ

| ACPI パス | Bus:Dev.Fn | PCI ID | デバイス |
|---|---|---|---|
| `_SB.PCI0` | 00:00.0 | 8086:3E34 | Host Bridge (Whiskey Lake) |
| `_SB.PCI0.GFX0` | 00:02.0 | **8086:3EA0** | **Intel UHD Graphics 620** |
| — | 00:04.0 | 8086:1903 | DPTF Processor Participant |
| — | 00:12.0 | 8086:9DF9 | Thermal Subsystem |
| `_SB.PCI0.XHC` | 00:14.0 | 8086:9DED | USB 3.1 xHCI |
| — | 00:14.2 | 8086:9DEF | PCI standard RAM (Shared SRAM) |
| **WiFi** | **00:14.3** | **8086:9DF0** | **Intel Wireless-AC 9560 ← CNVi!!** |
| `_SB.PCI0.I2C0` | 00:15.0 | 8086:9DE8 | Serial IO I2C #0 |
| **`_SB.PCI0.I2C1`** | **00:15.1** | **8086:9DE9** | **Serial IO I2C #1 ← トラックパッド** |
| — | 00:16.0 | 8086:9DE0 | Management Engine |
| `_SB.PCI0.RP01` | 00:1C.0 | 8086:9DB8 | PCIe Root Port #1 (空き) |
| **`_SB.PCI0.RP05`** | **00:1C.4** | **8086:9DBC** | **PCIe RP#5 → MX150** |
| `_SB.PCI0.RP09` | 00:1D.0 | 8086:9DB0 | PCIe RP#9 → Thunderbolt |
| **`_SB.PCI0.RP13`** | **00:1D.4** | **8086:9DB4** | **PCIe RP#13 → NVMe SSD** |
| `_SB.PCI0.LPCB` | 00:1F.0 | 8086:9D84 | LPC Controller |
| `_SB.PCI0.HDAS` | 00:1F.3 | 8086:9DC8 | HD Audio → **Realtek ALC298** (10EC:0298) |
| — | 00:1F.4 | 8086:9DA3 | SMBus |
| — | 00:1F.5 | 8086:9DA4 | SPI (flash) |
| dGPU | 02:00.0 | **10DE:1D10** | NVIDIA GeForce MX150 (Pascal GP108) |
| TB3 upstream | 03:00.0 | 8086:15DA | PCIe Upstream Switch (JHL6240 Alpine Ridge LP) |
| TB3 down | 04:00/01/02.0 | 8086:15DA | PCIe Downstream Switch ×3 |
| TB3 NHI | 05:00.0 | 8086:15D9 | Thunderbolt Controller |
| TB3 xHCI | 59:00.0 | 8086:15DB | USB 3.1 xHCI (TB3側) |
| SSD | 60:00.0 | 144D:A808 | **Samsung 970 EVO 1TB** (PM981ではない=OK) |

サブシステムID は全体で `1A58:1000`（1A58 = Razer/Wistron）。

## ★ 重大な発見 1: WiFi が CNVi である

**`8086:9DF0` は Intel Wireless-AC 9560 の CNVi 版。**

CNVi (Integrated Connectivity) は、MACをPCH内部に置き、M.2スロット側にはRF部分のみを載せる方式。つまり:

- スロットの電気的インターフェースが **PCIe/USB ではなく CNVio 専用**
- **CNVi スロットに通常の PCIe M.2 WiFi カード（BCM94352Z / DW1560）を挿しても動作しない**
- Broadcom カードは PCIe を要求するため、物理的に挿さっても認識されない

これは「WiFiカードを買って差し替える」計画の前提を崩す。→ 別途対処方針が必要（下記「未解決課題」参照）。

Bluetooth 側: 当初「Windows 側の調査では USB `VID_8087` が見えない」と記録したが、
これは**検索が不十分だっただけ**だった（2026-08-18 再確認）。Windows でも見える:

```
Status Class      FriendlyName                    InstanceId
OK     Bluetooth  インテル(R) ワイヤレス Bluetooth(R)  USB\VID_8087&PID_0AAA\5&1A1FDAD1&0&10
                                                                                        ^^ port 10
```

`Get-PnpDevice -Class USB` で絞ると**漏れる**。この device の Class は `USB` ではなく
`Bluetooth` だからである。`-Class` で絞らず `InstanceId -match 'VID_8087'` で探すこと。

macOS 側でも XHCI の **port 10**（ノード `HS10`、Windows の root hub port 10 と同一）に
`8087:0AAA` として列挙される。
つまり CNVi の BT は内部的に USB でぶら下がっており、両 OS で見える。そして動作している:

```
Bluetooth Controller:  Address FC:77:74:85:D8:82   State: On
Chipset: THIRD_PARTY_DONGLE   Transport: USB   Firmware Version: v256 c256
Supported services: 0x392039 < HFP AVRCP A2DP HID Braille LEA AACP GATT SerialPort >
```

`IntelBluetoothFirmware` 2.4.0 + `BlueToolFixup` 2.7.2 で対応済み。ioreg 上の
ノード名が `IOUSBHostDevice@14800000` と無名なのは USB の Product String を
持たないだけで、`registered, matched, active` = ドライバは一致している。
**無名を「ドライバ未一致」と読み違えないこと。**

## ★ 重大な発見 2: スリープ修正パッチは適用可能（ただし vampjaz とは別パターン）

`RWAK` メソッド内に LID 状態を読む該当コードが **存在する**（vampjaz が「機体によっては無い」と警告した部分）。ただし ASL の形が違うため、**彼のパッチはそのまま使えない**。

### DSDT 内の LIDS 代入は3箇所

| # | AML offset | 場所 | ASL |
|---|---|---|---|
| 1 | **0x16796** | **`RWAK` (Arg0==3\|\|4)** | `Local0 = (\_SB.PCI0.LPCB.EC0.PSTA & 0x04)` ← **フルパス** |
| 2 | 0x4150E | `EC0._REG` | `Local0 = (PSTA & 0x04)` ← 相対 |
| 3 | 0x416B9 | `EC0._Q14` | `Local0 = (PSTA & 0x04)` ← 相対 |

3箇所すべて同一ロジック:
```asl
Local0 = (PSTA & 0x04)
LIDS = Zero
If (Local0) { LIDS = One }
If (IGDS) {
    If ((LIDS == One)) { GFX0.CLID = 0x03 } Else { GFX0.CLID = Zero }
}
```

### 狙い撃ちできる根拠

RWAK 直後の `If (IGDS)` の PkgLength が **0x3A**（他2箇所は 0x2C）。この違いにより21バイトのパターンが **DSDT 全体で offset 0x16796 に1回だけ出現**する（検証済み）。

```
Find    : 70 00 4C 49 44 53 A0 08 60 70 01 4C 49 44 53 A0 3A 49 47 44 53
Replace : 70 01 4C 49 44 53 A0 08 60 70 01 4C 49 44 53 A0 3A 49 47 44 53
          ^^ ^^ Store(Zero,LIDS) → Store(One,LIDS)
```
- 長さ完全一致（21バイト）→ OpenCore の ACPI Patch で安全に適用可
- `Count = 1` を指定
- 意味: レジューム時に「LIDは常に開いている」と報告させ、macOS の即再スリープを防ぐ

Base64:
- Find: `cABMSURToAhgcAFMSURToDpJR0RT`
- Replace: `cAFMSURToAhgcAFMSURToDpJR0RT`

## ★ 発見 3: MX150 の電源オフ手段が ACPI に用意されている

Optimus 用 SSDT が2つ存在:
- `SgRef/SgRpSsdt` (1,159 bytes) — `\_SB.PCI0.HGON` / `\_SB.PCI0.HGOF` を定義
- `OptRef/OptTabl` (7,949 bytes) — 上記を呼び出す `_DSM` / `_ON` / `_OFF` ロジック

`HGOF()` は完全な電源断シーケンスを実装:
```asl
ELCT = LCTR; HVID = SVID; HDID = SDID; LTRE = LREN   // 状態退避
L23E = One                                            // L2/L3 Ready 遷移
SGPO (HRE0, HRG0, HRA0, One)                          // GPIO: RESET アサート
SGPO (PWE0, PWG0, PWA0, Zero)                         // GPIO: 電源オフ
```

さらに DSDT 側に `\_SB.PCI0.RP05.POFF` / `.PON` / `.PINI` が External 宣言されている（18148行, 18230行で呼び出し）。

**→ SSDT-DGPU-OFF は `\_SB.PCI0.RP05` の `_OFF` に `HGOF()` を呼ぶ形で書ける。** 一般的な「_DSM で無効化」より確実で、ファームウェア設計通りの正規手順。

## その他確定事項

### トラックパッド
- ACPI パス: **`\_SB.PCI0.I2C1.TPD0`**（実機で BIOS 名として確認）
- DSDT 上の `_HID` 候補: `SYNA2393`（Synaptics）/ `ELAN0406`
- Windows 上は `ACPI\1A581000` で列挙、`HID-compliant touch pad` として動作 = **Windows Precision Touchpad (I2C HID)**
- → VoodooI2C + **VoodooI2CHID** で動くはず。VoodooI2CSynaptics は不要な可能性が高い（HID記述子経由のため）
- SSDT-XOSI が必須（DSDT 内 `_OSI` 参照 11箇所、`XOSI` は未定義）

### オーディオ
- **Realtek ALC298** (`HDAUDIO\FUNC_01&VEN_10EC&DEV_0298&SUBSYS_1A581000`)
- ACPI パス `\_SB.PCI0.HDAS` → **リネームしない**（`HDAS._PS0` 内の `CondRefOf (HDAS.PS0X)` フックが `HDEF.PS0X` を探しに行って壊れる。AppleALC は PCI ID 8086:9DC8 + layout-id で一致するのでリネーム不要）
- AppleALC layout-id **30**（同一機種 i7-8565U / Blade Stealth 13 Early 2019 の成功報告で確定。29 は 8550U 機の値だった）

### USB ポート（物理）
PCH xHCI (00:14.0) 配下:
| Port | デバイス |
|---|---|
| HS02 | Generic USB Hub (05E3:0610) |
| HS06 | USB Composite (13D3:56D5) = **内蔵カメラ** |
| HS08 | USB Composite (1532:0239) = **内蔵キーボード + Razer Chroma** |
| SS14 | Generic SuperSpeed Hub (05E3:0626) |

TB3 xHCI (59:00.0) は別コントローラ。USBMap は macOS 上で実施が必要（Windows側だけでは全ポート判定不可）。

#### macOS 側から見たポート番号（2026-08-18 実測、USBMap 未実施の素の状態）

コントローラは `XHC@14000000`（`AppleIntelCNLUSBXHCI`、locationID 335544320）**1つだけ**。
**訂正:** ここには「TB3 側の xHCI は Thunderbolt を Block しているため列挙されない」と
書いてあったが**誤り**。Block しているのは `IOThunderboltFamily` /
`AppleThunderboltNHI` であり、TB3 の xHCI 機能は別の PCI デバイスとして
`AppleUSBXHCIAR` が掴む。実測（2026-08-18）:

```
system_profiler SPUSBDataType:
  USB 3.1 Bus  Host Controller Driver: AppleUSBXHCIAR        PCI Device ID: 0x15db   ← RP09@1D 配下
  USB 3.1 Bus  Host Controller Driver: AppleIntelCNLUSBXHCI  PCI Device ID: 0x9ded   ← XHC@14
```

`AppleUSBXHCIAR` 配下は 4 ポート（`port` = 1, 2 が HS、3, 4 が SS）で、`UsbConnector`
プロパティは**付いていない**（マップしていないので素のまま）。マップしていない
コントローラは USBToolBox が触らないため、ポートは無効化されず普通に使える。

| ノード名 | `port` | locationID | VID:PID | デバイス | 内蔵/外付 |
|---|---|---|---|---|---|
| HS01 | 1 | 0x14100000 | — | （USB-C、未接続） | 外付 |
| HS02 | 2 | 0x14200000 | 214E:0004 | GesturePoint Mouse Dongle | 外付 |
| HS03 | 3 | 0x14300000 | 05E3:0610 | USB2.1 Hub (Genesys) | 外付 |
| HS06 | **6** | 0x14400000 | **13D3:56D5** | **内蔵カメラ** | 内蔵 |
| HS07 | 7 | 0x14500000 | — | （未使用） | — |
| HS08 | **8** | 0x14600000 | **1532:0239** | **内蔵キーボード + Razer Chroma** | 内蔵 |
| HS09 | 9 | 0x14700000 | — | （未使用） | — |
| HS10 | **10** | 0x14800000 | **8087:0AAA** | **Intel Bluetooth (CNVi)** | 内蔵 |
| SS01 | 13 | 0x14900000 | — | （USB-C、未接続） | 外付 |
| SS02 | 14 | 0x14a00000 | — | （USB-A ①、未接続） | 外付 |
| SS03 | **15** | 0x14b00000 | 05E3:0626 | USB3.1 Hub (Genesys) → 配下に AX88179A (0B95:1790) | 外付 |
| SS04 | 16 | 0x14c00000 | — | （未使用） | — |

#### ★ 訂正: Windows と macOS のポート番号は**一致する**

ここには以前「Windows の HSxx 番号と macOS の PortNum は一致しない。カメラは Windows で
HS06 だが macOS では PortNum 4」と書いてあったが、**間違い**だった。読んでいたのは
`port` ではなく **locationID のニブル**で、あれは macOS が列挙したポートに振り直す
表示用の詰めた連番にすぎない（HS04/HS05 が存在しないので HS06 が 4 番目になる）。

`ioreg` の **`port` プロパティ**を読むと Windows / ACPI `_ADR` と完全に一致する:
カメラ = 6、キーボード = 8、Bluetooth = 10、USB3 ハブ = 15。
DSDT の `Device (RHUB)` 配下も `HS01._ADR = 1` … `HS10._ADR = 0x0A` と名前どおり。

**USB マップに書く番号はこの `port` の体系**で、Windows 側で採取した番号がそのまま使える。

macOS は 18 ポート中 12 ポートだけ列挙する（HS04, HS05, 11, 12, 17, 18 は出ない）ので、
そもそも 15 ポート制限には当たっていない。また `UsbConnector` は既に `_UPC` から
読まれており、**port 1 と 13 だけ `9`（Type-C）、他は全部 `255`（内蔵）**。
つまりマップの実利は「ポート制限の回避」ではなく、**USB-A（2, 3, 14, 15）が内蔵扱い
`255` になっているのを正しい `3` に直すこと**と、未使用の 7 / 9 / 16 を落とすこと。

内蔵は 6 / 8 / 10 の3つで確定。Ethernet は Genesys ハブ経由（root は port 3 / 15）。

### Windows 動作が重い原因（仮想デバイスの山）
Display クラスに実画面以外が2つ、加えて多数の仮想バス:
- Meta Virtual Monitor (`ROOT\DISPLAY\0000`)
- Parsec Virtual Display Adapter (`ROOT\DISPLAY\0001`)
- spacedesk virtual Bus
- Oculus Virtual Gamepad Emulation Bus / Oculus Virtual Audio Device
- NDI Webcam Audio / Video（Webcam 1〜4 の音声エンドポイント4つ）
- NVIDIA Virtual Audio Device
- DCV Virtual Usb Hub, Bome Virtual MIDI, Hyper-V 一式

バッテリー劣化が 2.1% しかないので、**重さはハードウェア劣化ではなくソフトウェア要因**とほぼ断定できる。

## 未解決課題

1. ~~**CNVi WiFi 問題**~~ → **解決**。カード交換は物理的に不可能（CNVio）。AirportItlwm が `0x9df08086` を直接サポートするため、分解・購入ゼロで対応。代償は AirDrop / Handoff / Sidecar が使えないこと（これらは Broadcom チップ固有機能）。**Windows 実測でも確定**: WiFi は `PCI bus 0, device 20, function 3` = PCH 内部、`PARENT: ACPI\PNP0A08\0` でルート直付け、`SUBSYS_00348086`（Razer の `1A58` ではなく Intel）。空いている PCIe ルートポート `RP01`(00:1C.0) の配下は `CHILD: (none - slot empty)`、実際に PCIe バス上にいるのは MX150 / TB3 / NVMe のみ。**WiFi はどの PCIe ポートの下にもいない** → DW1560 等の PCIe カードは電気的に接続できない。同型番でも Intel 9260 / Killer 1550 構成の機体は通常の PCIe M.2 なので交換可能。両者はスペック表上どちらも「Wireless-AC」で区別が付かない。
2. USBMap は macOS インストール後に実施（フェーズ2）
3. ~~`SSDB-OptRef-OptTabl` の `_OFF` 実装詳細~~ → **解決**。`HGOF()` / `RP05.PEGP._OFF()` を `CondRefOf` で呼ぶ SSDT-DGPU-OFF を作成済み。
4. CPUFriend 用データプロバイダは実機 macOS 上で生成（フェーズ2）
5. `_WAK` からの dGPU 再オフ（スリープ復帰後）はフェーズ2。スリープ経路に2つ目のパッチを当てるリスクを避けるため後回し。

## macOS バージョン方針（2026-08 時点の確定事項）

| 項目 | 状況 |
|---|---|
| Intel 対応最後の macOS | **macOS 26 Tahoe**。macOS 27 は Apple Silicon 専用 |
| AirportItlwm の最新ビルド対象 | **Sonoma 14.4**（v2.3.0 / 2024-06 以降 更新なし） |
| → 本機のターゲット | **Sonoma 14.x** で確定。Sequoia/Tahoe に上げると WiFi が死ぬ |
| セキュリティ更新 | Sonoma は 2026年秋頃まで。以後は更新の来ない OS になる |

つまり本機は「Sonoma で完成させて、そこで止める」構成。将来 Tahoe に上げる価値は WiFi を失うため無い。

## ★ 発見 4: バッテリー残量が動かない原因（Reddit 成功報告の未解決問題を特定）

Reddit の成功報告（OpaqueWalrus, 2020-08-10 / 同一機種 i7-8565U Blade Stealth 13 Early 2019）と、
そのコメントで ski_net が「トラックパッドは動いたが **バッテリー残量がどうしても動かない**」と
述べていた問題の原因が、実機 DSDT から特定できた。

### 原因

`\_SB.PCI0.LPCB.EC0` の `Field (ERAM, ByteAcc, ...)` に **16bit 以上のフィールド**が存在し、
`BAT0._BIF` / `BAT0._BST` がそれを直接読んでいる（DSDT 59930行〜, 60359行〜）。

| フィールド | 幅 | 用途 |
|---|---|---|
| `BIF0`〜`BIF8` | **16** | `_BIF`（設計容量・満充電容量・電圧など） |
| `BST0`〜`BST3` | **16** | `_BST`（現在の状態・残量・電圧） |
| `BADN` | 128 | バッテリー名 |
| `ECVR` | 32 | EC バージョン |
| `ECCM` | 256 | シリアル文字列（`ToString(ECCM, 0x20)`） |

macOS の `AppleACPIEC` は **EC を 8bit 単位でしか読めない**。16bit フィールドの読み出しは
失敗するか壊れた値を返すため、`_BIF`/`_BST` が意味のある値を返さず、残量表示が死ぬ。
`PAK1` / `BFB0` の初期値が `0xFFFFFFFF` なので「不明」のまま固まる。

なお `_BIX` は存在しない（`_BIF` のみ）。

### 対策: ECEnabler.kext（DSDT パッチ不要）

**ECEnabler 1.0.6** を採用。EC への 16bit 以上の読み出しを実行時に 8bit へ分割する。
Dortania も明言している通り、これを使えば **旧来ガイドのような EC フィールド分割 DSDT パッチは不要**:

> "you do not need to split EC fields as shown in the guides below"

ski_net は 2020年当時これを知らず（ECEnabler は 2020年後半以降）、
「Razer Blade 2014 用パッチを DSDT に当てる → SSDT ホットパッチが効かなくなる」という
行き詰まりに陥っていた。本構成では DSDT を差し替えないので、その罠には落ちない。

**注意**: Rehabman 系ガイドの `ACPIBatteryManager` ではなく **`SMCBatteryManager`**（VirtualSMC プラグイン）を使う。両方入れてはいけない。既に SMCBatteryManager を採用済み。

## ★ 発見 5: DVMT 32MB 問題は BIOS 改造なしで解決できる

Reddit の投稿者は **BIOS 1.06 を改造して DVMT 64MB** にしていた。
本機の BIOS 1.01 には DVMT の設定項目が存在しない（コメントの Viscel2al も同じ状況で質問している）。
実機レジストリでも `HardwareInformation.MemorySize = 0 0 0 64` (= 32MB 相当の pre-alloc) を確認。

> **2026-08-18 追記**: この節は `AAPL,ig-platform-id = 0x3E9B0000` 時代の記述。
> レイアウトは **`0x3EA50009` / `device-id 0xA53E0000`** に変更済み（理由は発見 10）。
> ただし本節の結論は両方に等しく当てはまる: 要求 STOLEN は同じ 57MB/58MB で、
> `framebuffer-stolenmem` / `framebuffer-fbmem` の値も connector 構成（DP×2）も
> そのまま有効。実機で framebuffer 3個の enumerate を再確認済み。

`0x3E9B0000` フレームバッファは **STOLEN 57MB / TOTAL 58MB** を要求するため、
32MB のままでは WhateverGreen マニュアルの通り **カーネルパニックする**:

> "The absence in BIOS of an option to change the amount of memory for the frame buffer is
> resolved with either semantic `framebuffer-stolenmem` and `framebuffer-fbmem` patches,
> by modifying the BIOS or by manually inputting the values in UEFI Shell.
> **Otherwise you get a panic.**"

→ **BIOS を焼かずに DeviceProperties で解決**（BIOS 3.02 が本機種を壊す事例があるため、
フラッシュは選択肢に入れない）:

```
framebuffer-patch-enable = 01000000
framebuffer-stolenmem    = 00003001   (0x01300000 = 19MB)
framebuffer-fbmem        = 00009000   (0x00900000 =  9MB)
```

これは Dortania の DVMT 32MB ケース向け指定値と完全一致。

### connector-type パッチは不要と判明

`0x3E9B0000` の既定 connector 構成:

| # | busId | pipe | type | 意味 |
|---|---|---|---|---|
| 0 | 0x00 | 8 | 0x00000002 | ConnectorLVDS（内蔵 eDP パネル） |
| 1 | 0x05 | 9 | 0x00000400 | **ConnectorDP** |
| 2 | 0x04 | 10 | 0x00000400 | **ConnectorDP** |

本機の外部出力は USB-C 1 + Thunderbolt 3 1 で **HDMI が無い**ため、既定の DP×2 と完全に一致。
当初計画していた `framebuffer-con1/con2-type = 00040000` は **no-op** なので削除した。

## ★ 発見 6: boot-args の `-igfxblr` は Sonoma では効かない

macOS 13.4 以降、Apple が CFL フレームバッファドライバの `WriteRegister32` を
インライン化したため、旧来の Backlight Registers Fix (`-igfxblr`) は**黙って無効化される**。

→ Sonoma (14.x) では **`-igfxblt`**（WEG 1.6.5+ の alternative fix）を使う。
両方を同時指定してはいけない。これで起動時 3分間ブラックスクリーン問題を防ぐ。

また `igfxonln=1` は「全ディスプレイを常時接続済みと偽装する」機能で、
外部ディスプレイのフリーズ対策ではない（WEG マニュアル未記載、ソースの
`ForceOnlineDisplay` で確認）。有害なので採用しない。

## Reddit 成功報告（同一機種）との対照表

出典: https://www.reddit.com/r/hackintosh/comments/i6w2gk/ (2020-08-10, OpaqueWalrus)

| 項目 | Reddit 報告 | 本構成 |
|---|---|---|
| CPU | i7-8565U | 同一 |
| GPU | UHD 620 / MX150 | 同一 |
| WiFi | Intel AC 9560 → itlwm で動作 | **AirportItlwm**（IO80211、ネイティブ WiFi UI） |
| BIOS | **1.06 を改造して DVMT 64MB** | **1.01 のまま。stolenmem/fbmem で回避** |
| OpenCore | 0.6.0 | **1.0.7** |
| オーディオ | AppleALC **layout-id=30** で完璧 | 同じ 30 を採用 |
| トラックパッド | VoodooI2C + VoodooHID、force touch 無効化が必要 | VoodooI2C + **VoodooI2CHID** |
| タッチスクリーン | VoodooI2C でそのまま動作 | **本機にタッチスクリーンは無い**（実機確認済み） |
| DSDT | 差し替え（dsdt.aml を配置） | **差し替えない**（SSDT ホットパッチのみ） |
| **スリープ** | **未解決**（画面が壊れて再起動が必要） | **RWAK LIDS パッチで対策**（0x16796、一意性検証済み） |
| **外部ディスプレイ** | **未解決**（接続でフリーズ） | **解決**（左 USB-C で 1920x1080@60、フリーズなし。発見 23） |
| **バッテリー残量** | ski_net が未解決 | **ECEnabler で解決**（16bit EC フィールドが原因と特定） |
| SMBIOS | — | **MacBookPro15,2**（ski_net が「15,2 でのみスリープした。15,4 と 16,3 は駄目」と報告） |

## ★ 発見 7: リカバリは 14.6.1 で、AirportItlwm の対応上限を超える

`macrecovery.py -b Mac-827FAC58A8FDFA22`（Sonoma のボード ID）が返すのは
**14.6.1 (23G93)**。取得済みイメージの `SystemVersion.plist` で確認した。

一方 AirportItlwm は `IO80211Family` の非公開 API に直接リンクするため、
OS のマイナーバージョンごとにビルドが切られている。GitHub API で確認した現状:

| リリース | 日付 | Sonoma 向け |
|---|---|---|
| **v2.3.0** | 2024-06-09 | **14.0 と 14.4 のみ** |
| v2.2.0 | 2023-05-31 | なし（Ventura まで） |

**14.5 / 14.6 向けビルドは存在せず、2年以上更新がない。**
14.4 向けバイナリが 14.6.1 でロードできる保証はない。

### 対策: itlwm.kext を無効状態で同梱（二段構え）

`itlwm.kext` は `IO80211Family` を経由せず、カードを**イーサネットとして見せる**方式。
`LSMinimumSystemVersion = 10.9` で、**OS バージョン依存がほぼない**。

- 通常は `AirportItlwm.kext` を使う（ネイティブ WiFi UI が使える）
- ロードに失敗したら config.plist で `AirportItlwm` を無効化し `itlwm` を有効化
- 操作は **HeliPort**（メニューバーアプリ）から行う
- **両方を同時に有効にしてはいけない**（同一 PCI デバイスを取り合う）

config.plist には `itlwm.kext` が `Enabled=false` で入っている（16 個目のエントリ）。

⚠ **`itlwm.kext` の `IOPCIPrimaryMatch` は `0x00008086&0x0000ffff`**（= Intel の全 PCI
デバイスに広くマッチ）で、`AirportItlwm` のような個別 device-id リストを持たない。
`9df0` を名指ししていないのは正常で、非対応ではない。

⚠ `itlwm.kext` の Info.plist には**作者のテスト用 SSID とパスワードが `WiFiConfig`
として残っている**（`ssdt` / `Redmi` など）。動作に影響はないが、有効化して使う場合は
自分の SSID を書くか空にしておく。

### 第三者による実機での裏付け（Reddit r/hackintosh `i6w2gk`, 2020-08-10）

`OpaqueWalrus` が **Blade Stealth 13 Early 2019 / i7-8565U / Intel AC 9560** で成功報告。
`Clippings/Success Razer Blade Stealth 2019 w Intel Wifi!.md` に保存済み。

**カード交換はしていない。`itlwm.kext` で 9560 をそのまま動かしている。**

> "Wifi thanks to **Itlwm.kext** :)"
> "It is working great the speeds aren't ideal (**Only 20Mbps**) but **it's much easier
> than replacing the Wifi card** or using USB"

一致した点（こちらの構成の裏付けになる）:

| 項目 | 向こう | こちら |
|---|---|---|
| オーディオ | AppleALC + **`layout-id=30`** | boot-args `alcid=30` ✅ |
| SMBIOS | `ski_net`「**`MacBookPro15,2` でしかスリープしない**。15,4 / 16,3 は不可」 | `MacBookPro15,2` ✅ |
| トラックパッド | VoodooI2C + VoodooHID（force touch 無効化に DSDT パッチ） | VoodooI2C + VoodooI2CHID ✅ |
| タッチスクリーン | VoodooI2C で「right off the bat」 | 同 ✅ |
| kext の読ませ方 | OpenCore の通常 kext で OK | 同 ✅ |
| MX150 | 動かない | 前提済み ✅ |
| itlwm はイーサネットに見える | 「**intended**。HeliPort を使え」 | 二段構えの後段そのもの ✅ |

**このスレッドに「Blade Stealth 2019 でカード交換に成功した」報告は一件もない。**
交換を薦めた `sk9592` は ASUS の**デスクトップ**マザーの話（CNVi ではない）。
スレッド中で「**pin configuration looks different than 9560. Is it still gonna work?**」
と質問した人がいるが**誰も答えていない** → CNVi だから。本人も AirDrop は諦めている。

⚠ **相違点: 向こうは BIOS 1.06 を改造して DVMT を 64MB にしている。**
こちらは BIOS 1.01 のまま触らない（3.02 で起動不能報告あり）。代わりに
WhateverGreen の `framebuffer-stolenmem = <00003001>`(19MB) / `framebuffer-fbmem =
<00009000>`(9MB) で回避する。これが BIOS 改造の代替。2023 年に別の人が
「自分の BIOS に DVMT 設定がない」と質問して回答が付いていない箇所への答えでもある。

**向こうが 6 年解けていない課題（誰も回答なし）:**
- スリープ復帰で画面が壊れて再起動が必要 → **こちらは `RWAK` offset `0x16796` を特定済み**（発見 2）。おそらく同じ原因
- 外部ディスプレイを挿すとフリーズ → **こちらでは起きない**（発見 23、実機で拡張デスクトップ動作）

## ★ 発見 8: USB インストーラは 2GB で足りる

Apple Silicon の Mac では `createinstallmedia` が使えない（Intel 用インストーラを
実行できない）ため、`macrecovery.py` 方式が唯一の選択肢。この方式の必要容量:

| 内容 | サイズ |
|---|---|
| `com.apple.recovery.boot/BaseSystem.dmg` | 753 MB |
| `com.apple.recovery.boot/BaseSystem.chunklist` | 3 KB |
| `EFI/`（OpenCore + kext 16 個） | 59 MB |
| **合計** | **812 MB** |

一般ガイドの「16GB 以上」は `createinstallmedia` でフルインストーラ（13GB）を
書く場合の話で、本方式には当てはまらない。**2GB あれば十分**。

代償として、インストーラ起動後に Apple のサーバーから本体をダウンロードするため
**ネット接続が必要**。WiFi が動かない場合は USB-C 有線 LAN アダプタが保険になる。

### Windows インストールメディアとの同居は不可

手持ちの 62.9GB USB は Windows インストールメディア（`ESD-USB`, Dec 2023, 4.6GB 使用）
だった。27GB 空いているが**同居できない**:

```
/efi/boot/bootx64.efi    ← Windows インストーラの起動ファイル
/EFI/BOOT/BOOTx64.efi    ← OpenCore の起動ファイル
```

FAT32 は大文字小文字を区別しないので**同一ファイル**。上書きすると Windows
インストーラが起動しなくなる。MBR (`FDisk_partition_scheme`) なので
`diskutil addPartition`（GPT 専用）も使えない。

→ **別の USB メモリを使う。** Windows メディアは `ntfsresize` 失敗時の唯一の
復旧手段なので保全する（外付けバックアップドライブが無いため）。

### 作成済み USB（2026-08-16 20:45）

2本目の USB（62.9GB, ProductCode）を `bin/mkusb disk15` で作成した。

| 項目 | 値 |
|---|---|
| パーティション | FAT32 / **MBR** / ラベル `OPENCORE` |
| `EFI/` | 実 59MB（`du` では 72MB = FAT32 の 32KB クラスタ丸め） |
| `com.apple.recovery.boot/` | 753MB |
| 使用量 | 829MB / 59GiB |
| 必須5ファイル検証 | すべて ok |

書き込み前に中身（作業資料と資格情報ファイル）を
`backup/usb15-20260816-2030/` へ退避（76 → 76 ファイル一致で検証済み）。
**このバックアップには API キー / パスワードのファイルが含まれるので中身を開かない。**

`disk14`（`ESD-USB` = Windows インストールメディア, Dec 2023）は無変更で保全。

## NTFS と APFS の同居について（2026-08-16 検討）

GPT は区画ごとにファイルシステムが独立しているので同居は問題ない。
実機はすでに 3 種類（NTFS / FAT32 / MSR）が同居している。目標の形:

```
disk0 (930.4GB, GPT)
 ├ 1  Recovery  0.10GB
 ├ 2  ESP       0.10GB  FAT32   ← Windows Boot Manager（残り 63.26MB のみ）
 ├ 3  MSR       0.02GB
 ├ 4  C:        550GB   NTFS    ← 縮める
 ├ 6  ESP#2     0.20GB  FAT32   ← OpenCore 専用（新規）
 ├ 7  macOS     300GB   APFS    ← 新規
 └ 5  WinRE     0.89GB          ← ディスク末尾にあるので空きは 4 と 5 の間にできる
```

ESP を 2 つ作る理由: 既存 ESP は 96MB で空きが **63.26MB**。
OpenCore の EFI は 59MB なので数字上は入るが余裕 4MB しかなく、
OC 更新 / kext 追加 / Windows Update の Boot Manager 書き換えで溢れる。
**ESP が溢れると Windows も macOS も起動しなくなる**ので削らない。
GPT は同一タイプ GUID の ESP を複数持てて、ファームウェアは両方をスキャンする。

### 同居で気をつけること

| 項目 | 内容 |
|---|---|
| macOS → NTFS | **読めるが書けない**（標準は読み取り専用マウント） |
| Windows → APFS | **見えない**。ディスクの管理で「不明な領域」= 誤って削除できる |
| 休止 / 高速スタートアップ | **無効を維持**。有効だと Windows がディスクをロックしたまま寝て、macOS からマウントすると NTFS が壊れる。Windows Update で復活することがあるので定期確認 |

同居自体にリスクは無い。危険なのは**そこに至る C: の縮小操作**（`ntfsresize`）だけ。

### exFAT 共有パーティションは作らない（方針変更）

当初 80GB の exFAT 共有領域を計画したが、外した。

**exFAT はジャーナルを持たない。** NTFS はメタデータジャーナル、APFS はコピーオンライト
で中間状態が残らないが、exFAT はディレクトリエントリと割り当てビットマップを直接上書き
する。書き込み中に落ちると 1 ファイルの事故がディレクトリ構造ごと壊す。

ただし破損報告の大半は**リムーバブルメディアを書き込み中に抜いた**ケースで、
内蔵パーティション（抜けない / バッテリーがある / 高速スタートアップ無効）なら
リスクは桁違いに低い。それでも NTFS・APFS より弱いことは変わらない。

機能不足由来の実害もある:
- シンボリックリンクと POSIX パーミッションが無い → **git チェックアウト / `node_modules` / Xcode ビルドが壊れる**
- 80GB ボリュームだと macOS はクラスタを 128KB で作る → 小さいファイルが大量にあると激しく無駄

**代替（ファイルシステムを増やさない）:**

| 方向 | 手段 | リスク |
|---|---|---|
| Windows → macOS | 不要。macOS は NTFS を標準で読める | ゼロ |
| macOS → Windows | **Mac mini の SMB 共有**（同一 LAN にいる） | ゼロ |
| 直接受け渡したい場合 | Paragon NTFS for Mac（有料・約4千円） | 低 |

**そして後から追加できるので今決めなくてよい。**
C: の NTFS と違い **APFS はマウントしたまま安全に縮小できる**:

```
diskutil apfs resizeContainer disk0sN 250G
```

→ まず macOS を 300GB で入れ、実際に不便なら後で縮めて exFAT を作る。
NTFS のような「縮められない」詰みは APFS では起きない。

## ★ 発見 9: C: は Windows 標準ツールでは 7.44GB しか縮小できない

空き容量を 122.77GB → 437.27GB（314.5GB 回収）まで増やしたが、
**縮小可能サイズは 7.44GB から 1 バイトも動かなかった。**

原因はイベントログ (Application, Event ID 259) が明示していた:

```
The last unmovable file appears to be: \$Mft::$BITMAP
The last cluster of the file is: 0xe6bab88      = 922.92 GB 地点
Shrink potential target (LCN address): 0x7b4874c = 494.6 GB 地点
NTFS file flags: -S--S                           (S = System)
```

Windows は「494.6GB まで縮めたい」と判断しているが、922.92GB 地点の
`$Mft::$BITMAP` に阻まれて 7.44GB で妥協している。

### MFT を縮める手段は存在しない（調査結論）

| 事実 | 根拠 |
|---|---|
| NTFS は設計上 MFT を縮小しない | ファイル削除で MFT レコードは再利用されるだけ。Microsoft は縮小 API を提供していない |
| `$Mft::$BITMAP` はマウント中は移動不可 | NTFS フラグ `-S--S` の System 属性 |
| MFT 本体は無関係 | `Mft Start Lcn = 0x000c0000` = **3.0GB 地点**。末尾にあるのは `$BITMAP` 属性の断片のみ |
| デフラグは無効 | `defrag /X` 実行後も 7.44GB のまま。`Optimize-Volume -ReTrim` でも変化なし |
| サードパーティ製ツールも不可 | MFT を移動する機能を持つものは存在しない |

**→ 内蔵 SSD を分割するには GParted Live の `ntfsresize` が必要**（アンマウント状態で
NTFS 構造を外部から再構築できる唯一の手段）。

### デフラグと SSD 寿命について

`defrag /X` は書き込みを伴うが、実害はない:
- Samsung 970 EVO 1TB の耐久値は **600 TBW**
- 今回の実行は 2 分で完了 → 書き込み量は数 GB 程度
- 100GB 書いたとしても 600TBW の **0.017%**

ただし**効果がゼロだったので、今後デフラグは実行しない。**
`Optimize-Volume -ReTrim` は書き込みを伴わない TRIM なので無害（211.48GB 解放）。

## 容量回収について（実測内容は非公開）

macOS 用に 600GB 超を空ける必要があったため C: の棚卸しと削除を行った。
個々の内容は個人データなので公開版では省略する。他の機種でも使える知見だけ残す:

| 見落としやすい回収先 | メモ |
|---|---|
| DeliveryOptimization キャッシュ | `C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization`。**`ProgramData` 配下ではない**ので探しても見つからない |
| DISM WinSxS クリーンアップ | `Dism /Online /Cleanup-Image /StartComponentCleanup /ResetBase`。所要 6 分程度 |
| WSL2 `ext4.vhdx` | Linux 内で `fstrim -av` → `diskpart` の `compact vdisk`。Linux 側は無傷。半分近く縮む |
| pagefile 一時退避 | 縮小作業中だけ無効化する場合、終わったら **`AutomaticManagedPagefile = True` に戻す** |
| シャドウコピー | `vssadmin delete shadows`。復元ポイントを捨てる判断が必要 |
| `%TEMP%` | 7 日以上前のものだけ消す。**全消しすると実行中の SSH セッションが死ぬ** |

**ジャンクションの罠**: `C:\Users\<user>` 配下の XP 時代の互換名は
`LinkType = Junction` なので、素朴に集計すると二重計上になる。

| 見かけ | 実体 |
|---|---|
| `My Documents` | → `Documents` |
| `Local Settings` | → `AppData\Local` |
| `Application Data` | → `AppData\Roaming` |

`C:\Documents and Settings` も同種（後述）。

## バックアップ方式の選択: ファイル単位ではなくイメージ

C: のファイル構成を実測したところ、所要時間は**容量ではなくファイル数が支配的**だった。
実機は約 130 万ファイル / 平均 352KB で、**95.5% が 1MB 未満**（なのに容量では 11% だけ）。
小さいファイルの山はシーク待ちがそのまま時間になる。

| 方式 | 律速 | HDD (120MB/s) | SATA SSD (450MB/s) |
|---|---|---|---|
| ファイル単位コピー (robocopy 等) | **ファイル数**（100〜200 files/s） | **3.5〜5 時間** | 40 分〜1 時間 |
| **セクタ単位イメージ**（使用領域のみ） | 帯域のみ | **約 45 分**（316GB 時） | **約 12 分** |

→ **イメージバックアップを使う。** 130 万ファイルのシーク待ちが消え、
復元も丸ごと戻せるのでパーティション操作の備えとして適切。
AOMEI 同梱 / Macrium Reflect Free / Clonezilla のいずれでも可。
退避先は同価格帯なら **SSD 推奨**（速い / 動作中の衝撃に強い /
バスパワーでリンク切れしない）。

## AOMEI Partition Assistant について（実機に既存）

実機に **AOMEI Partition Assistant 9.15.0** が既にインストールされていた
（ライセンス情報が空なので Standard = 無料版と推定。無料版でも
「パーティションのサイズ変更/移動」は使える）。

同梱バイナリに `AMBooter.exe` / `PeLoadDrv.exe` / `loaddrv.exe` があり、
**再起動して Windows 起動前の PreOS 環境で自前 NTFS ドライバをロードする**方式と確認できた。

| | ディスクの管理 | AOMEI / GParted |
|---|---|---|
| 実行環境 | マウント中のボリューム | **アンマウント状態** |
| 使う手段 | OS の `FSCTL_SHRINK_VOLUME` | 自前 NTFS ドライバ |
| `$Mft::$BITMAP` | **動かせない → 7.44GB で降参** | 再配置できる |

**つまり AOMEI は「安全な回避策」ではなく、`ntfsresize` と原理的に同じことを
別の皮で提供しているもの。成功率は上がるが、失敗確率はゼロではなく
失敗時の損失も同じ。バックアップは省略できない。**

実利はある:

| | GParted Live | AOMEI |
|---|---|---|
| 準備 | USB を作って起動 | Windows 上で予約 → 自動再起動 |
| WinRE / MSR / BCD | 汎用ツールなので認識しない | **認識して整合性を保つ** |
| 中断時 | 手作業で復旧 | ロールバック機構あり |

実機の **WinRE はディスク末尾（パーティション 5）** にあるため、C: を縮めると
その手前に空きができる。BCD の参照を壊さない AOMEI のほうが有利。

**制約: `PartAssist.exe` は `/?` に応答しない GUI 専用バイナリで、CLI 操作は不可。
RDP も無効（`fDenyTSConnections = 1`、Win11 Home では有効化困難）。
→ AOMEI の操作だけは実機の前で手作業になる。**

### ★ 検証結果: AOMEI は 7.44GB の壁を越える（2026-08-16、書き込みゼロで確認）

AOMEI の「パーティションのサイズ変更/移動」ダイアログを開いて数値を読むだけの検証を実施。
**スライダーを動かしても「適用」を押すまで何も書き込まれない**ので、リスクなしで判定できた。

| ツール | C: 930.4GB からの縮小可能サイズ |
|---|---|
| Windows ディスクの管理 (`FSCTL_SHRINK_VOLUME`) | **7.44 GB** |
| **AOMEI Partition Assistant 9.15.0** | **558.78 GB** |

ダイアログの表示:
```
サイズ            : 371.62GB    ← 下限
前の未割り当て領域 : 0.00KB      ← 開始位置は動かない（狙い通り）
後の未割り当て領域 : 558.78GB
「このパーティションを移動したい」: チェックなし
```

**75 倍の差。`$Mft::$BITMAP` は AOMEI で再配置できる → 案A（内蔵分割）が実行可能。**

確認後 × で閉じ、パーティションテーブルが無変更であることを検証済み
（`#4 offset 0.212GB / size 930.403GB` のまま）。

**注意: 「前の未割り当て領域」は必ず 0 のままにする。**
C: の開始位置 0.212GB を動かすと NTFS の全データを物理移動することになり、
309GB の読み書きで数時間かかる上、その間ずっと中断リスクを抱える。
後ろを削るだけなら移動は最小限。

### 決定した配分: C: = 400GB（ユーザー判断）

**方針: macOS を中心に使う。** ムービーを今後さらに削る予定があるため C: は 400GB で確定。

```
disk0 (931.51GB, GPT)
 ├ 1  RazerRecPar   100 MB           Razer 工場ツール領域（空き 92.19MB でほぼ空）
 ├ 2  ESP           100 MB   FAT32   Windows Boot Manager（空き 63.26MB）
 ├ 3  MSR            16 MB           Microsoft 予約、FS なし
 ├ 4  C:            400 GB   NTFS    使用 308.34GB
 ├ 6  ESP#2         200 MB   FAT32   OpenCore（新規）
 ├ 7  macOS         530 GB   APFS    新規
 └ 5  WinRE         916 MB           ディスク末尾。触らない
```

400GB の妥当性（使用 308.34GB に対して）:

| 項目 | 容量 |
|---|---|
| 使用量 | 308.34 GB |
| pagefile（RAM 15.9GB の自動管理） | 最大 16 GB |
| System Restore 上限（設定済み） | 10 GB |
| Windows Update 作業領域 | 10〜20 GB |
| **合計** | **約 354 GB** |
| **余裕** | **約 46 GB**（400GB の 11.5%） |

Windows は空きが 10% を切ると挙動が怪しくなるので、ぎりぎり上。
ムービーを削ればそのまま余裕が増える方向なので問題ない。
AOMEI が示した下限 371.62GB は余裕 63GB しかなく採用しない。

### パーティション5 = WinRE（916MB、消してはいけない）

```
Windows RE status   : Enabled
Windows RE location : \\?\GLOBALROOT\device\harddisk0\partition5\Recovery\WindowsRE
Windows RE Version  : 10.0.26100.9168
BCD identifier      : cdbbd6fe-7023-11f0-b90d-ea45d06ef8f8
GptType             : {de94bba4-06d1-4d40-a16a-bfd50179d6ac}
```

「スタートアップ修復」「このPCを初期状態に戻す」「詳細オプションからのブート」の実体。
**パーティション操作が失敗したとき最初に頼る場所**なので保全する。
ディスク末尾（offset 930.615GB）にあるので、C: を後ろから削るだけなら影響しない。

なおパーティション1の `RazerRecPar`（100MB）は GptType が Recovery だが WinRE ではなく
Razer の工場出荷時ツール領域。

### 大容量メディアファイルの棚卸し（内容は非公開）

200MB 超のメディア／アーカイブを一覧して個別に判断した。中身は個人データなので
公開版では省略する。手順だけ:

```powershell
Get-ChildItem "$env:USERPROFILE" -Recurse -File -EA SilentlyContinue |
  Where-Object { $_.Length -gt 200MB } |
  Sort-Object Length -Descending |
  Select-Object @{n='GB';e={[math]::Round($_.Length/1GB,2)}}, FullName |
  Out-File "$env:USERPROFILE\Desktop\media-files.txt"
```

再ダウンロード可能なインストーラ／キャッシュ類（各種アプリの InstallerCache 等）は
迷わず消せるので、まずそこから当たると判断が早い。

### バックアップ実施状況（2026-08-17 時点）

**完了:**

| 項目 | 内容 |
|---|---|
| ディスクイメージ | AOMEI の `.adi` = **157.5GB**（251GB を 63% に圧縮）。外付け HDD 上 |
| BCD バックアップ | `bcdedit /export` で 24KB |
| 退避先 | 4TB / exFAT / USB 接続の外付け HDD |

**未完了: 復元環境の起動経路。** これが無いとイメージがあっても開けない。

### AOMEI Backupper 6.4.0 の RecoveryEnv は Windows 11 で動かない

`RecoveryEnv.exe`（回復環境をブートメニューに組み込む機能）が **5 回連続で同一箇所で落ちる**。
ログ `RecoveryEnv0..4.txt` はすべて次の 2 行で途切れる（エラー記録なし = 例外で即死）:

```
[2026-08-17 00:37:11] :sys par  is C:
[2026-08-17 00:37:11] :createfilew argument is \\.\C:
```

`CreateFileW("\\.\C:")` = C: を raw デバイスとして開く呼び出しで死んでいる。原因はログ冒頭:

```
Product Name : Windows 10 Home (10.0.9200.2)
OS Build Name: 26200.9168
OS Version   : 10.0.9200.9168
```

**6.4.0（2020 年版）が OS を「Windows 10 / build 9200」と誤認している。**
実機は Windows 11 build 26200。`9200` は Windows 8 の番号で、
マニフェストに新 OS 対応が無い古いアプリが返す互換値。
→ **6.4.0 は現行 Windows 11 世代に対応していない。同じ版で再試行しても無意味。**

`C:\AOMEI\AomeiBoot.wim`(723.4MB, 2023-04-09) / `AomeiBoot.sdi`(3.02MB, 2019-12-07) は
置かれているが、**日付がインストーラ同梱物のままで今日生成されたものではない**。
`bcdedit /enum all` に AOMEI のエントリは一切無く（WinRE のみ）、起動経路が存在しない。
中身の正しさが保証できないため手動 `bcdedit` 登録はしない。

### 復元経路: AOMEI に頼らない代替（USB 追加なしで成立）

守るべきは 250GB のデータで、`.adi` はその手段にすぎない。次の経路が既に確保できている:

```
縮小失敗 → Windows 起動不可
  ① disk14（Windows インストールメディア）から起動 → スタートアップ修復
      BCD 破損程度ならここで直る
  ② 直らなければ Windows を再インストール（C: 400GB のまま）
  ③ AOMEI Backupper 最新版を入れて .adi をマウントしてファイルを取り出す
```

**「45 分で丸ごと元通り」は失うが「データが消える」は防げる。差は手間だけ。**
`.adi` は「イメージを探索」機能でマウントしてエクスプローラから読める。

推奨は **AOMEI Backupper を最新版（7.4.x, Windows 11 24H2 対応）へ入れ替えて再試行**、
それでも駄目なら上記の代替経路で進める。

## ★★ 縮小成功（2026-08-17 07:29 完了）

**AOMEI Partition Assistant 9.15.0 で C: を 930.403GB → 350.006GB に縮小。成功。**
Windows 標準ツールの上限 7.44GB に対し、**580.4GB を確保**（78 倍）。

### 結果

```
disk0 (931.51GB, GPT)
 ├ 1  RazerRecPar    98 MB
 ├ 2  ESP            98 MB   FAT32   使用 32.74MB / 空き 63.26MB（無変更）
 ├ 3  MSR            16 MB
 ├ 4  C:            350 GB   NTFS    offset 0.212GB（無変更）/ 使用 258.04 / 空き 91.97 (26.3%)
 │    ───────  未割り当て 580.4 GB  ───────   ★macOS 用
 └ 5  WinRE         895 MB   offset 930.615GB（無変更）
```

当初計画は 400GB だったが実際には **350GB** を指定。使用 258.04GB に対して空き 91.97GB
（26.3%）あり、pagefile 16GB + System Restore 10GB + Update 作業領域 20GB を引いても
46GB 残るので問題なし。macOS に 580GB 渡せるので「Mac 中心」の方針にはむしろ好都合。

### 縮小後の検証（全項目クリア）

| 項目 | 結果 |
|---|---|
| `chkdsk C:` | ✅ **found no problems** / **bad sectors 0 KB** |
| **`Mft Start Lcn`** | ✅ **`0x000c0000` = 3.0GB 地点。`$BITMAP` も 350GB 以内に再配置された** |
| `Mft Valid Data Length` | 3.77 GB |
| C: HealthStatus | ✅ Healthy |
| WinRE | ✅ Enabled / partition5 / 10.0.26100.9168 |
| BCD / Windows Boot Manager | ✅ `\EFI\MICROSOFT\BOOT\BOOTMGFW.EFI` 正常 |
| ESP | ✅ 32.74MB / 63.26MB（無変更） |
| `AutomaticManagedPagefile` | ✅ True（`pagefile.sys` 9.5GB） |
| System Restore | ✅ 上限 10.0GB |
| 起動時エラー | Google Update / PRI-Driver / Hyper-V VmSwitch — **すべて縮小と無関係の既存問題** |

### 所要時間

**約 1 時間**（開始 01:15 頃 → 完了 07:29 の間。PreOS 実行中は
ASIX USB-GbE のドライバが無いため ARP に応答せず `(incomplete)` になる = 正常）。

`$MFT` / `$BITMAP` の再配置は進捗表示の更新が粗く、止まって見える区間がある。
**ネットワークからは PreOS 実行中と電源断を区別できない**ので、判断は実機の画面で行う。

### 事前準備（実際に効いたもの）

| 項目 | 備考 |
|---|---|
| `.adi` イメージ 157.5GB | 外付け HDD 上 |
| BCD バックアップ 24KB | `bcdedit /export` の出力 |
| **`chkdsk` で事前に NTFS を修復** | **縮小直前のチェックで `found problems` を検出。`chkdsk C: /scan` がオンライン修復し `found no problems` を確認してから実行した。壊れた NTFS のまま `$MFT` を動かすのは危険なので、この手順は必須** |
| AC 電源 97% | |
| BitLocker 復号済み / 高速スタートアップ・休止 無効 | |

### ESP#2 作成完了（2026-08-17）

**ESP#2 は Windows の `diskpart` で作った。** `create partition efi` が正規のタイプ GUID
`c12a7328-f81f-11d2-ba4b-00a0c93ec93b` を自動で設定するため。macOS のディスクユーティリティで
「MS-DOS (FAT)」を作ると **Microsoft Basic Data (`ebd0a0a2-...`)** になり、
**ファームウェアが ESP として認識しない**（後から `gdisk` で `EF00` に直す手間が出る）。

```
 6  System  OCESP  off=376,044,519,424  size=209,715,200 (200MiB)  FAT32  空き 196MB
```

C: の直後・WinRE の手前。既存パーティションは 1 バイトも動いていない。

**注意: diskpart は Hidden 属性の ESP をフォーマットできない**（`format quick fs=fat32` が
`The device is in use.` で失敗する）。PowerShell の `Format-Volume` を使う。
`assign letter` も同じ理由で効かないが、EFI のコピーは macOS から `diskutil mount` で
行うので不要。

### 残りの未割り当て 580.20GB

**Windows 側では一切フォーマットしない。** macOS インストーラのディスクユーティリティで
「パーティション作成」（消去ではない）を使って APFS を作る。Windows で exFAT/NTFS にすると
余計なボリューム情報が残る。

以降の手順は **`docs/install-runbook.md`** に集約した。

### 適用前に必須の手順

「適用」を押すと PreOS 環境で `$MFT` / `$BITMAP` の再配置と 923GB 地点のデータ移動が走る。
**中断すれば 309.48GB が失われる**（ロールバック機構はあるがメタデータ書き換え中は救えないことがある）。

1. 500GB 以上の外付けドライブを用意（約6千円）
2. **イメージバックアップ**取得（309.48GB → HDD 約45分 / SSD 約12分）
3. **復元メディアの作成** ← イメージだけでは戻せないので必須
4. AOMEI で C: を 550GB に縮小 → 適用 → 自動再起動
5. Windows が正常起動するか確認
6. ESP#2 + macOS 領域を作成
7. OpenCore USB から macOS インストール

### 電源についての注意

検証開始時、実機は **バッテリー駆動 43%** だった。パーティション操作時は AC 必須。
（検証後に AC 接続を確認: `BatteryStatus = 2`）

### Mac mini は退避先にできない

Mac mini の空きは **129GB** しかない（`/System/Volumes/Data` 304Gi 使用 / 129Gi 空き）。
316GB を受けられないので、外付けドライブを Razer に直接 USB 接続する。
なお Razer 側の有線 LAN は ASIX USB-GbE で 1Gbps リンク済み。

### 測定時の罠: `C:\Documents and Settings`

トップレベルのサイズ集計で **336.93GB** と出るが、これは
`C:\Users` への**ジャンクション**（`LinkType = Junction`, `Target = C:\Users`）。
二重計上なので除外して読む必要がある。実体は `C:\Users\<user>` の 335.2GB。

### 削除してはいけないもの（調査して除外した）

| パス | サイズ | 理由 |
|---|---|---|
| `AppData\Local\Microsoft\OneDrive\26.134.0713.0007` | 0.56 GB | OneDrive **本体のプログラムファイル**。キャッシュではない |
| `AppData\Local\Microsoft\Office\SolutionPackages` | 0.45 GB | Office アドインの実体 |
| ノートアプリのローカル「バックアップ」世代 | — | クラウド未同期のローカル専用ノートがあれば唯一のコピー |

itlwm の速度について: 2020年時点の報告は 20Mbps（802.11n 相当）。
その後 v1.1.0 以降で 802.11ac に対応済みなので、現在の AirportItlwm 2.3.0 では改善している。
ただし **AirDrop / Handoff / Sidecar は Broadcom チップ固有機能なので使えない**（Reddit でも
「airdrop が欲しければ BCM94360NG に交換」という流れになっているが、本機は CNVi のため交換不可）。

## ★★ 発見 10: ディスプレイスリープ後の黒画面は eDP リンクトレーニング失敗だった（2026-08-18 解決）

### 症状

macOS は正常に起動して画面も出る。しかし **一度でもディスプレイが DPMS off になると
（`pmset displaysleepnow`、アイドルタイムアウト、あるいはホットコーナーの Display Sleep）
二度と画面が戻らない**。ユーザーは右上ホットコーナーに Display Sleep を割り当てていたため、
これを頻繁に踏んでいた。

ユーザーによる 3点の物理観察が、探索空間を一撃で潰した:

| 観察 | 排除できるもの |
|---|---|
| 懐中電灯で照らしても**何も見えない** | バックライト系すべて（PWM、PNLF、`-igfxblt`、`max-backlight-freq`）。バックライト故障なら「暗いが見える」になる |
| 輝度キーを押しても戻らない | 同上 |
| 蓋を閉じて開けても戻らない | 「再接続で治る」系のワークアラウンド全部。lid open は再トレーニングを走らせるが、それが失敗しているので無意味 |

つまり **画像信号そのものが出ていない**。バックライトではなく **リンク**の問題。

### 決定的トレース（失敗時、`AAPL,ig-platform-id = 0x3E9B0000`）

```
Panel power ON time was 228 ms        <- パネルには通電している
PP_STATUS=0x80000008
SetupOptimalLaneCount LaneCount=2 BitRate=0xa
SetupDPTimings pixelClock=138500000 linkSymbolClock=270000000
EnableClocks:12937 PLL successfully enabled
ConfigureBufferTranslation: BT: Using eDP eye   <- ここでレイアウト由来の電気パラメータを使う
Clock Recovery Initated, Retry Count = 0..7     <- 8回
IG:: LinkTraining:932 HW strength setting=0x0 -> 0x4 -> 0x87
[Link_Training] (request01=0 -> 0x11 -> 0x22 -> 0x33) Voltage=0 -> 3
[Link_Training] laneMask=0xff, laneStatus=0     <- 毎回 0
dpAuxChRead/Write ... Status:0                  <- AUX は全部成功
[WARNING] Failed Phase 1 of Link Training
[ERROR  ] Link training failed - notifying AGDC to take display offline
[ERROR  ] [AGDC] AGDC not registered. Unmanaged display
[ERROR  ] [Modeset] Not successful. Disabling display
```

読み方:

- **AUX は完全に正常**。全トランザクションが `Status:0`（成功）で、シンク側が
  ADJUST_REQUEST（`request01`）に「もっと振幅を上げろ」と書き込んできている。
  つまりパネルは通電済み・アドレス可能・会話可能。当初「AUX が壊れている」と疑ったが外れ。
- にもかかわらず **`laneStatus=0`**、すなわち CR_DONE が一度も立たない。ドライバは電圧を
  0→3、HW strength を 0→0x87 まで上げ切っても駄目。
- **電気的パラメータが panel に合っていない**ことを示す典型的な形。

### 根本原因: フレームバッファレイアウトが間違っていた

WhateverGreen `FAQ.IntelHD` の記載:

> Recommended framebuffers:
> Desktop: `0x3EA50000` (default), `0x3E9B0007` (recommended)
> **Laptop: `0x3EA50009` (default)**

> For UHD620 (**Whiskey Lake**) fake `device-id` **`A53E0000`** for `IGPU`.

本構成は `0x3E9B0000` + `device-id 0x3E9B` で動いていた。これは
**2つの異なるレシピの片方ずつを混ぜたもの**。

（訂正: 当初「`0x3E9B0000` はデスクトップ用レイアウト」「末尾 0000 系はデスクトップ」と
書いたが、これは誤り。FAQ の CFL/CML 表では `0x3E9B0000` は **mobile / 3 connector / 58MB**
と明記されている。欠陥は「デスクトップ用だった」ことではなく、
**laptop default ではないこと**、および `0x3E9B` が Whiskey Lake の
正規の fake device-id ではないことである。）

`ConfigureBufferTranslation: BT: Using eDP eye` が、この
レイアウトから eDP のアイパターン（電圧スイング / プリエンファシスのテーブル）を
取り出す。そこが間違っていたので、どの rate でもどの電圧でもリンクが張れなかった。

### 修正と確認（`0x3EA50009` + `device-id 0xA53E0000`）

> **大幅改善だが完全修復ではない。この節は必ず次の「時間依存性」節まで読むこと。**
> この節は当初「4/4 で成功、CONFIRMED FIXED」と書いていたが、その4サイクルは
> すべて消灯時間 **約14秒**だった。消灯時間を変えるだけで結果が反転する。

`pmset displaysleepnow` → wake を 4回連続、全部成功（いずれも消灯 14 秒）:

```
[Modeset] FB0: Complete modeset
[Modeset] Lighting up eDP
IG:: EnableClocks:12937 PLL successfully enabled
[LINK_TRAINING] Running fast link training          <- "regular" ではない
[LINK_TRAINING] noLanes=2, ASR=1, downspread=0 BitRate = 10
[LINK_TRAINING] voltage=0, preEmphasis=0            <- 最低ドライブ強度
[LINK_TRAINING] laneMask=0xff, laneStatus=0x77      <- 完全ロック
```

- `laneStatus=0x77` = lane0 の `CR_DONE|CHANNEL_EQ_DONE|SYMBOL_LOCKED` (0x01|0x02|0x04)
  ＋ lane1 の同じ 3bit (0x10|0x20|0x40)。**2レーン完全ロック**。
- **リトライ 0回、電圧 0**。以前は電圧 3 / strength 0x87 まで上げて 8回失敗していた。
  最低強度で一発で通るということは、このレイアウトの eDP アイパターンが
  「たまたま許容範囲」ではなく **正しい**という意味。
- `Failed Phase 1` / `Link training failed` / `Not successful. Disabling display` は
  この起動で **0件**。
- アクセラレーションは無傷: Device ID `0x3ea5`、VRAM 1536MB、Metal 3、
  framebuffer 3個、Online: Yes、新規パニックなし。

### ★★ 2026-08-18 再訂正: 真因は「パネル電源投入のタイムアウト」だった

> **以下の「消灯時間依存」節は撤回された。** 実測で否定されたので、
> 結論としては読まないこと。残してあるのは、どこで判断を誤ったかの記録のため。
> 正しい真因はこの節にある。

帰宅した実機を調べたところ、**起動以降のパネル電源投入 7 回が、7 回すべて
タイムアウトしていた**。これまで一度も見ていなかった ERROR レベルの
グラフィクスログに出ていた:

```
  52 [IGFB][ERROR  ] Framebuffer 0 is not enabled yet!
   7 [IGFB][ERROR  ] hwSetPanelPower : Timeout powering ON the panel!!
   7 [IGFB][ERROR  ] displayPath is not NULL for index i = 0. continue
   7 [IGFB][ERROR  ] FB0 Not waiting for in set gamma to solid color as path state is not active
   6 [IGFB][ERROR  ]  [AGDC] AGDC not registered. Unmanaged display
   1 [IGFB][ERROR  ] FB0: Flip called without enabling VBL
   1 [IGFB][ERROR  ] FB0: VBlank Timeout Timer called in 51ms - fOnline: 1
```

毎回まったく同じ形をしている:

```
hwSetPanelPower (state=0)                  <- パネル OFF
hwSetPanelPowerConfig (value=1)
  ... 4〜6 秒後
hwSetPanelPower (state=2)                  <- 電源 ON 要求
  ... 2.20 秒後
[ERROR] hwSetPanelPower : Timeout powering ON the panel!!
hwSetPanelPower (state=2)                  <- 再要求（そのまま先へ進む）
```

タイムアウトまでの時間は 7 回で 2.170 / 2.248 / 2.255 / 2.250 / 2.253 / 2.184 /
2.197 秒。**固定タイムアウト約 2.2 秒が満了している**のであって、ばらつきのある
ハードウェア障害ではない。ドライバはパネル電源シーケンサ（`PP_CONTROL` に
要求を書いて `PP_STATUS` の完了ビットをポーリングする）の完了を待ち、
それが来ないまま諦めて次の段へ進んでいる。

**起動時だけ映る理由もこれで説明できる。** ブート直後（08:18:55）のログには
`hwSetPanelPowerConfig` しか無く、`state=0` → `state=2` の電源遷移が存在しない。
ファームウェアが既に点けたパネルをそのまま引き継ぐので、破綻する経路を通らない。

#### この発見で撤回される、それまでの結論

1. **`laneStatus=0x77` は成功の証拠にならない。**
   08:29:39 に `0x77` が出たが、画面は戻っていなかった。それ以降 5 時間半
   リンクトレーニングは一度も走っておらず、帰宅時に見えていた暗いパネルは
   08:23 から連続して暗かったものである。同じサイクルで
   `hwSetPanelPower : Timeout` も出ている。**リンクが張れてもパネルの電源が
   入っていなければ何も映らない。**
2. **「リトライすれば復帰する」手順は機能しない。** 下に残してある
   `for n in 1 2 3 4 5; ...` のループは、`laneStatus=0x77` を成功と誤認した
   前提の上に建てたもので、実機では一度も画面を復帰させていない。
   「3回目で絵が戻った」という記述はログからの推測で、視覚的に確認されていなかった。
3. **「消灯時間依存」は支持されない。** 不変なのは消灯時間ではなく
   「パネル電源投入が必ずタイムアウトする」ことである。テスト A の「成功」も
   `laneStatus` だけを見た判定であり、視覚確認を伴っていなかった。

#### 実務上の帰結

このパネルは**電源を落とすと必ず戻らない（7/7）。逆に、落とさなければ落ちない。**
08:29:39 から 14:06 までの 5 時間半、ログにイベントが一切無いのは、
パネルを消す要因が私のテストコマンド以外に無かったからである。
最初にユーザが踏んだのもホットコーナーのディスプレイスリープだった。

したがって対策は「復帰させる」ではなく「**消さない**」に一本化する。

#### 撤回済み（記録用）: 当初の「消灯時間依存」実験

システムスリープを無効化した状態（`pmset -a sleep 0`）で、消灯時間だけを変えた対照実験:

| テスト | 消灯時間 | 結果（当時の判定） |
|---|---|---|
| A | 15 秒 | `laneStatus=0x77` **成功**（← 視覚未確認。誤判定） |
| B | 180 秒 | `Failed to fast link train` / `laneStatus=0x7` **黒画面** |

S3 は両方とも介在していない。**途中で「原因は S3 だ」と診断したのは誤りで、
その根拠は私のグレップの誤検出だった** — 述語
`eventMessage CONTAINS "Entering Sleep state"` が、`log show` 自身のコマンドラインが
ログに載ったものにマッチしていた。S3 は起きていない。

つまりホットコーナーで踏んだ黒画面も、S3 のせいではなく**2分放置したから**である。

#### ドライバ側の欠陥: フォールバックが無い

```
[LINK_TRAINING] Failed to fast link train, err = 0x0
```

ドライバは fast link training の失敗を**検出しているのに、フルリンクトレーニングに
落ちない**。そのまま部分的にしか張れていないリンクで `EnablePipe` に進む。
だからこの失敗モードでは `Failed Phase 1 of Link Training` が出ない
（フルトレーニングが一度も試行されないため）。

**`Failed Phase 1` が無いことは成功の証拠にならない。必ず `laneStatus` を見ること。**

#### 部分ロックはレーン単位でランダム

| `laneStatus` | 意味 | 画面 |
|---|---|---|
| `0x77` | 両レーンロック | 出る |
| `0x07` | lane0 のみ (`0x01|0x02|0x04`) | 黒 |
| `0x70` | lane1 のみ (`0x10|0x20|0x40`) | 黒 |

1レーン HBR = 2.7 Gbps では必要な 4.155 Gbps に足りないので、片側だけでは何も映らない。

> **撤回。** 「ランダムなのでリトライすれば復帰する」と書いていたが、これは誤り。
> `0x7` → `0x7` → `0x77` という推移は実測どおりだが、`0x77` になっても画面は
> 戻らなかった（同じサイクルで `hwSetPanelPower : Timeout` が出ている）。
> 下のループは**実機で一度も画面を復帰させていない**。SSH 越しの復帰手段は
> 現時点では存在せず、暗くなったら再起動（電源ボタン短押し → クリーン
> シャットダウン → 電源オン）しかない。記録のために残す:

```bash
for n in 1 2 3 4 5; do
  T=$(date '+%Y-%m-%d %H:%M:%S')
  pmset displaysleepnow; sleep 4; caffeinate -u -t 10 & sleep 10
  r=$(log show --start "$T" --predicate 'senderImagePath CONTAINS "AppleIntelCFLGraphicsFramebuffer"' \
      --style compact 2>/dev/null | grep -oE 'laneStatus=0x[0-9a-f]+' | tail -1)
  echo "retry $n: $r"; [ "$r" = "laneStatus=0x77" ] && break
done
```

#### それでもレイアウト変更の効果は大きい

変更前は**復帰不能**だった: 8回のクロックリカバリ試行、ドライブ強度を
voltage=3 / 0x87 まで escalate、それでも毎回 `laneStatus=0`、最後は
`Link training failed - notifying AGDC to take display offline` /
`[Modeset] Not successful. Disabling display`。

リンク自体は張れる（`0x77` まで行く）。死んでいるのはパネル電源シーケンスであって、
レイアウト変更はそこには効かない。**ただし変更前の「リンクが全く張れない」状態からは
確実に一段改善しており、戻す理由は無い。**

#### 実機側の回避策（config ではなくランタイム）

対策は「消さない」に一本化する。`caffeinate` は**再起動で消える**ため恒久策にならない。
`pmset -a` は設定が永続するので、一度実行すれば足りる:

```bash
sudo pmset -a displaysleep 0 sleep 0      # アイドルのディスプレイスリープと S3 を両方封じる
```

sudo 不要な補助（これも必須。どちらもパネル電源を落とす経路になる）:

```bash
defaults write com.apple.dock wvous-tr-corner -int 1 && killall Dock   # ホットコーナーの Display Sleep を解除
defaults -currentHost write com.apple.screensaver idleTime -int 0      # スクリーンセーバを無効化
```

2026-08-18 に実機へ適用済み: `wvous-tr-corner` は 10 → 1、`idleTime` は既に 0。

> **★ この回避策は 2026-08-18 21:10 に解除した。** 真因（`camelliaVersion = 3`）が
> 判明して直ったので「消さない」で凌ぐ必要が無くなった。現行の設定は下記
> 「ディスプレイスリープ復活」を参照。`wvous-tr-corner = 1` と `idleTime = 0` は
> そのまま残してあるが、これは好みの問題であって回避策ではない。

#### ディスプレイスリープ復活（2026-08-18 21:10）

`framebuffer-camellia = 0` の検証が済んだので消灯を戻した。同時に、
S3 の失敗要因として知られている hibernate 系を潰した。**これらは消灯とは
別の問題**で、S3 を試す前に片付けておくべきもの:

```bash
sudo pmset -a hibernatemode 0     # 3 だった。スリープ毎に 1.0 GB の sleepimage を書く
sudo pmset -a standby 0           # 1 だった。3h/24h 後に hibernation へ遷移する
sudo pmset -a powernap 0          # AC で 1 だった。定期的な自動 wake がループの種
sudo pmset -a womp 0              # Wake on LAN。USB Ethernet 経由の意図しない復帰を防ぐ
sudo pmset -a proximitywake 0     # Apple Continuity 前提で本機では無意味
sudo pmset -c displaysleep 10 -b displaysleep 5
```

適用後の状態:

| | Battery | AC |
|---|---|---|
| `hibernatemode` | 0 | 0 |
| `standby` | 0 | 0 |
| `powernap` | 0 | 0 |
| `womp` | — | 0 |
| `proximitywake` | 0 | 0 |
| `displaysleep` | 5 | 10 |
| `sleep` | **0（意図的に維持）** | **0（同）** |

`hibernatemode 3` が既に `/var/vm/sleepimage` を 1.0 GB 作っていた
（`-rw------T root wheel 1.0G Aug 18 19:18`）。`hibernatemode 0` にしたので
今後は使われない。消したければ消せるが、放置しても害は無い。

**`sleep`（S3）はまだ 0 のまま。** パネル電源とは別のコードパスで未検証。
発見 2 の `RWAK` LIDS パッチ（offset `0x16796`）が既に入っているが、
S3 復帰そのものは一度も通していない。

**S3 試験のときの注意: `ttyskeepawake` が 1 である。**
つまり **SSH セッションが繋がっている間はシステムスリープしない。**
消灯試験には影響しなかったが、S3 では効いてくる。
`sudo pmset -a ttyskeepawake 0` にするか、SSH を切ってから
`pmset -g log` を後で読む形にする必要がある。

**蓋閉じは安全（2026-08-18 実測）。** 当初「別経路なので抑止できない穴」と
書いていたが、実測で否定された。上記 3 つを適用した状態で蓋を 22 秒閉じて開けた結果:

```
14:26:55  LID CLOSED        （ioreg AppleClamshellState: No -> Yes）
14:27:17  LID OPENED        （Yes -> No）

hwSetPanelPower の遷移      : 0 件（ログに一行も出ない）
Timeout powering ON the panel: 0 件
laneStatus                  : 0 件（リンク再訓練が発生していない）
Entering Sleep state        : 0 件
復帰後 IODisplayWrangler    : CurrentPowerState = 4
復帰後 bklt                 : 65535
```

クラムシェル状態自体は正しく検出されている（`No` → `Yes` → `No`）ので、
センサは動いている。それでもパネル電源遷移が一件も発生しない。つまり本機の
macOS では**蓋閉じがパネル電源のオフに配線されていない**。
`AppleClamshellCausesSleep = No` の申告と整合する。

限定: 閉じていたのは 22 秒で、長時間の閉じは未検証。ただし `displaysleep 0` に
してあるためアイドルタイマが存在せず、時間経過で発火する経路は残っていない。

#### 真因の詰め方: パネル電源シーケンサ

失敗サイクルのログにこれが出ている:

```
Using the default EDP panel timings
Override power up delays to optimize
hwSetPanelPower : Timeout powering ON the panel!!
```

ドライバはパネル固有のタイミングではなく**プラットフォーム既定の eDP タイミングを
使い、さらに電源投入遅延を短縮している**。Intel のパネル電源シーケンサは
`PP_ON_DELAYS` / `PP_OFF_DELAYS` / `PP_DIVISOR`（`PP_DIVISOR` は基準クロックからの
分周比）で T1〜T12 を刻む。分周比の前提が実機とずれていればシーケンスは
2.2 秒以内に完了しない。約 2.2 秒でぴたりと揃うタイムアウトは、
ハードウェア故障よりこの筋を示唆する。

**WhateverGreen に該当ノブは無い。** 調査結果:

- `framebuffer-featurecontrol-maximumselfrefreshlevel` は**使えない**。
  `WhateverGreen/kern_igfx.hpp` を読むと、このフィールドは
  `FramebufferWestmerePatchFlagBits`（第 1 世代 Westmere / Arrandale 専用）の
  中にあり、CFL には適用されない。`framebuffer-fbccontrol-*` /
  `framebuffer-featurecontrol-*` 一式が同様に Westmere 限定。
  → **CFL 向けの PSR / FBC ノブは存在しない。**
- `enable-backlight-registers-alternative-fix` (`-igfxblt`) は**すでに適用済み**。
  FAQ の「KBL/CFL の 3 分黒画面問題」節がまさにこの機種クラスの既知バグで、
  macOS 13.4 以降は旧 `-igfxblr` が効かない（Apple が `WriteRegister32` を
  インライン化したため）ので `-igfxblt` が正解、という記述と本機の条件は一致する
  （ドライバ `AppleIntelCFLGraphicsFramebuffer`、Sonoma 14.8.9、WEG 1.7.0、
  `SSDT-PNLF.aml` 投入済み）。**それでも直っていない。**
  `-igfxblt` が触るのは PWM 側（`BLC_PWM_*`）で、
  タイムアウトしているのはパネル電源側（`PP_CONTROL` / `PP_STATUS`）— 別レジスタ。
- `enable-dbuf-early-optimizer` (`-igfxdbeo`) は ICL 専用。
  なお `Pipe Underrun` / `DBuf` は本機のログに **0 件**なので、症状も違う。

未試行で残っている手は、別のモバイル 3 コネクタレイアウト
`0x3E920009` / `0x3E9B0009` を試すこと（プラットフォームデータが別のパネル電源
遅延を持っている可能性がある）。ただし本命は VBT 側であり、
WEG のノブでは届かない領域に入っている可能性が高い。

### ★★ 2026-08-18 決着: 真因は `camelliaVersion = 3`（VBT でもタイミングでもなかった）

> **直前の 2 段落（「本命は VBT 側」「未試行は `0x3E920009` / `0x3E9B0009`」）は
> 撤回する。** どちらも外れ。原因は**プラットフォームデータのたった 1 フィールド**で、
> しかも **WhateverGreen に専用のノブが存在する**。推測ではなく、実機に入っている
> バイナリを逆アセンブルして確定させた。

#### 調べ方（再現手順）

Sonoma のグラフィクス kext は `/System/Library/Extensions/` にはスタブしか無く、
本体は KernelCollection の中にある。CFL は **`BootKernelExtensions.kc` ではなく
`SystemKernelExtensions.kc`** 側（ロードアドレスが `0xffffff7f…` 系で、
`0xffffff80…` ではないことから判る。最初に BootKC を探して 62 MB 無駄に転送した）。

1. `LC_FILESET_ENTRY`（cmd `0x80000035`）のテーブルを走査して
   `com.apple.driver.AppleIntelCFLGraphicsFramebuffer` のエントリを見つける
   （`/tmp/kcparse.py`）。
2. この種の fileset は **`fileoff == vmaddr`** なので、`dd` で素朴に切り出した
   バイナリがそのままアドレス付きで逆アセンブルできる。
   `BASE=0x14070000`, `END=0x1412c000` → `/tmp/cfl.bin`（770,048 バイト）。
   SYMTAB（`symoff=0x150efe30`, `nsyms=3521`, `stroff=0x1529a640`）から
   シンボル 2931 個 → `/tmp/cfl.syms`（`/tmp/kcextract.py`）。
3. 逆アセンブルは **capstone**（`pip3 install --user capstone`）。
   Xcode の `llvm-objdump` には `-b binary` が無く、`llvm-mc` も同梱されていない。
   線形 sweep は途中で同期が外れて既知の参照を取りこぼすので、
   **シンボル境界で関数ごとに**逆アセンブルする（`scan2.py`）。
   （罠: スクリプトを `dis.py` と名付けると標準ライブラリの `dis` を隠して
   capstone の import が壊れる。`disx.py` に改名した。）

**そして最大の反省点**: `[IGFB][LOG  ]` レベルのメッセージは
**素の `log show` には出ない**。`log show --info --debug` が必要。
これまで ERROR 行しか見ていなかったので、「パネルプロパティ」経路や
`PP_STATUS=%#x` の存在に何ヶ月も気付かなかった。

#### 確定した因果

プラットフォームデータのテーブルは**実行時に構築される**（`__common` に即値を
書き込むコードがある）ので、静的なテーブルとしては grep できない。
レイアウト `0x3EA50009` の構造体は `0x14127600`（サイズ `0xb0`）で:

```
0x140db018  movabs r14, 0x400000003
0x140db022  mov    qword [0x14127660], r14      ; 0x14127600 + 0x60
```

`struct+0x60` は **`camelliaVersion`** で、値は **3**。
（WEG の `kern_fb2.hpp` の `FramebufferCFL` を手で並べると `camelliaVersion` は
ちょうど `0x60`、構造体全体が `0xb0` — 22.0.5 の実バイナリと完全一致。
つまり WEG の構造体定義はこの OS バージョンでも正しい。）

`camelliaVersion` は「Apple 製 TCON（パネル側タイミングコントローラ）が
載っているか」を決めるフィールドである: 2 → `CamelliaTcon2`、
3 → `BanksiaTcon`、0 → どちらも無し。
`AppleIntelFramebufferController::start()`:

```
0x1409b41b  cmp   dword [rax+0x60], 3
0x1409b425  lea   rax, [rip+0x81a2c]            ; <__ZN11BanksiaTcon9metaClassE>
0x1409b438  mov   qword [rbx+0x2e68], rax
```

→ ドライバは **`BanksiaTcon` を生成する**。`BanksiaTcon` は実機 Retina MacBook Pro の
パネルに載っているチップで、**本機の Sharp LQ133M1JW41 には存在しない**。
`InitTcon` は（AUX が通らなくても）成功扱いで進むらしく、
`[rbx+0x2e68]` は非 NULL のまま残る。ここから 2 つの結果が出る:

**(a) PP_ON_DELAYS がゼロにされる。** `hwSetPanelPowerConfig`:

```
0x1409fc94  cmp   qword [rbx+0x2e68], 0          ; TCON あり?
   → ログ "Override power up delays to optimize"
0x1409fcc3  mov   dword [rbx+0x2c20], 0          ; PP_ON_DELAYS = 0
```

つまり**直そうとしていた遅延値は、意図的に捨てられていた**。
ログの "Override power up delays to optimize" は症状ではなく、
TCON 経路に入った証拠だった。

**(b) 存在しないチップを 2.2 秒ポーリングする。** `hwSetPanelPower(2)`:

```
0x140aa0b7  cmp   qword [rbx+0x2e68], 0          ; 同じ判定
   TCON 経路: r13d = 0x1e (= 30 回)
       WriteCamelliaReg(0x10200DE, 1, 0xC)
       ReadCamelliaReg (0x10200E9, 1, &v)
       IOSleep(0x14)                             ; 20 ms
0x140aa28e  （抜けた先）
   → 0x140f95de "[IGFB][ERROR  ] %s : Timeout powering ON the panel!!"
```

30 × (AUX 失敗 + 20 ms) ≒ **2.2 秒**。
実測は 7/7 で 2.170 / 2.248 / 2.255 / 2.250 / 2.253 / 2.184 / 2.197 秒。
これは「約 2.2 秒に近い」のではなく、**このループそのもの**である。

**`camelliaVersion == 0` なら通る経路**（`0x140aa242`）:

```
r15d = 0x32 (= 50 回)
    IOSleep(0x19)                                ; 25 ms
    PP_STATUS & 0xB0000000 == 0x80000000 ?        ; ON かつシーケンサ完了かつ
                                                 ; power-cycle-delay 未消化でない
0x140aa42a  成功
```

これが**普通の eDP パネルが実際に完了できる経路**で、しかも
PP_ON_DELAYS をゼロにしない。

#### 参考: PCH パネル電源レジスタ（CFL）

| Addr | Reg | 内容 |
|---|---|---|
| `0xC7200` | PP_STATUS | bit31 = パネル ON / bits 29:28 = シーケンス進行 / bit27 = power cycle delay 中 |
| `0xC7204` | PP_CONTROL | bit0 = ON 要求 / bit1 = power-down on reset / bit3 = backlight enable / bits 8:4 = power cycle delay |
| `0xC7208` | PP_ON_DELAYS | 28:16 = 電源投入 T1+T3 / 12:0 = バックライト ON T8（単位 100 µs） |
| `0xC720C` | PP_OFF_DELAYS | 28:16 = 電源切断 T10 / 12:0 = バックライト OFF T9 |

#### 打ち手その 1（採用）: `framebuffer-camellia`

WEG はこのフィールドをそのまま公開している。`kern_igfx.cpp:1473`:

```cpp
framebufferPatchFlags.bits.FPFCamelliaVersion =
    WIOKit::getOSDataValue(igpu, "framebuffer-camellia",
                           framebufferPatch.camelliaVersion);
```

`framebuffer-patch-enable` に依存するが、それは既に投入済みで、
`framebuffer-stolenmem` / `framebuffer-fbmem` が効いていることから
**この機種で実際に機能することが確認済み**。値 0 でも
`getOSDataValue` はプロパティの存在で真を返すので、`= 0` は正しく伝わる
（`kern_igfx.cpp:1751` で `frame->camelliaVersion` に代入される）。

```
PciRoot(0x0)/Pci(0x2,0x0)
    framebuffer-camellia   <00000000>
```

**「WhateverGreen に該当ノブは無い」という上の結論は、この 1 つに関して誤り
だった。** PSR / FBC / PWM のノブを探していて、TCON のノブを探していなかった。

#### 打ち手その 2（保留）: `AAPL00,Panel*` — 未公開だが実在する注入経路

`AppleIntelFramebufferController::hwGetPanelTimingProperties()` は iGPU の
provider から 5 つの `OSNumber` プロパティを読み、`PP_ON_DELAYS` /
`PP_OFF_DELAYS` / `PP_CONTROL[8:4]` を直接プログラムする:

| プロパティ | 単位 | 変換 | Apple 内蔵の既定 |
|---|---|---|---|
| `AAPL00,PanelPowerUp` | ms | ×10 → PP_ON_DELAYS[28:16] | 12.5 ms |
| `AAPL00,PanelPowerOn` | ms | ×10 → PP_ON_DELAYS[12:0] | 210 ms |
| `AAPL00,PanelPowerDown` | ms | ×10 → PP_OFF_DELAYS[28:16] | 74 ms |
| `AAPL00,PanelPowerOff` | ms | ×10 → PP_OFF_DELAYS[12:0] | 250 ms |
| `AAPL00,PanelCycleDelay` | ms | ÷100 + 1 → PP_CONTROL[8:4] | 500 ms |

（既定値はバイナリ中の即値 `0x02E409C4007D0834` と除数 6 から。
この経路に入るには `AAPL00,PanelPowerOn` が存在して非ゼロである必要がある。）

**意図的に保留する。** 実験は 1 回に 1 変数。`framebuffer-camellia = 0` は
(a) により PP_ON_DELAYS の破棄も同時に止めるので、これ単独で直る見込みがある。
タイミング注入は第 2 ラウンド用に取っておく。

#### 検証方法（判定基準を先に決めておく）

`IG: TCON:` 行が **`BanksiaTcon` 初期化の直接の指標**。修正前の実測ベースライン
（`camelliaVersion = 3`、boot 17:33:32、`log show --info --debug` を起動時刻で絞ったもの）:

| パターン | 修正前 | 修正後の期待 |
|---|---|---|
| `IG: TCON` | **2** | **0** |
| `hwSetPanelPower` | 2 | 2 |
| `default EDP panel timings` | 2 | — |
| `Override power up delays` | 0 | 0 |
| `Timeout powering` | 0（この boot は消灯試験をしていない） | **0**（消灯試験後も） |
| `panel properties` | 0 | 0（第 2 ラウンドまでは） |

判定スクリプトは実機の `~/panelchk.sh`（sudo 不要）。

#### ★★★ 結果: 直った（2026-08-18 21:03）

再起動後（boot 19:17:49）の判定は予測どおり:

| パターン | 修正前 | 修正後 |
|---|---|---|
| `IG: TCON` | 2 | **0** ✅ |
| `Timeout powering` | 7/7 | **0** ✅ |
| `Override power up delays` | 消灯時に出る | **0** ✅ |
| Metal / VRAM / 解像度 | Metal 3 / 1536MB / 1080p | 同一（副作用なし） |

そして実際の消灯 → 点灯サイクルが**通った**:

```
20:58:44.844  hwSetPanelPower (state=0)          <- 消灯要求
20:58:44.844  hwSetPanelPowerConfig (value=1)
20:58:44.844  Using the default EDP panel timings
20:58:45.197  Panel power OFF time was 353 ms    <- OFF 完走
20:58:45.197  PP_STATUS=0x8000001                <- bit27 = power cycle delay 中、パネル OFF

    ... 4 分 32 秒 消灯したまま ...

21:03:17.334  hwSetPanelPower (state=2)          <- 点灯要求
21:03:17.334  hwSetPanelPowerConfig (value=1)
21:03:17.334  Using the default EDP panel timings
21:03:17.560  Panel power ON time was 225 ms     <- ★ 225 ms で完走
21:03:17.560  PP_STATUS=0x80000008               <- ★ bit31 = パネル ON、シーケンサ完了
21:03:17.560  [Transition_wake] FB0 Lighting up display in resume from sleep
21:03:17.560  [Modeset] Lighting up eDP
21:03:17.561  [LINK_TRAINING] Running fast link training
21:03:17.561  [LINK_TRAINING] noLanes=2, ASR=1, downspread=0 BitRate = 10
21:03:17.561  [LINK_TRAINING] voltage=0, preEmphasis=0
21:03:17.580  [LINK_TRAINING] laneMask=0xff, laneStatus=0x77
```

**2.2 秒のタイムアウトが 225 ms の正常完了に置き換わった。**
そして最も強い証拠が `PP_STATUS=0x80000008` である。
逆アセンブルから読み取った汎用経路（`0x140aa242`）の成功条件は

```
PP_STATUS & 0xB0000000 == 0x80000000
```

で、`0x80000008 & 0xB0000000 = 0x80000000` — **予測した合格条件にビット単位で一致**。
`Panel power ON time was ...` と `PP_STATUS=...` は、どちらも**それまで一度も
ログに出たことがない行**である（ベースラインで 0 件）。TCON 経路では
そこまで到達しないので出るはずがなく、出たこと自体が経路が変わった証拠になる。

`Panel power OFF time was 353 ms` も新規。OFF 側は元々破綻していなかったが、
完了時間がログに出るようになったのは同じ理由（同じ関数の後段）。

`laneStatus=0x77` が `voltage=0, preEmphasis=0` の**初回**で出ていること、
かつ今回は**視覚的に画面が戻ったことをユーザが確認している**点が重要。
過去に `0x77` を「成功」と誤読した反省（発見 10 の撤回節）を踏まえ、
ログではなく実際の表示で判定した。

**副産物: 「消灯時間依存」仮説は完全に死んだ。** 今回消灯していたのは
4 分 32 秒で、過去に「長時間消灯すると戻らない」とされた領域に十分入っている。

残った ERROR 行は modeset 前後の VBlank / flip タイミングのノイズで、
パネル電源とは無関係:

```
2 TxnHang1: FB0: IsTransactionComplete called following fakeVBL notification
1 displayPath is not NULL for index i = 0. continue
1 Path state is 2
1 FB0: VBlank Timeout Timer called in 51ms - fTransactionState = 0x0 ... fOnline: 1
1 FB0: Flip called without enabling VBL
1 FB0 Not waiting for in set gamma to solid color as path state is not active
```

**`AAPL00,Panel*` の第 2 ラウンドは不要になった。** `framebuffer-camellia = 0`
単独で解決したので、パネルタイミングの注入には手を付けない
（プロパティの仕様は上に記録してあるので、将来必要になれば使える）。

#### 試験手順のメモ（次に同種の試験をするとき用）

- 消灯のトリガは **Ctrl+Shift+電源ボタン**。`pmset displaysleepnow` は root が
  必要なので、権限付与を最小に保つならキーボード操作の方が良い。
- 点灯は普通のキー入力 / トラックパッド。
- `log stream` を `nohup` で回しておくと、画面が真っ暗で SSH が切れても記録が残る。
  ただし **`log show --last Nm` で後から拾える**ので、監視窓を外しても復旧できる。
- 遠隔からの復旧手段として、`/etc/sudoers.d/reboot-nopasswd` に
  `hiroki ALL=(root) NOPASSWD: /sbin/reboot` を 1 行だけ入れた（ユーザ承認済み）。
  付与範囲は reboot のみ。`osascript` 経由の再起動は
  **GUI ダイアログに依存するため復旧手段として使えない**（上述）。
- ssh 越しに `log show --predicate '...'` を渡すときは、
  `ssh host 'bash -s' <<'EOF' ... EOF` の形にする。
  シングルクォート内で `\"` をエスケープする書き方は壊れて 0 行になった。

#### 安全上の前提

このパネルは**電源を落とすと戻らない（7/7）**ので、消灯試験は
「戻らなければ再起動するまで真っ暗」の片道切符である。したがって試験前に:

1. **ESP をアンマウントしておく**（`diskutil unmount disk0s5`）。
   ジャーナル無しの FAT32 をマウントしたまま電源を落としたのが、
   過去に `VirtualSMC` を壊した原因。
2. **画面が見えなくても叩ける再起動手段を用意しておく。**
   `osascript -e 'tell application "System Events" to restart'` は
   **不適**と判明した: `rc=0` を返すのに再起動せず（`kern.boottime` 不変）、
   2 回目の呼び出しは `UserNotificationCenter` の Automation 許可ダイアログで
   ハングした。**画面上の GUI ダイアログに依存する手段は、
   画面が見えない状況の復旧手段として原理的に使えない。**

### 副産物: `dpcd-max-link-rate` の値は「無害な上限」ではない

当初 `0x14` (HBR2) を「リンクトレーニングが下方ネゴシエートする上限だから高い方が安全」
という理屈で設定していた。**この理屈は誤り**で、FAQ は解像度ごとの指定を求めている:

> "Typically use `0x14` for 4K display and `0x0A` for 1080p display.
> All possible values are `0x06` (RBR), `0x0A` (HBR), `0x14` (HBR2), `0x1E` (HBR3)."

本機パネルは **Sharp LQ133M1JW41**（13.3" 1920x1080 eDP、実機 EDID の
`ioreg AppleBacklightDisplay` → `IODisplayEDID` 内のディスクリプタ文字列から同定）。
FAQ がこの修正の代表例として挙げているのがまさに Sharp eDP パネル
（"Dell Inspiron 7590 with Sharp display"）。

`0x0A` で足りることは同じ EDID の detailed timing から出る:

```
pixel clock = 0x361A = 13850     -> 138.50 MHz
payload     = 138.50 MHz * 24bpp -> 3.324 Gbps
8b/10b      = 3.324 / 0.8        -> 4.155 Gbps 必要
2 lane * 2.7 Gbps (HBR)          -> 5.400 Gbps 利用可能
headroom                          = 1.30x
```

ドライバ自身のログ (`pixelClock=138500000, linkSymbolClock=270000000,
colorDepth=24, noLanes=2`) と一致する。

**ただし `0x14` → `0x0A` の変更はこのバグを直していない。** `0x0A` にしても
`0x3E9B0000` のままでは同じく `laneStatus=0` で失敗した。`0x0A` を維持しているのは
FAQ 準拠で、実測十分で、実際にリンクがこの rate で走っているからであって、
修正だったからではない。

注意: カーネルログの DPCD ダンプは**パネルの素の能力の確認には使えない**。
WEG が AUX 読み出しをフックした後に `GetDPCDInfo` がダンプを出すので、
`14 14 C2 41` は自分が注入した値が見えているだけ。
このパネルの真の最大リンクレートは未観測。

### 未解決として残したこと

`enable-dpcd-max-link-rate-fix` / `dpcd-max-link-rate` のペアが、レイアウトが
正しくなった今でも必要かは**未検証**。このペアは `-igfxblt` 下のゼロ除算パニック対策として
入れたが、そのパニックの診断は間違ったレイアウトのまま行われたので、
同じ根本原因の別症状だった可能性がある。外して試す価値はあるが、
失敗モードが起動パニックなので、他の変更と混ぜず、revert スクリプトを用意して単独で行う。

## ★★ 発見 10b: S3 システムスリープは完全に動く（`Wake reason: XDCI` は誤読だった）

2026-08-18 21:44、`framebuffer-camellia = 0` を入れた状態で S3 を初めて通した。
`pmset sleep 0` が止めるのは**アイドル**スリープだけなので、
設定を変えずに 🍎 メニューから明示的にスリープすれば発動する。

### 結果: スリープも復帰も成功した（再起動もパニックも無し）

```
21:44:16.734  PMRD: tellChangeDown ON_STATE->SLEEP_STATE
21:44:16.738  PMRD: sleep factors 0x2208c6, LidOpen, ACPower, StandbyDisabled,
                    USBExternalDevice, RTCAlarmScheduled, AutoPowerOffDisabled,
                    LocalUserActivity
21:44:16.802  PMRD: hibernateMode 0x0          <- hibernatemode 0 が効いている
21:44:17.155  PMRD: === FINISH (ON_STATE->SLEEP_STATE, 9->0, 0x40c2)
21:44:17.155  PMRD: System Sleep               <- ★ 本当に S3 に入った
21:44:17.161  PMRD: evaluateSystemSleepPolicyFinal
21:44:17.162  PMRD: trace point 0x19           <- CPU が止まる直前の最後の記録

21:44:18.189  AppleACPIPlatformPower Wake reason: XDCI    <- ⚠ 1.03 秒後
21:44:18.189  PMRD: trace point 0x23
21:44:18.199  PMRD: trace point 0x22
      ... 7.8 秒、dark wake のまま何も起きない ...
21:44:26.000  PMRD: System Wake
21:44:26.000  PMRD: Clamshell opened / display wrangler tickled
21:44:26.000  PMRD: Requesting full wake due to dark wake activity tickle
21:44:26.000  PMRD: full wake request (reason 1) 0 ms
```

**これは発見 2 / 発見 5 の「スリープ復帰で画面が壊れて再起動が必要」が
解消されたことを意味する。** 画面は戻り、`boottime` は不変（19:17:47）で
再起動していない。`RWAK` LIDS パッチ（offset `0x16796`）とパネル修正が
揃って初めて S3 が通った。

### ★ 訂正: `Wake reason: XDCI` は問題ではない（自分の誤読だった）

当初これを「XDCI が 1 秒後にマシンを dark wake させている」と読み、
`XDCI._PRW` を潰す ACPI パッチが必要だと判断した。**これは誤りである。**
`framebuffer-camellia` の件と同じく、推測ではなく計測で決着させた。

**決定的な証拠 1: スリープ中のログは完全に沈黙している。**
アイドルスリープを有効にして（`sleep 20`/`10`、`ttyskeepawake 0`）
2 回目のサイクルを取った:

```
22:20:45.658  PMRD: System Sleep
22:20:45.690  AppleACPIPlatformPower Wake reason: XDCI
      ... 4 分 12 秒 ...
22:24:58.003  PMRD: System Wake
```

この 4 分間のログ行数を数えると **0 行**。
30 秒バケットで数えると `22:20:4x` から `22:24:5x` へ丸ごと飛んでいる:

```
2027 22:20:4x
15478 22:24:5x        <- 間に何も無い
```

dark wake で起きていたなら、この 4 分間に必ずログが出る。出ていない。
**マシンは本当に寝ていた。** 1 回目の空白（21:44:18.3〜21:44:25.9）も同様に 0 行。

**決定的な証拠 2: trace point の並びが `Wake reason` の位置を決めている。**

```
22:20:45.658  PMRD: System Sleep
22:20:45.690  Wake reason: XDCI
22:20:45.690  PMRD: trace point 0x23     <- スリープ経路の末尾
22:20:45.707  PMRD: trace point 0x22     <- 同
      ... 4 分 12 秒 ...
22:24:58.003  PMRD: System Wake
22:24:58.003  PMRD: trace point 0x24     <- ここからウェイク経路
22:24:58.008  PMRD: trace point 0x25
22:24:58.014  PMRD: trace point 0x26
22:24:58.015  PMRD: trace point 0x27 ...
```

`0x19 → 0x23 → 0x22` はスリープ経路の末尾で、
ウェイク経路は `0x24` から始まる。
`Wake reason: XDCI` は `0x23` / `0x22` と**同時刻**、つまり
**スリープ完了時に「どのデバイスを wake 源として arm したか」を
記録している行**であって、実際に起きた記録ではない。
メッセージ文面が "Wake reason" なので誤読しやすいが、位置が答えを決めている。

実際のウェイク源は別の行に、正しいウォールクロック時刻で出る:

```
22:24:58.721  PMRD: system wake events: XDCI XHC
```

`XHC` は USB ホストコントローラ。これはユーザがキーを押したことによる
正当なウェイクである（`Requesting full wake due to dark wake activity tickle`）。

### 結論: S3 は完全に正常。ACPI パッチは不要

- スリープに入る ✅
- 4 分以上寝続ける ✅（ログ沈黙で確認）
- キー入力で復帰する ✅
- 画面が戻る ✅（`framebuffer-camellia` の修正が効いている）
- 再起動もパニックも無し ✅（`boottime` 不変）

`XDCI` が ACPI 名前空間に居て PCI 14.1 が列挙されていないこと自体は事実だが、
**害は出ていない**ので触らない。`XDCI._PRW` → `XPRW` のリネームは
**やる必要が無かった**（必要になったときのために手法だけ記録しておく:
OpenCore の `ACPI > Patch` で `_OSI`→`XOSI` と同じパターン）。

#### 教訓

ログのメッセージ文面ではなく**前後の trace point / 行数**で判断すること。
`camelliaVersion` の件では ERROR レベルしか見ていなかったせいで
真因を長く見落とし、ここでは逆に文面を読んで在りもしない問題を作った。
**「その時間帯にログが何行出ているか」は、電源管理の判定で最も安いかつ
最も強い証拠になる。**

### 参考: スリープ時の USB カーネルアサーション

`sleep factors` に `USBExternalDevice` が立っている。実際に 4 件:

```
id=500  owner=GesturePoint Mouse Dongle      (com.apple.usb.externaldevice.14200000)
id=501  owner=USB2.1 Hub                     (...14300000)
id=503  owner=USB3.1 Hub                     (...14900000)
id=505  owner=AX88179A                       (...14940000)
```

`AX88179A` は SSH に使っている USB Ethernet 自身。これらはスリープを
禁止してはいないが、スリープポリシー評価に影響する。

### 注意: `MaintenanceWakeCalendarDate`

```
21:44:16.733  PMRD: MaintenanceWakeCalendarDate 2026/08/18 14:44:14
21:44:16.733  PMRD: next alarm (MaintenanceWakeCalendarDate) 2026/08/18 14:44:14
21:44:16.733  PMRD: scheduled alarm mask 0x4
```

14:44:14 UTC = 2 時間先の RTC アラーム。`sleep factors` の
`RTCAlarmScheduled` はこれ。1 秒後の wake の原因ではない。
`powernap 0` にしたので今後は減るはず。

## ★ 発見 11: 内蔵カメラは動作している（2026-08-18 確認）

Reddit 報告では未確認扱いだった内蔵 Web カメラを、実機ログで確認した。

### 認識状態

```
system_profiler SPCameraDataType:
  Integrated Camera:
    Model ID: UVC Camera VendorID_5075 ProductID_22229    (0x13D3:0x56D5, IMC Networks)
    Unique ID: 0x1440000013d356d5

ioreg -p IOUSB:
  +-o Integrated Camera@14400000  <class AppleUSBDevice, registered, matched, active>
```

追加 kext は不要。Apple 標準の `UVCAssistant`（CoreMediaIO system extension）＋
`VDCAssistant` がそのまま担当する。

### ストリーミング実測（Photo Booth を SSH から起動して計測）

```
UVCUSBDeviceStreamingInterface  format: UVCDeviceStreamFormat:[1280 * 720 (MJPEG)]
                                frameInterval : 333333            (= 30.0 fps)
Last Stream  StartTime: 08:42:42.497   StopTime: 08:45:53.628
FirstPacketTime:        08:42:42.645   (開始 +148 ms)
FirstFrameDispatchTime: 08:42:42.814   (開始 +317 ms)
TotalPackets: 1527768   TotalFrames: 5768
```

- **3分11秒で 5,768 フレーム = 30.2 fps**、公称 30 fps とほぼ一致。実質ドロップなし
- 1280×720 MJPEG。USB のアイソクロナス転送が正常に成立している
- 最初のフレームが 317 ms で到達 → 初期化も正常
- メニューバーにカメラ使用中インジケータ（緑）が点灯

停止時に出る

```
(IOUSBHostFamily) UVCAssistant@14400000: AppleUSBHostFrameworkInterfaceClient::
  hostPipeClearStall: unable to get pipe with endpoint address 129
```

は、既に破棄済みの IN エンドポイント (0x81) に対する後片付けメッセージで**無害**。

### ★ 絵の中身も確認済み（2026-08-18 15:08、画像データで確定）

当初は「絵の中身は未確認」として残していた。MJPEG は真っ黒な被写体でもフレームを
配送するので、30 fps 安定配送だけでは中身を保証しないという理由である。これを
**実画像の画素統計で潰した。**

手順は Photo Booth で1枚撮影 → JPEG を SSH で回収 → PNG に変換して自力デコードし、
4px 間隔でサンプリングした 21,600 画素の統計を取る、というもの。

```
720x480 JPEG, 52,830 bytes
luma  mean=147.5  sd=90.3  min=10  max=255
channel means  R=150.5  G=145.9  B=147.8
histogram (16 bins, 各 16 luma 幅, per-mille):
    12  146   88   40   42   46   39   40   49   39   32   22   14   22   17  345
```

- **mean=147.5 / sd=90.3** — 真っ黒なら mean≒0, sd≒0 になる。明暗差のある実シーン
- **16 ビン全部に分布** — 単色塗りでもノイズでもない。暗部 146‰、白飛び 345‰（窓光）
- **R/G/B の平均がほぼ等しい** — 緑被り・紫被りといった UVC のフォーマット誤認なし。
  ホワイトバランスも正常
- 目視でも鮮明でピントが合っており、上下左右の反転もない

したがって内蔵カメラは**転送・デコード・色・向きのすべてが正常**。追加 kext もパッチも不要。

なお USB ポートマッピング（USBToolBox）は**まだ実施していない**。それでもカメラの
アイソクロナス転送が 30 fps で成立しているので、少なくともこのポートの
記述は実用上問題ない。

### 手法メモ: SSH セッションからカメラは掴めない

自動化のため AVFoundation で1フレーム取得する Swift プログラムを書こうとしたが、
これは筋が悪い。`kTCCServiceCamera` の許可レコードがユーザ TCC.db に1件も無く、
SSH セッションには許可ダイアログを出す手段がないため、TCC に無言で弾かれる。

**GUI アプリ（Photo Booth）に撮らせて、生成物を SSH で回収して解析するのが正解。**
実アプリ経由なので end-to-end の確認にもなる。

## ★ 発見 12: SSH 越しの `screencapture` はウィンドウを無言で剥がす

SSH 経由で `screencapture -x` を実行すると **exit 0 で成功し、正常な PNG が生成される**。
しかしその画像には**壁紙とメニューバーしか写らない** — ウィンドウも Dock も
一切含まれない。エラーも警告も出ない。

### 判定の根拠

- Dock プロセス（PID 367）が稼働しているのに、全キャプチャで Dock が写らない
- Photo Booth の保存ウィンドウ位置は `"NSWindow Frame Main Window" = "556 252 720 568 0 0 1920 1055"`
  = 完全に画面内なのに写らない
- ディスプレイは1台のみ（`screencapture -x a.png b.png c.png` で 2枚目以降は生成されず、
  `system_profiler` も `Connection Type: Internal` の1台のみ）。ゴーストディスプレイ説は否定
- 連続2回のキャプチャがバイト単位で同一サイズ（3917842）→ 画面内容が変化していない

### TCC の判定（`log show --predicate 'process == "tccd"'`）

```
kTCCServiceScreenCapture
responsible = com.apple.sshd-keygen-wrapper  (/usr/libexec/sshd-keygen-wrapper)
requesting  = com.apple.screencapture        (/usr/sbin/screencapture)
arbiter     = com.apple.WindowServer
```

権限は **`sshd-keygen-wrapper` に帰属**する。これが「画面収録」の許可リストに
無いため、WindowServer がウィンドウ内容を伏せる。

### 対処

フルスクリーンを取得したい場合は、システム設定 →
プライバシーとセキュリティ → 画面収録 に **`/usr/libexec/sshd-keygen-wrapper`** を追加する
（ファイル選択ダイアログで `Cmd+Shift+G` を使ってパスを直接入力。管理者権限が必要）。
TCC.db は SIP 保護下なので、リモートから `sudo` 無しでは変更できない。

**教訓: このプロジェクトで「画面が正常か」を screencapture で判断してはいけない。**
黒画面バグの最中でもフレームバッファの中身は正常に撮れてしまうし、
逆にウィンドウが写らないのはアプリの異常ではない。
リンクトレーニングの成否は `laneStatus` で、カメラの成否は UVC のフレーム数で見る。

---

## ★ 発見 13: SSH 越しの `log show` は zsh の `log` 組み込みに食われる

`ssh host 'log show --last boot ...'` が、エラーも出さず **0 行**を返す。
grep が何も見つけられないので「そのイベントは起きていない」と誤読する。

原因は zsh に `log` という組み込みコマンドがあること（csh 由来。ログイン中の
ユーザを表示するもの）。非対話 zsh でも組み込みが優先されるので、
`/usr/bin/log` は呼ばれない。引数を渡すと `zsh:log:5: too many arguments` になる
（これも stderr に出るだけで、パイプ先の `wc -l` は 0 を返す）。

```
# 壊れる
ssh host 'log show --start "..." | wc -l'        -> 0
# 正しい
ssh host '/usr/bin/log show --start "..." | wc -l'  -> 1812091
```

**この罠のせいで「起動以降リンクトレーニングは一度も走っていない」と誤診断した。**
実際には 6 回走っていて、うち 4 回が fast link train 失敗、
7 回すべてでパネル電源投入がタイムアウトしていた（発見 10 の再訂正節）。

あわせて、これまでに踏んだログ読みの罠:

- `log show --last Nm` は**前回の起動まで遡る**ことがある。`kern.boottime` と
  照合するか `--start` で起動時刻を明示する。
- 述語 `eventMessage CONTAINS "..."` は **`log show` 自身のコマンドラインが
  ログに載ったもの**にマッチする。これで「S3 が起きた」という偽陽性を出した。
- ログの `at 197856915` のような数値は**起動からのマイクロ秒**。
- `[Modeset] Disabling display for non-camelia fbs` は無害で、
  `[Modeset] Not successful. Disabling display` とは別物。
- **ERROR レベルを最初に見ること。** `[IGFB][ERROR ]` で絞れば
  `hwSetPanelPower : Timeout powering ON the panel!!` が一行で出ていた。
  LOG レベルの `laneStatus` を延々追う前にこれを見るべきだった。

## ★ 発見 14: このマシンの `swiftc` は壊れている（CLT の残骸ファイル）

macOS 側で小さな検証プログラムを書こうとすると、`swiftc` が Foundation すら
ビルドできずに失敗する。

```
/Library/Developer/CommandLineTools/usr/include/swift/module.modulemap:13:8:
  error: redefinition of module 'SwiftBridging'
→ 連鎖して error: could not build module 'CoreServices'
                could not build module 'Foundation'
                could not build module 'ApplicationServices'
```

### 原因

同じディレクトリに、同じモジュールを宣言したファイルが2つ残っている。

```
-rw-r--r--  root  wheel  581  Dec  4  2024   bridging.modulemap
-rw-r--r--  root  wheel  581  Aug 18  2023   module.modulemap     ← 古い残骸
```

中身は同一で、両方が `module SwiftBridging { header "bridging" export * }` を宣言。
clang はそのディレクトリの modulemap を全部読むので衝突する。

**日付が答え。** 新しい CLT（16.2.0、2024-12）がこのファイルを `module.modulemap` から
`bridging.modulemap` に改名したが、インストーラが古い CLT（2023-08 = 15.x 系）の
`module.modulemap` を削除しなかった。アップグレード時の典型的な残骸で、
**ハッキントッシュ固有の問題ではない。**

実機の環境自体は正常:

```
com.apple.pkg.CLTools_Executables  version: 16.2.0.0.1.1733547573
Apple Swift version 6.0.3 (swiftlang-6.0.3.1.10 clang-1600.0.30.1)
Target: x86_64-apple-macosx14.0
xcode-select -p → /Library/Developer/CommandLineTools
```

### 直し方 — **実施・検証済み（2026-08-18 15:20）**

古い方を削除ではなく改名する（中身が同一なので戻せる）。

```
sudo mv /Library/Developer/CommandLineTools/usr/include/swift/module.modulemap \
        /Library/Developer/CommandLineTools/usr/include/swift/module.modulemap.disabled
```

適用後の確認:

```
$ printf 'import Foundation\nprint("swift-ok", ProcessInfo.processInfo.hostName)\n' > /tmp/t.swift
$ swiftc -o /tmp/t /tmp/t.swift     → rc=0
$ /tmp/t                            → swift-ok hirokis-macbook-pro.local
```

`import Foundation` を含むプログラムがエラーなしで通る。**これで原因の切り分けも裏取りできた**
（重複 modulemap 1ファイルの除去だけで直った）。以後、macOS 側で小さな検証プログラムを
書いて実機を調べる手が使える。

## ★★ 発見 15: Windows 起動確認と、その場で見つかった2つの実害（2026-08-18 15:37-15:45）

### まず本題: Windows は OpenCore のピッカーから起動する

config を何度も書き換えた後でも、同一 NVMe 上のデュアルブートは生きている。**実起動で確認済み。**

事前に OpenCore の起動ログ（`Misc > Debug > Target = 67` = 0x43 でファイル出力あり、
ESP 直下に `opencore-YYYY-MM-DD-HHMMSS.txt`）でエントリ登録も確認していた:

```
01:247  OCB: Found 11 potentially bootable filesystems
01:662  OCBP: Predefined \EFI\Microsoft\Boot\bootmgfw.efi was found
01:672  OCB: Registering entry Windows [Windows] (T:32|F:0|G:0|E:0|B:0)
        - HD(2,GPT,CA948512-7708-4912-AF47-1065E6D9919F,0x32800,0x32000)
          /\EFI\Microsoft\Boot\bootmgfw.efi
04:166  OCB: Should boot from 2. Macintosh HD (T:2|F:0|G:0|E:0|DEF:0)
```

**副産物: `disk0s2` が macOS からマウントできない件は、OpenCore の障害ではない。**
上のログの `HD(2)` はまさにその `disk0s2` で、OpenCore は自前の FAT ドライバで
問題なく読めている。macOS の msdos ドライバ側の癖であって、ESP の破損ではない。

`DEF:0` = デフォルトエントリは未設定（`Ctrl+Enter` での設定は別途）。

起動後の健全性:

| 項目 | 値 | 判定 |
|---|---|---|
| OS | Windows 11 Home 10.0.**26200** | 記録は 26100 → **Windows Update が走った** |
| BIOS | **1.01 / 2018-11-12** | **維持されている（最重要）** |
| Secure Boot | False | OpenCore に必要、正常 |
| ディスク | Samsung 970 EVO 1TB, GPT, 7 パーティション | 無傷 |
| C: | 350.01 GB | 正常 |
| APFS 領域 | 580.2 GB（Windows からは `Unknown`） | 正常 |
| OCESP | 0.2 GB（partition 5, `System`） | 正常 |

### 実害 1: Windows の時計が9時間ずれる（RTC の UTC/現地時刻問題）

```
Windows が表示する現地時刻 : 2026-08-18 06:39   ← 実際は 15:39 JST
タイムゾーン                : Tokyo Standard Time (UTC+9)   ← 設定は正しい
RealTimeIsUniversal         : (未設定)                       ← 原因
w32time                     : Stopped                        ← 自己修復もしない
```

macOS は RTC を UTC で持つ。Windows は `RealTimeIsUniversal` が無いと **RTC を現地時刻として
読む**ため、06:39 UTC をそのまま JST として表示する。しかも `w32time` が停止していたので
NTP でも直らない。**macOS 側は NTP で自動的に直るので、ずれるのは Windows だけ。**

修正（適用済み・検証済み）:

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\TimeZoneInformation" `
  -Name RealTimeIsUniversal -PropertyType DWord -Value 1 -Force
Set-Service -Name w32time -StartupType Automatic
Start-Service -Name w32time
w32tm /config /syncfromflags:manual /manualpeerlist:"time.windows.com,0x9" /update
w32tm /resync /force
```

結果は秒単位で一致:

```
Windows  : 2026-08-18 15:42:45 JST
Mac mini : 2026-08-18 15:42:45 JST
```

**NTP 抜きで直った**（`RealTimeIsUniversal=1` が効いて RTC を UTC として読み直したため）。
これ自体が切り分けの裏取りになっている。なお最初の `w32tm /resync` は
「時刻データが利用できなかった」で失敗したが、2回目は exit 0。

### 実害 2: BIOS が Windows Update から配信されうる経路が開いていた

```
デバイス: System Firmware   UEFI\RES_{2F41F3C2-BB7C-4895-B9CD-621622C4DE2C}\0
保留中の更新: [Drivers] Intel - System - 3/19/2019 - 1912.12.0.1247
```

`System Firmware` デバイスの存在は、**UEFI カプセル更新の経路が生きている**という意味。
「BIOS 1.01 を絶対に維持する」という方針に対する実際のリスクである
（BIOS 3.02 は複数ユーザで起動不能を招いている）。

#### まず試して不十分だったもの

```powershell
# HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate
ExcludeWUDriversInQualityUpdate = 1
```

これは**品質更新（毎月の累積更新）にドライバを同梱させない**設定にすぎず、
ファームウェア更新そのものを禁止しない。適用後も Windows Update の検索 API
（`IsInstalled=0`）には `[Drivers] Intel - System` が残り続ける。
ただし**この検索結果は「サーバ上に存在する」ことしか示さない**ので、
効果判定の道具としても不適切だった。設定自体は有用なので残してある。

#### 実際に効く手段（適用済み）

Firmware デバイスクラスのインストール自体を禁止する。

```powershell
$FW = "{f2e7dd72-6468-4e36-b6f1-6488f42c1b52}"   # Firmware setup class
$R  = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions"
New-ItemProperty -Path $R -Name DenyDeviceClasses            -PropertyType DWord -Value 1
New-ItemProperty -Path $R -Name DenyDeviceClassesRetroactive -PropertyType DWord -Value 0
New-ItemProperty -Path "$R\DenyDeviceClasses" -Name "1" -PropertyType String -Value $FW
```

**GUID は推測ではなく実物で確認した:**

```
HKLM:\SYSTEM\CurrentControlSet\Control\Class\{f2e7dd72-...}  の Class 値 = "Firmware"
対象デバイス: System Firmware / UEFI\RES_{2F41F3C2-...}\0
```

`Retroactive = 0` にしてあるので、既にインストール済みのものには触れず、
**新規のインストール・更新のみを拒否**する。元に戻すには `Restrictions` キーを削除する。

### この3つの設定は「後片付け」の対象ではない

Windows 側の SSH 有効化（`sshd` / `administrators_authorized_keys` /
ネットワークカテゴリを Private に変更）は作業後に**戻す**対象だが、
本節の3つのレジストリ設定は**恒久的な修正なので戻さない**。混同しないこと。

| 設定 | 作業後 |
|---|---|
| `RealTimeIsUniversal = 1` | **残す** |
| `ExcludeWUDriversInQualityUpdate = 1` | **残す** |
| `DeviceInstall\Restrictions`（Firmware クラス拒否） | **残す** |
| `sshd` 有効化 / `administrators_authorized_keys` / NetworkCategory | 戻す |

### 手法メモ: `bin/rzps` 経由だと Windows のネイティブコマンド出力が化ける

`rzps` は `[Console]::OutputEncoding` を UTF-8 に固定するが、`w32tm` などの
ネイティブコマンドは OEM コードページ（日本語環境では cp932）でバイトを吐くため、
UTF-8 として解釈されて文字化けする。

```
  �R�}���h�͐������������܂����B      ← 実際は「コマンドは正常に完了しました。」
```

PowerShell のコマンドレット（`Get-CimInstance` 等）の出力は化けない。
**ネイティブコマンドは出力本文を読まず、`$LASTEXITCODE` で判定するのが確実。**

---

## ★★ 発見 16: USB ポートマップ — USBToolBox は `type` ではなく `selected` を見る（2026-08-18 16:05-16:20）

この PCH xHCI（`8086:9DED`、ACPI `\_SB.PCI0.XHC`）は Windows から見ると **18 ポート**
申告する。`XhciPortLimit` は Catalina 以前向けの手抜きなので `false` のまま、ポートを
明示宣言する方針を採った。

**ただし後から実測で判明したとおり、macOS はそのうち 12 ポートしか列挙しないので
15 ポート制限には当たっていない**（上の「macOS 側から見たポート番号」の表を参照）。
マップの実利は制限回避ではなく、**外部 USB-A が `UsbConnector 255`（内蔵扱い）に
なっているのを `3` に直すこと**と、未使用ポートを落とすこと。当初の見込みより効果は小さい。

### ポート構成は ACPI `_UPC` / `_PLD` から確定した（差し替え実験なしで）

USBToolBox の `usbdump` が Windows 側で読む `_UPC`/`_PLD` は、`user_connectable`
`type_c` `companion_info` `guessed` を返す。これで物理コネクタ配置が全部割れた。

| index | class | UsbConnector | 物理 | 根拠 |
|---|---|---|---|---|
| 1 | HS | 9 | USB-C | `type_c=True` `uc=True` `guessed=9`、companion=13 |
| 13 | SS | 9 | USB-C | `type_c=True` `uc=True` `guessed=9`、companion=1 |
| 2 | HS | 3 | USB-A ① | `uc=True` `guessed=3`、companion=14 |
| 14 | SS | 3 | USB-A ① | companion=2 |
| 3 | HS | 3 | USB-A ② | `uc=True` `guessed=3`、companion=15 |
| 15 | SS | 3 | USB-A ② | companion=3 |
| 6 | HS | 255 | 内蔵カメラ | `uc=False` `guessed=255`、`13D3:56D5` |
| 8 | HS | 255 | 内蔵キーボード + Chroma | `uc=False`、`1532:0239` |
| 10 | HS | 255 | 内蔵 Bluetooth | `uc=False`、`8087:0AAA` |

残る 9 ポート（4,5,7,9,11,12,16,17,18）は全て `user_connectable=False` かつ
デバイス履歴なし。**マップを適用すると載っていないポートは無効化される**ので、
これは意図的な除外。

UsbConnector の値: **3** = USB3 Type-A、**9** = Type-C（スイッチ付き）、
**255** = 内蔵/独自。

### ★ 罠: `usb.json` の `type` を書いても選択されない

`usb.json` を手で編集して 9 ポートに `type` を入れ、ツールに kext を作らせたところ、
**7 ポートしか出力されず、USB-C の 2 ポート（index 1 と 13）が落ちた。**

原因はツールのソースにある（[base.py:296](https://github.com/USBToolBox/tool/blob/master/base.py#L296)、
[base.py:591](https://github.com/USBToolBox/tool/blob/master/base.py#L591)）:

```python
# select_ports(): 採否は "selected" で決まる
if "selected" not in port:
    port["selected"] = bool(port["devices"])
    port["selected"] = port["selected"] or bool(self.get_companion_port(port)["devices"])

# build_kext():
for port in controller["ports"]:
    if not port["selected"]:
        continue
    ...
    "UsbConnector": port["type"] or port["guessed"],
```

つまり:

* 採否のフラグは **`selected`**。`type` は「採用されたポートの UsbConnector 値」
  にしか効かない（未指定なら `guessed` にフォールバック）。
* `selected` の自動判定は「そのポートにデバイスが挿さっている」か
  「companion に挿さっている」かだけ。
* → port 2,3,6,8,10 はデバイス有りで採用。port 14,15 は companion(2,3) 有りで採用。
  **port 1,13 は USB-C に何も挿していなかったので不採用。**

`usb.json` を手編集する場合は **`"selected": true` も書く**こと。`type` だけでは
足りない。（`"selected" not in port` のガードがあるので、明示すれば尊重される。）

もう一点: **ツールは kext 生成後に `usb.json` を書き戻し、`type` を全部 null に消す。**
生成後の `usb.json` は「何を作ったか」の証拠にならない（16383 → 18368 バイト、
mtime は kext より 10 秒後）。

### 出力の命名は連番で、実 index は `port` データ側にある

`HS01`…/`SS01`… はコントローラのポート列を上から数えた連番のラベルにすぎず、
実際のポート番号は `port` の 4 バイト **リトルエンディアン** に入る。
`port-count` は「採用したポートの最大 index」（ポート数ではない）。

```
HS01 port=<01000000> UsbConnector 9    ← index 1
HS06 port=<0a000000> UsbConnector 255  ← index 10
SS01 port=<0d000000> UsbConnector 9    ← index 13
port-count = <0f000000>                ← 最大 index 15
```

### 最終的に採った手段

ツールに作らせ直すには USB-C にデバイスを挿して再実行する必要があるが、判断材料は
ファームウェアの申告で既に揃っていたので、**全 9 ポート採用時にツールが出すはずの
Info.plist を同じロジックで組み直した**（index 順に連番、`port` は LE、`port-count`
は最大 index）。ツールが出した 7 ポート版は `/tmp/utb/UTBMap.kext.tool-7port` に残した。

### kext の投入順序

`UTBMap.kext` は **コードレス**（`Contents/Info.plist` のみ、`ExecutablePath` 空）で、
`OSBundleLibraries` に `com.dhinakg.USBToolBox.kext` を宣言する。よって
**`USBToolBox.kext` を先に注入しないと依存解決に失敗する**。`mkconfig.py` の
`KEXTS` はこの順で並べてある。

### `IONameMatch` が当たる根拠

生成された personality は `IONameMatch = "XHC"`（Windows 側 ACPI パス
`\_SB.PCI0.XHC` の末尾から導出）。macOS の ioreg でも同じノード名
`XHC@14000000` で見えている（発見 1 参照）ので一致する。**別名だった場合は
kext が当たらず無言で効かない**ので、名前依存であることは覚えておく。

### 未対応として明示しておく箇所

**TB3 コントローラ（`8086:15DB`、ACPI `RP09/PXSX`、4 ポート）はマップしていない。**

当初ここには「`IOThunderboltFamily` を Block しているうちは macOS から見えないため」と
書いたが**誤り**だった。適用後の実測で、このコントローラは `AppleUSBXHCIAR` として
**macOS からちゃんと見えており、4 ポート（`port` = 1, 2, 3, 4）を持っている**ことが
分かった。Block しているのは Thunderbolt のトンネル側（`IOThunderboltFamily` /
`AppleThunderboltNHI`）だけで、xHCI 機能は別 PCI デバイスとして生きている。

マップしていないコントローラは USBToolBox が一切触らないので、これらのポートは
無効化されず素のまま動く（`UsbConnector` プロパティも付かない）。つまり実害はないが、
**このマシンの USB-C ポートのうち TB3 側は型付けされないまま**である。型付けしたく
なったら、Windows で `8086:15db` 側のポートも `selected` にして personality を追加すること。

### 番号体系は ioreg で照合済み

マップに書いた 9 個の番号が macOS の `port` プロパティと同じ体系であることは、
適用前の ioreg で確認した（上の訂正節を参照）。`IONameMatch = "XHC"` も
`XHC@14` の `compatible = <"pci1a58,1000","pci8086,9ded","pciclass,0c0330","XHC">`
に含まれるので一致する。

config hash は `5623ac3bf71d6536` → `785d247bb29ba101`。

**なお最初の投入は起動失敗した。原因は kext の内容ではなく置き場所で、発見 17 を参照。**

---

## ★★★ 発見 17: 起動するのは `EFI/BOOT/` 側。`EFI/OC/` だけ更新しても効かない（2026-08-18 16:35-16:50）

USB マップを入れて再起動したら、カーネル読み込み中に止まった。

```
#[EB.LD.LKC|R.2] <"boot\System\Library\KernelCollections\BootKernelExtensions.kc">
OC: Plist Kexts\USBToolBox.kext\Contents\Info.plist is missing for injected kext USBToolBox.kext ()
Halting on critical error
```

### 原因: この ESP には OpenCore が**二重に**入っている

`EFI/BOOT/` は単なるフォールバックの `BOOTx64.efi` ではなく、**独立した完全な
OpenCore 一式**だった。

```
EFI/BOOT/BOOTx64.efi      872448 バイト  ← EFI/BOOT/OpenCore.efi と同一サイズ
EFI/BOOT/OpenCore.efi     872448
EFI/BOOT/config.plist                    ← ファームウェアが読むのはこっち
EFI/BOOT/config-vesa.plist
EFI/BOOT/ACPI/  Drivers/  Tools/  Resources/  Kexts/   ← 自前の Kexts を持つ
EFI/OC/OpenCore.efi       872448
EFI/OC/config.plist
EFI/OC/ACPI/  Drivers/  Tools/  Resources/  Kexts/
```

ファームウェアが起動するのは `EFI/BOOT/BOOTx64.efi` なので、**実際に読まれる設定は
`EFI/BOOT/config.plist`、実際に読まれる kext は `EFI/BOOT/Kexts/`**。

やってしまったのは:

* `config.plist` は `EFI/OC/` と `EFI/BOOT/` の**両方**に置いた
* kext は `EFI/OC/Kexts/` に**しか**置かなかった
* → 新しい設定が `USBToolBox.kext` を要求したが、`EFI/BOOT/Kexts/` には無い

エラーのパスが `Kexts\USBToolBox.kext\...` と**相対表記**なので、どちらの `Kexts` を
見て失敗したのかがログから判別できない。ここが分かりにくい。

### 誤診した仮説（記録として残す）

最初に「FAT への書き込みがディスクに落ちておらず、`shasum` の検証はページキャッシュ
から返っていた」と考えた。**外れ**。Windows から OCESP を読んだら、ファイルは正しい
サイズで存在し、SHA256 もローカルと完全一致していた。書き込みは成功しており、
置き場所が足りなかっただけ。

### 復旧経路: Windows は生きている

**OpenCore は macOS 起動時にしか kext を注入しないので、この halt が起きても Windows
は普通に起動する。** これが確実な復旧経路になる。もう一つの経路として
`EFI/OC/Tools/OpenShell.efi` がピッカーに出る設定になっている（`Misc > Tools`、
Enabled）。

Windows から OCESP を触る手順（`disk0s5`。**`disk0s2` は Windows の SYSTEM なので触らない**）:

```powershell
# diskpart は使わない（disk0 に Windows も macOS も載っている）。対象限定のコマンドレットだけ。
Add-PartitionAccessPath    -DiskNumber 0 -PartitionNumber 5 -AccessPath "Z:"
# ... 作業 ...
Remove-PartitionAccessPath -DiskNumber 0 -PartitionNumber 5 -AccessPath "Z:"
```

`Get-Partition -DiskNumber 0` でパーティション番号は GPT の順序と一致する
（1=Razer Recovery, 2=SYSTEM, 3=MSR, 4=C:, **5=OCESP**, 6=APFS, 7=WinRE）。

### ★ 以後の手順: ESP を更新したら必ず両方に入れ、config が要求する全 kext の実在を確認する

読まれる `EFI/BOOT/config.plist` を parse して、`Kernel > Add` の各エントリの
`BundlePath` + `PlistPath` / `ExecutablePath` が `EFI/BOOT/Kexts/` に実在するかを
機械的に検証する。今回の失敗はこれをやっていれば起動前に捕まえられた。

### 両ツリーのドリフト（2026-08-18 実測）

`EFI/OC`（530 ファイル）と `EFI/BOOT`（527 ファイル）を SHA256 で全件突き合わせた結果:

| 差分 | 内容 |
|---|---|
| `EFI/OC` のみ | `config-accel.plist` `config-bt.plist` `config-bt2.plist` `config-dpcd0A.plist` `config-fb3EA5.plist`（実験用の変種） |
| `EFI/BOOT` のみ | `BOOTx64.efi`、`.contentVisibility` |
| **内容が違う** | `config-vesa.plist`、**`Kexts/VirtualSMC.kext/Contents/MacOS/VirtualSMC`** |

**`VirtualSMC` のバイナリが OC と BOOT で違う。** 動いているのは BOOT 側。正常起動して
いるので今は触らないが、いつからずれたのか不明であり、今後 VirtualSMC を疑うときは
BOOT 側を見ること。

### ESP のバックアップ

`backup/ocesp-20260818-1629/ocesp-EFI-backup.tar.gz`（105,914,442 バイト、
SHA256 `7399663c3aa00ba92a3e923670bcc6b39a7208f741b3830066d9bd2a9cad937f`）。
`EFI` は 120MB あるので ESP 上ではなく Mac mini 側に退避した（ESP の空きは 71MB）。
中の `EFI/OC/config.plist` と `EFI/BOOT/config.plist` は既知良好の
`5623ac3bf71d6536…`。

### 副産物: 「OpenCore ログが 05:20:03 以降出ない」謎の解決

ログは出ていた。`uptime` が 3 分で、直前の macOS セッションは 05:20 から**連続稼働**
していたので、その間そもそも再起動が無かっただけ。今回の起動で
`opencore-2026-08-18-162144.txt` が生成されている。

---

## ★★ 発見 18: USB ポートマップは実機で検証済み（2026-08-18 17:00-17:05）

`EFI/BOOT/Kexts` にもコピーして再起動したら通った。**マップは意図通りに効いている。**

### ioreg の実測（9 ポート、期待値と完全一致）

```
node   port UsbConn  class                  device
HS01      1       9  AppleUSB20XHCIPort
HS02      2       3  AppleUSB20XHCIPort     GesturePoint Mouse Dongle 0x214e:0x0004
HS03      3       3  AppleUSB20XHCIPort     USB2.1 Hub 0x05e3:0x0610
HS04      6     255  AppleUSB20XHCIPort     Integrated Camera 0x13d3:0x56d5
HS05      8     255  AppleUSB20XHCIPort     Razer Blade 0x1532:0x0239
HS06     10     255  AppleUSB20XHCIPort     Bluetooth USB Host Controller 0x8087:0x0aaa
SS01     13       9  AppleUSB30XHCIPort
SS02     14       3  AppleUSB30XHCIPort
SS03     15       3  AppleUSB30XHCIPort     USB3.1 Hub 0x05e3:0x0626
port node count: 9
```

- ポート 7 / 9 / 16 は消えた（マップに載せていないポートは無効化される、の実証）
- 外部 USB-A は `255 → 3` に矯正された（これがこのマップの実質的な成果）
- Type-C の `9` は 1 / 13 とも維持
- `com.dhinakg.USBToolBox.kext (1.2.0)` がロード済み

### 適用後のハードウェア健全性

| 項目 | 結果 |
|---|---|
| 内蔵カメラ | `UVC Camera VendorID_5075 ProductID_22229`、Unique ID `0x1440000013d356d5`、480 Mb/s |
| Bluetooth | State On / Transport USB |
| en0 (Wi-Fi) | UP / RUNNING |
| en1 (USB Ethernet AX88179A `0b95:1790`) | UP / RUNNING、**5 Gb/s** |
| USB3.1 Hub `05e3:0626` | **5 Gb/s** |
| USB 関連エラーログ | なし |

SS 側が 5 Gb/s でリンクしているので、`UsbConnector 3` を付けたことで USB3 が
落ちるといった副作用は起きていない。

### トラックパッドのスタックも完備を確認

```
TPD0 <VoodooI2CDeviceNub>
 └ VoodooI2CHIDDevice
    └ IOHIDInterface
       └ VoodooI2CPrecisionTouchpadHIDEventDriver
          └ VoodooI2CMultitouchInterface  (AppleMultitouchDeviceUserClient)
          └ VoodooInputActuatorDevice
             └ AppleActuatorHIDEventDriver → AppleActuatorDevice
                → AppleActuatorDeviceUserClient
 └ TrackpointDevice → IOHIDPointingEventDevice → IOHIDEventDriver
IOHIDSystem (user client あり)
```

ハプティックまで含めて全段つながっている。ただし**外付けの GesturePoint マウス
ドングルが刺さっているので、ポインタが動いていてもそれがトラックパッド由来とは
限らない。** 人間がトラックパッドだけを触って確認する必要がある（未確認事項）。

### 副産物: `AllowSetDefault` は既に True

`Misc > Boot > AllowSetDefault` と `Misc > Security > AllowSetDefault` は両方
`True`（Timeout 8、ShowPicker True、PollAppleHotKeys True、HideAuxiliary False）。
ピッカーで macOS を既定にするのは **Ctrl+Enter を押すだけ**で、config の変更は不要。

### 副産物: OCESP は sudo 無しでマウントできる

`diskutil mount disk0s5` でユーザー `hiroki` のまま read-write でマウントできる。
sudo パスワードが要らないので、以後の ESP 更新はこの手順でよい。

---

## ★★★ 発見 19: `SSDT-DGPU-OFF` は最初から一度も動いていなかった（`_STA = Zero` が `_INI` を殺す）

「dGPU を切ったはずなのに MX150 がまだ列挙される」の原因が判明した。**私の SSDT の
バグ。** ACPI の仕様に真っ向から反する書き方をしていた。

### 症状

`SSDT-DGPU-OFF.aml` は正しくロードされている。OpenCore のログにも入っている：

```
00:840  OCA: Inserted table SSDT (54445353) (OEM 0046464F55504744) of 365 bytes into ACPI at index 31
```

`0046464F55504744` = `D G P U O F F \0`。ベンダ側の SSDT も揃っている
（index 22 = `SgRpSsdt`、index 24 = `OptTabl`）ので、`_OFF` / `HGOF` は存在する。

なのに dGPU は生きている：

```
+-o GFX0@0  <class IOPCIDevice, registered, matched, active>
    "compatible"  = <"pci1a58,1000","pci10de,1d10","pciclass,030200","PEGP","GFX0">
    "acpi-path"   = "IOACPIPlane:/_SB/PCI0@0/RP05@1c0004/PEGP@0"
    "IOPowerManagement" = {"CurrentPowerState"=2,"MaxPowerState"=3}
    └ IONDRVFramebuffer     ← フレームバッファまで生えている
```

そして決定的な手がかり:

```
$ ioreg -p IODeviceTree -l -w0 | grep -c RZDX
0
```

トリガー用に置いた `\_SB.RZDX` がデバイスツリーに存在しない。

### 原因

```asl
Device (\_SB.RZDX)
{
    Name (_HID, "RZDX0001")
    Name (_STA, Zero)          /* invisible to the OS; only _INI matters */
    Method (_INI, 0, NotSerialized) { \_SB.RZDG () }
}
```

このコメントの理屈が**完全に逆**だった。`_STA` が「非存在」を返すデバイスの `_INI` は
**そもそも評価されない**。ACPI 仕様の `_INI` の説明（ACPICA `nsinit.c` の
`AcpiNsInitOneDevice()` が仕様をそのまま引用している。Apple の
`AppleACPIPlatform` もこの系譜のコード）:

> "If the _STA method indicates that the device is not present, OSPM will not
> run the _INI and will not examine the children of the device for _INI methods"

実装もそのとおりで、`_STA` のビット 0（present）とビット 3（functioning）が
両方落ちていると `AE_CTRL_DEPTH` を返してサブツリーの走査を打ち切る:

```c
if (!(Flags & ACPI_STA_DEVICE_PRESENT)) {
    if (Flags & ACPI_STA_DEVICE_FUNCTIONING) {
        /* not present but functioning: _INI は走らせないが子は見る */
        return_ACPI_STATUS (AE_OK);
    } else {
        /* not present かつ not functioning: 子も見ない */
        return_ACPI_STATUS (AE_CTRL_DEPTH);
    }
}
/* ここまで来たら _INI を実行 */
```

`Zero` は present も functioning も落ちているので後者。**`RZDG()` は一度も
呼ばれていない。** ioreg に `RZDX` が無いのはその走査打ち切りの跡である。

### 修正

`_STA` を `0x0B`（present | enabled | functioning、"show in UI" の 0x04 のみ落とす）
にした。present が立っていれば `_INI` は走る。`_HID` `RZDX0001` に対応する
ドライバは macOS に無いので、ノードが見えても何も起きない。

```asl
    Name (_STA, 0x0B)
```

`iasl` で再コンパイル: 365 → **366 バイト**、
SHA256 `83c0a9eb623ba0bc1a59b87b94eb12096254aa1ed9222cea1ef911c709428599`。
`EFI/OC/ACPI/` と **`EFI/BOOT/ACPI/`（起動するのはこっち、発見 17 参照）** の両方に配置。
旧版は同じディレクトリに `SSDT-DGPU-OFF.aml.sta0` として残してある。

### 次の起動で見るべきこと

| 観測 | 意味 |
|---|---|
| `ioreg -p IODeviceTree \| grep RZDX` が**当たる** | `_STA` 修正が効き、namespace 走査が RZDX に到達した |
| `GFX0@0` / `pci10de,1d10` が**消える** | ベンダ `_OFF` が成功し dGPU が電源から落ちた（成功） |
| RZDX は出るが GFX0 も残る | `_INI` は走ったが `_OFF` が効かない別問題。`RZOF` のフォールバック `HGOF` 側を疑う |

### ★ 実機で検証済み: 成功（2026-08-18 17:34、修正後の初回起動）

上の表の 2 行目、狙ったとおりの結果になった。

```
=== RZDX in device tree? ===
    +-o RZDX  <class IOACPIPlatformDevice, id 0x1000001f4, registered, matched, active, busy 0 (3 ms)>

=== dGPU (pci10de,1d10 / GFX0) still enumerated? ===
GFX0 NOT IN IOService

=== any 10de PCI device left? ===
0
```

- `RZDX` が `IOACPIPlatformDevice` として出現 → `_STA` 修正で namespace 走査が
  到達し、`_INI` → `RZDG()` → `RZOF()` → ベンダ `_OFF()` が実行された
- **`pci10de` を持つ `IOPCIDevice` はゼロ。** MX150 は PCI から完全に消えた
- `system_profiler SPDisplaysDataType` も `Intel UHD Graphics 620`（`0x3ea5`）ただ 1 つ
- dGPU がいたルートポートは**空のブリッジだけが残った**:

```
+-o RP05@1C,4  <class IOPCIDevice, registered, matched, active>
| +-o IOPP     <class IOPCI2PCIBridge, registered, matched, active>     ← 子なし
```

副作用なし。内蔵ディスプレイは iGPU に付いたまま 1920×1080 / Metal 3 /
Connection Type Internal で正常（以前は `IONDRVFramebuffer` が dGPU 側にも
生えていたが、それも一緒に消えた）。新規のパニックレポートも無し
（最新は `Kernel-2026-08-18-011253.panic` で今回の作業より前のもの）。

**消費電力の実測はまだできていない。** 検証時は AC 接続・満充電で
`InstantAmperage = 0` だったため、バッテリ駆動での前後比較が取れない。
公称 3-5 W の節約が実際に出ているかは、バッテリ運用時に改めて測ること。

### 教訓

ダミーデバイスで `_INI` を撃つパターンでは **`_STA` を書かない**か、書くなら
present を立てる。`_STA = Zero` は「OS から隠す」ではなく「この枝を見るな」であり、
自分が仕込んだフックごと捨てられる。

**この手のバグは無症状で潜る。** SSDT がロードされていることと、その中身が
実行されたことは別問題で、OpenCore のログは前者しか教えてくれない。今後 SSDT を
足すときは、効果そのものを ioreg で確認できる観測点（今回なら `RZDX` ノードの有無）を
必ず用意すること。

---

## ★★★ 発見 20: ESP の FAT が壊れていた — 起動中の `VirtualSMC` に 2 KB のゴミが入っていた

発見 17 で「`VirtualSMC` のバイナリが `EFI/OC` と `EFI/BOOT` で違う。動いているのは
BOOT 側。今は触らない」と書いて放置した差分の正体を調べたら、**BOOT 側が壊れていた**。

### どちらが正しいかは一発で決まった

| 場所 | SHA256 (先頭) |
|---|---|
| ESP `EFI/OC/Kexts/VirtualSMC.kext` | `865f736ae87654ee` |
| ESP `EFI/BOOT/Kexts/VirtualSMC.kext` | `856a9044043ac1ed` |
| **公式リリース** `downloads/x_VirtualSMC-1.3.7-RELEASE/` | **`865f736ae87654ee`** |
| リポジトリ内の他 23 コピー全部 | `865f736ae87654ee` |

サイズ（245408）も `CFBundleVersion`（1.3.7）も mtime も同一なのに中身が違う。
DEBUG ビルドとの取り違えならサイズが変わるので、それでもない。**BOOT 側だけが
どこにも一致しない孤児**だった。

### 壊れ方

```
$ cmp -l OC/.../VirtualSMC BOOT/.../VirtualSMC | awk '...'
first: 145409  last: 147456  span: 2048  count: 2045
```

**ちょうど 2048 バイト（0x23800–0x23FFF、512 バイト境界揃い）だけが化けている。**
中身を見ると:

```
OC   : 830201807deb037204c645eb0283ec0c8d45eb6a00688800000068756938206a
BOOT : 252c24242424252c252c252c252c242424242424242491a1140b252c252c252c
```

OC 側は素直な x86-64 コード（`68 75 69 38` = SMC のキー型 `ui8` のリテラルが見える）。
BOOT 側は `25 2c 24 24 24 24` の繰り返しで、コードでもデータでもない。
**1 クラスタ分がまるごと別の内容で上書きされた FAT レベルの破損。**

### つまり、これまで起動していた macOS は

**`__TEXT` の真ん中に 2 KB の穴が空いた `VirtualSMC` を読み込んで動いていた。**
`kmutil showloaded` には `as.vit9696.VirtualSMC (1.3.7)` として正常にロードされて
見える。Mach-O のヘッダ構造は無傷なのでカーネルは受け入れるし、OpenCore は kext の
内容を検証しない。壊れた領域が呼ばれない冷たい関数だったので無症状だった、というだけ。
**そこに実行が届いた瞬間にパニックする爆弾**であり、SMC キー・バッテリ・スリープ
まわりの原因不明の挙動を疑うとき、この線を排除できていなかった。

### ESP 全体の健全性を確認した

破損が他にもあるかを、ESP の全 `.efi` / `.aml` / `Kexts/*` をローカルの既知良好コピー
（`build/` 以下 + `downloads/` の公式リリース）とハッシュ照合して確認した：

```
ESP files checked: 127
not matching ANY local copy: 1
  856a9044043ac1ed  BOOT/Kexts/VirtualSMC.kext/Contents/MacOS/VirtualSMC
```

**127 個中 126 個はバイト一致。破損はこの 1 ファイルだけ。**
`config*.plist` 7 個も `plutil -lint` 全部 OK（`config-vesa.plist` の OC/BOOT 差分は
壊れではなく、単に古い実験用変種が残っているだけ）。

### 修正

公式リリースのバイナリを `EFI/BOOT/Kexts/VirtualSMC.kext/Contents/MacOS/VirtualSMC`
に上書きし、`865f736ae87654ee…` で OC 側と一致することを確認。壊れていた方は
フォレンジック用に `backup/esp-corruption-20260818/VirtualSMC.BOOT.corrupt`
（SHA256 `856a9044043ac1ed2a3e87c4bf71e7ce56adc539464bb9d003ebc9e03b5fa08f`）へ退避し、
ESP からは削除した（kext バンドルの中に余計なファイルを置いたままにしない）。

### 原因の見当と、今後の運用

FAT32 はジャーナルを持たない。このマシンは**発見 10 の黒画面のせいで電源ボタン強制断を
何十回もやっている**ので、その中の一回が、書き込み途中の ESP のクラスタを飛ばしたと
考えるのが自然。断定はできないが、ESP は書き込み後に必ず

```
diskutil unmount disk0s5
```

してマウントしっぱなしにしないこと。マウントされた FAT を抱えたまま電源を落とすのが
一番危ない。

**そして重要なのは、この破損は 1 バイトも症状を出さなかったという点。** ESP 上の
ブートローダとカーネル拡張は、ローカルの既知良好コピーとハッシュ照合しない限り
壊れているかどうか分からない。今後 ESP を触ったら上の 127 ファイル照合を回すこと。

---

## 補足: トラックパッドは実機で動作確認済み（ドライバ側の裏も取れた）

ユーザーが実機で確認、ポインタが動く。ドライバ側の裏付けも取れた：

- `VoodooI2CNativeEngine` が `IOMatchedAtBoot = Yes` で起動時にマッチ
- その上に `VoodooInput`（`me.kishorprins.VoodooInput`）が `IOPropertyMatch
  {"VoodooInputSupported"=Yes}` で乗っている
- デジタイザの実寸をデバイスから読めている:
  `Physical Max X = 10750` / `Physical Max Y = 7140`（= 107.5 × 71.4 mm、
  Blade Stealth 13 のタッチパッド実寸と一致）、
  `Logical Max X = 1291` / `Logical Max Y = 857`
- `VendorID = 1739`（0x06CB = Synaptics）、`ProductID = 52643`
- `com.apple.AppleMultitouchTrackpad` の設定ドメインが生成済み（`version = 12`、
  4本指・5本指ジェスチャのキーまで揃っている）→ macOS が**本物の
  Apple 式マルチタッチトラックパッドとして扱っている**

### ただし既定値が macOS の初期値のまま

```
Clicking = 0                 ← タップでクリックが OFF（物理押し込みのみ）
Dragging = 0
TrackpadThreeFingerDrag = 0
TrackpadThreeFingerTapGesture = 0
ActuationStrength = 0        ← クリック音なし
USBMouseStopsTrackpad = 0
```

`Clicking = 0` は Apple の実機と同じ初期値なので不具合ではないが、日常使いでは
システム設定 > トラックパッド でオンにしたくなるはず。

### ★ 深く押し込んだクリックが通らない → Force Click を切る（2026-08-18 22:40 解決）

「物理的に深く押し込んだとき、軽くタップしたのと同じようにクリックとして
認識してほしい」という症状。原因は **Force Click（強めのクリック）が有効**だったこと。

VoodooInput は Magic Trackpad 2 としてエミュレートするので、macOS は圧力を
解釈して「第 2 ディテント到達 = Force Click」と判定し、通常クリックではなく
辞書引き / QuickLook 側の動作へ回す。**この機械には圧力センサも触覚エンジンも
無いので、この解釈は常に誤り。**

```bash
defaults write com.apple.AppleMultitouchTrackpad ForceSuppressed -bool true
defaults write com.apple.AppleMultitouchTrackpad ActuateDetents -int 0
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad ForceSuppressed -bool true
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad ActuateDetents -int 0
defaults write -g com.apple.trackpad.forceClick -bool false
```

| キー | 前 | 後 |
|---|---|---|
| `ForceSuppressed` | 0 | **1** |
| `ActuateDetents` | 1 | **0** |
| `com.apple.trackpad.forceClick` | 1 | **0** |

実機で確認済み。GUI では システム設定 > トラックパッド >
「強めのクリックと触覚フィードバック」のチェックを外すのと同じ。
元の値に戻すだけで完全に可逆。

---

## ★★ 発見 21: CPU 電力管理の実測 — XCPM は正常、ただし単スレッドが 4.1 GHz で天井

CPUFriend を入れるべきか判断するために、まず現状を測った。**結論: 入れない。**
4.1 GHz の天井は OS 側の周波数ベクタではなく**ハードウェアの turbo ratio 上限**で、
CPUFriend の届く範囲に原因が無いことが `powermetrics` で確定した（後述）。
電力管理そのものは XCPM も C-state も持続クロックも健全。

### XCPM は正しく動いている

`SSDT-PLUG` は効いていて `X86PlatformPlugin` が `AppleACPICPU` に付いている。
カーネルログも `IOPPF: XCPM mode`。`sysctl machdep.xcpm` の要点:

| キー | 値 | 意味 |
|---|---|---|
| `mode` | 1 | XCPM 有効 |
| `hard_plimit_max_100mhz_ratio` | **46** | 上限 4.6 GHz = i7-8565U の定格 max turbo と一致 |
| `hard_plimit_min_100mhz_ratio` | 4 | 下限 400 MHz |
| `lpm_plimit_max_100mhz_ratio` | 26 | 低電力モード時 2.6 GHz |
| `bootpst` | 46 | 起動時 P-state |
| **`vectors_loaded_count`** | **1** | 周波数ベクタは 1 本ロード済み |
| `ratio_changes_total` | 206954 → 290253 | P-state 遷移が実際に大量に起きている |
| `cpu_thermal_level` | 0 | 熱による制限は掛かっていない |

つまり「電力管理が死んでいる」類の問題は**無い**。

### 実クロックの測り方（sudo 不要）

`sudo` パスワードが無いので `powermetrics` が使えない。代わりに
**依存連鎖した `addq` は 1 サイクル 1 個**という性質を使って、実効クロックを直接測る
C プログラムを書いた（`/tmp/clk.c`）:

```c
__asm__ __volatile__("addq $1, %0\n\t" /* ... 10 個直列 ... */ : "+r"(x));
```

最初は素の C ループで書いたら `-O1` でも畳み込まれて **32280 GHz** と出た。
インラインアセンブラで依存関係を強制して解決。加算回数 ÷ 経過秒 = 実効 GHz。

### 実測結果

| 条件 | 実効クロック | 定格 |
|---|---|---|
| 単スレッド 0.4 秒バースト ×4 | 3.99 / 4.08 / 4.08 / **4.09 GHz** | 4.6 GHz (1C max turbo) |
| 単スレッド 3 秒 | 4.08 / 4.10 GHz | 〃 |
| 単スレッド 12 秒 | **4.10 GHz** | 〃 |
| 8 スレッド 12 秒（各スレッド） | **3.41 〜 3.43 GHz** | 4.1 GHz (all-core) |

- **全コア 3.42 GHz を 12 秒維持は、15W の U シリーズとしては極めて良い。**
  Razer のファームウェアが PL1 を定格 15W より高く設定していると考えられる。
  この負荷後でも `cpu_thermal_level` は 0。
- 一方**単スレッドは 4.10 GHz でぴったり天井**。0.4 秒バーストでも 12 秒でも
  同じ値なので、**熱や PL1 による減衰ではなく硬い比率上限**（ratio 41）。
  定格 4.6 GHz に対して約 11% 低い。

### ★ なぜ 41 で止まるのか — 実測で決着（両方の仮説がハズレ）

ここには当初「有力候補が 2 つ」と書いていた。(1) 周波数ベクタ / EPP のミスマッチ
（CPUFriend で直る）、(2) 他コアが深い C-state に入らずマルチコア turbo 比率が
適用されている（CPUFriend では直らない）。ユーザに `sudo /tmp/pmcap.sh` を
走らせて `powermetrics --samplers cpu_power` を採ったところ、**どちらでもなかった**。

| 状態 | パッケージ電力 | 平均周波数 | ハードウェアが報告する制限理由 | Avg Num Cores Active |
|---|---|---|---|---|
| アイドル ×3 | 3.65 〜 3.82 W | 2131 〜 2144 MHz | （なし） | 0.41 〜 0.43 |
| 単スレッド ×5 | **11.31 〜 11.41 W** | 4099 〜 4115 MHz | `CPU LIMIT PL2_PL3` (5/5) + **`CPU LIMIT MAX_TURBO_LIMIT` (4/5)** | 1.18 〜 1.24 |
| 全 8 スレッド ×5 | **24.92 〜 24.95 W** | 3896 〜 3909 MHz | `CPU LIMIT PL2_PL3` (5/5) + `ICCMAX/PL4/OTHER` (2/5) | 3.97 〜 3.98 |

**仮説 (2) は死んだ。** 単スレッド走行中のコア別 C-state residency は
Core0 22.21%（うち C7 21.95%）/ Core1 78.97%（C7 78.84%）/
Core2 55.67%（C7 55.66%）/ Core3 53.21%（C7 53.21%）。
**遊んでいるコアはちゃんと C7 に落ちている。**

**仮説 (1) も死んだ。** `MAX_TURBO_LIMIT` は `IA_PERF_LIMIT_REASONS` 由来の
**ハードウェア側**のフラグで、「アクティブコア数に対する turbo ratio 上限に
当たっている」という意味。そして電力には余裕がある — 単スレッド時の
パッケージ電力は 11.4 W で、全コア時に持続できている約 25 W の半分以下。
**電力が余っているのにクロックが上がらないなら、上限は比率表そのもの。**
周波数ベクタ（= OS 側の要求値）をいくら差し替えても、ハードウェアが
「その比率は出せない」と言っている壁は動かない。

つまり **Razer のファームウェアが `MSR_TURBO_RATIO_LIMIT` を 41 に設定している**
（定格の 1C=46 ではなく、全コア数で 41 でフラットに刻んでいる）と考えるのが
一番素直。スレッド数を振った実測もそれを裏付ける:

| スレッド数 | 1 | 2 | 3 | 4 | 6 | 8 |
|---|---|---|---|---|---|---|
| 各スレッドの実効クロック | 4.07 | 4.07 | 4.04 | 4.00 | 3.70 | 3.42 GHz |

1〜2 スレッドが**完全に同じ 4.07** で、そこから電力に応じて滑らかに落ちる。
1C だけ特別に高い（46）という段差がどこにも無い。

なお `PL2_PL3` が単スレッド 11.4 W でも立つのは、PL3/PL4 が ms オーダーの
短窓リミットで、バースト時に一瞬当たった sticky ビットが 1 秒のサンプル窓に
拾われるため。持続的な制限は全コア時の約 25 W 側。

### 持続負荷でも落ちない（PL1 ロールオフ・熱ダレなし）

7 本のスピナー + 測定スレッド = 8 スレッドを 110 秒連続で回し、途中 4 回測った:

| 経過 | +0s | +30s | +60s | +90s |
|---|---|---|---|---|
| 実効クロック | 3.44 | 3.43 | 3.43 | 3.44 GHz |

**100 秒回しても 1% も落ちない。** 終了後も `cpu_thermal_level` は 0。
つまり約 25 W は PL2 の短期ブーストではなく**持続的に維持できている電力枠**で、
熱設計も足りている。15W 定格のチップで全コア 3.43 GHz 無限持続は上出来。

### 移植元プロファイルが無い、という壁（参考・以下は上の結論により無意味になった）

CPUFriend は他機種の周波数ベクタを借りてくる仕組み。では 4.6 GHz を知っている
プロファイルはどれか。76 枚の board plist のうち `Frequencies` に 4600 を持つのは
4 枚だけで、board-id → 機種は acidanthera の `OcMacInfoLib/AutoGenerated.c` で照合した:

| board-id | 機種 | `Frequencies` キー | TDP クラス |
|---|---|---|---|
| `Mac-1E7E29AD0135F9BC` | MacBookPro15,3 | 4100 4300 4500 **4600** 4800 5000 | 45W H |
| `Mac-937A206F2EE63C01` | MacBookPro15,1 | 4100 4300 4500 **4600** 4800 5000 | 45W H |
| `Mac-63001698E7A34814` | iMac19,2 | 3600 4100 **4600** | 65W デスクトップ |
| `Mac-AA95B1DDAB278B95` | iMac19,1 | 4100 4300 **4600** 5000 | 95W デスクトップ |

**15W の U シリーズは 1 台も無い。** 現状の MacBookPro15,2 は
`Frequencies = {3800:0, 4100:1, 4200:1, 4500:2, 4700:2}` で、
これは 28W の i5-8259U / i7-8559U 等の turbo 値。うちの 4600 はキーに無い
（ただし 3 本のベクタは中身が全部異なるので、どれが選ばれたかは効く）。

つまり CPUFriend でやれるのは「45W か 65W か 95W 機のプロファイルを 15W の
チップに履かせる」ことで、**単スレッド約 11% と引き換えに発熱とファンと
バッテリを悪化させる**取引になる。しかも `powermetrics` が使えないので
消費電力側の代償を測れない。

### ★ 判断: CPUFriend は入れない（この問題には効かない）

実測が出た時点で、これは**判断の問題ではなく事実の問題**になった。

- CPUFriend にできるのは `X86PlatformPlugin` が読む
  `IOPlatformPowerProfile`（`Frequencies` / `FrequencyVectors` / `CPUFloor` /
  `BoostLimit`）の差し替え、つまり **OS 側の「要求値」を変えること**だけ。
- 4.1 GHz の天井は **ハードウェアが `MAX_TURBO_LIMIT` として拒否している**もの。
  要求値を 46 にしても PCU が 41 しか出さない。
- しかも電力枠には 13 W 以上の余裕があるので、「電力を余らせているから
  上がらない」でもない。

**よって CPUFriend をこの目的で入れるのは無意味。** 45W / 65W / 95W 機の
プロファイルを 15W チップに履かせるリスクだけを負って、リターンはゼロ。

理屈上この比率上限を動かせるのは `MSR_TURBO_RATIO_LIMIT`(0x1AD) への書き込み
（CPUTune 等）だが、(a) このレジスタは通常 BIOS がロックしていて書けない、
(b) 書けたとして未検証領域、(c) **BIOS は 1.01 のまま触らない**という本プロジェクトの
大原則がある。**得られるのは単スレッド約 11%。追わない。**

### 副産物: 電力管理は総合的に健全

| 項目 | 実測 | 評価 |
|---|---|---|
| アイドル パッケージ電力 | 3.65 〜 3.82 W | 妥当 |
| 全コア持続 | 24.95 W / 3.43 GHz / 100 秒以上フラット | 15W 定格として上出来 |
| `cpu_thermal_level` | 常に 0 | 熱ダレなし |
| コア別 C7 residency | 21.9 〜 78.8%（アイドルコア） | 深い C-state 動作 |
| `ratio_changes_total` | 290k → 783k と増え続ける | P-state 遷移が生きている |

唯一の気になる点は**パッケージ C-state が C2（約 10%）と C3（約 9.5%）にしか
入らず、PC6 〜 PC10 が全状態で 0.00%** だったこと。ただしこの測定は
**USB Ethernet 経由の SSH セッションが張られたまま**行っており、
USB Ethernet + xHCI + PCIe リンクがアクティブなだけで深いパッケージ C-state は
入れない。**この数字はアイドル電力の評価には使えない**（測定条件が汚染されている）。
きちんと測るなら SSH を切った状態で `nohup` + `sleep` した採取スクリプトが必要。
バッテリ持ちを詰める段になったら再測定する。

（参考: 測定時の `Boot arguments: -v debug=0x100 keepsyms=1 alcid=30 -igfxblt
-btlfxboardid` / `EFI version: 2094.80.5.0.0`）

---

## ★★ 発見 22: 輝度キーは「キーが死んでいる」のではなく macOS 側に受け手が居ない（2026-08-18 22:40-23:00 解決）

輝度の上下キーが無反応だった。結論から書くと、**キーは完全に正常で標準どおりの
usage を送っており**、壊れていたのは受け手側。ACPI 経路も `hidutil` も使えず、
最終的に Consumer usage を拾って `bklt` を叩く 150 行の常駐 (`tools/brtd/`) で解決した。

### 手順1: キーが macOS に届いているのか（`HIDIdleTime` 法）

まず `log stream` で HID イベントを捕まえようとしたが、`kernel` / `WindowServer` /
`hidd` / `com.apple.iohid` を `--info --debug` で 32 秒張っても**キー押下は 1 行も出ない**。
動作している音量キーですら 0 ヒットだったので、この計測方法自体が使えないと判断した。

代わりに `IOHIDSystem` の `HIDIdleTime`（HID 入力があるとゼロに戻る）を 0.3 秒間隔で
ポーリングした。これは権限も特別なツールも要らない。

```
22:45:35〜47  67.25 → 78.78 s   何も押していない（正常に増加）
22:45:47      0.12 s            ★ 輝度ダウンを押した瞬間に崩落
22:45:47〜    0.01〜0.92 s       連打がすべてイベントとして届いている
```

→ **キーは届いている。** 「EC がキーを出していない」説はこの時点で消えた。

### 手順2: 何の usage を送っているのか（`hidutil` 文字割り当て法）

`ReportDescriptor` を ioreg から取り出して解析すると、Razer Blade キーボード
(VendorID 5426 = 0x1532, ProductID 569) は 3 インターフェイス構成で、
インターフェイス 1 が Consumer ページ全域（Usage Min 0x00 〜 Max 0x23C の配列）を
宣言していた。つまり「送れる能力がある」ことしか分からない。

そこで候補 usage をそれぞれ別の英字に `hidutil` で割り当て、テキストエディットで
何の文字が出るかで同定した。**この方法の要点は対照実験を混ぜること**:
動作している音量ダウン (Consumer 0xEA) を `z` に割り当てておけば、
`z` が出た時点で「再マッピング機構は生きている」が確定し、
輝度キーで文字が出ない場合の解釈が一意に決まる。

結果は `zba`:

| 押したキー | 出た文字 | 正体 |
|---|---|---|
| 音量ダウン | `z` | Consumer 0xEA ← **対照実験成功** |
| 輝度ダウン | `b` | **Consumer 0x70 = Display Brightness Decrement** |
| 輝度アップ | `a` | **Consumer 0x6F = Display Brightness Increment** |

→ **キーは標準の輝度 usage を正しく送っている。**

### 手順3: 受け手が無いことの確認

**(a) `hidutil` では直せない。** 宛先を AppleVendorTopCase 0x04/0x05 にしても、
Keyboard F14 にしても `bklt` は 1 も動かなかった。src 側は同じ機構で
確実に動いている（`z` が出た）ので、**`hidutil` の宛先として輝度アクションは
生成できない**と結論。判定は動作中の音量キーを輝度宛先に転送して 32 秒間
`bklt` をポーリングし、値が 0.6000 のまま 74 サンプル動かないことで確定させた。

**(b) ACPI 経路は存在しない。** DSDT（60432 行）を調べると:

- `Method (BRTN, 1, Serialized)` は**定義されているだけで、どこからも呼ばれていない**
  （`grep BRTN` の結果が定義行 1 件のみ）
- EC の `_Q13`〜`_Q32` / `_QD1`〜`_QD5` に輝度通知は無い。
  `Notify(..., 0x86)` は 4 件あるが全部 DPTF 熱制御 (`IETM` / `TPWR`)、
  `Notify(..., 0x87)` は **0 件**

→ **`BrightnessKeys.kext` を入れても完全に無反応**。これは ACPI notify 0x86/0x87 を
フックする kext なので、そのイベントが存在しない本機では意味がない。
**無駄な kext 追加と再起動を 1 回節約できた。**

**(c) 輝度制御そのものは正常。** `IODisplaySetFloatParameter(svc, "bklt", 0.35)` が
`kr=0x0` を返し、ioreg の `bklt` が 65535 → 22937 に動き、画面も実際に暗くなった。
`PNLF` は `_STA=11` / `compatible=<"backlight">` で認識済み、`-igfxblt` も効いている。
つまり土台は完成していて、**足りないのは「キーイベント → この API」の結線だけ**だった。

### 解決: `tools/brtd/`

150 行の C。`IOHIDManager` で Consumer 0x6F/0x70 を拾い、`bklt` を Apple と同じ
1/16 刻みで動かす。`tools/brtd/install.sh` を**実機で**実行すればビルドから
LaunchAgent 登録まで済む。

**権限の範囲を意図的に絞ってある。** 入力監視は全キー入力が見える権限なので、
HID スタックに渡してもらう対象を二重に狭めた:

- `IOHIDManagerSetDeviceMatching` → VendorID 0x1532 のみ（内蔵キーボードだけ）
- `IOHIDManagerSetInputValueMatching` → UsagePage 0x0C のみ（メディアキーだけ）

文字キーは UsagePage 0x07 なので、**原理的にコールバックへ到達しない**。

### ★ 罠: `IOHIDManagerOpen` は許可が無くても成功を返す

これで 30 分ほど溶かした。TCC（入力監視）が未許可の状態でも:

```
IOHIDCheckAccess(ListenEvent) = 2   (0=granted 1=denied 2=unknown)
IOHIDManagerOpen = 0x0 OK
listening: VendorID 0x1532, UsagePage 0x0c only
```

**open は通り、値だけが黙って捨てられる。** `IOHIDCheckAccess` も ad-hoc 署名の
バイナリでは許可後も 2 (unknown) を返し続けるので、**どちらも判定に使えない**。
唯一信頼できるのは「イベントが実際に来るか」。ここでも対照実験が効く:
UsagePage 0x0C でフィルタしているので、**動作している音量キーを押せばログに出る**。
出るなら TCC は通っている、出ないなら通っていない。

なお SSH セッションから起動したプロセスは `0xe00002e2`
(`kIOReturnNotPermitted`) で明示的に失敗し、許可ダイアログも出せない。
TCC が許可を与えられるのは GUI（Aqua）セッションだけなので、
**LaunchAgent を `launchctl bootstrap gui/$(id -u)` で登録する必要がある**。
許可自体は システム設定 > プライバシーとセキュリティ > 入力監視 で手動投入した。

### 実測（2026-08-18 22:5x）

```
EVENT page=0x0c usage=0x70 value=1
brightness 1.0000 -> 0.9375 (kr=0x0)
EVENT page=0x0c usage=0x70 value=1
brightness 0.9375 -> 0.8750 (kr=0x0)
EVENT page=0x0c usage=0x70 value=1
brightness 0.8750 -> 0.8125 (kr=0x0)
EVENT page=0x0c usage=0xea value=1        ← 音量ダウン（対照実験）
```

`bklt` は 53247 / 65535 = 0.8125 で一致。上下どちらも実機で画面が追従することを確認済み。

配列要素由来の `usage=0xffffffff value=112` も同時に届くが、
判定は `usage == 0x6F / 0x70` で行っているので**1 押下 1 ステップ**になる。

### 未実装 / 既知の限界

- **輝度 OSD（画面中央のインジケータ）は出ない。** 出すには非公開の
  `DisplayServices` / `CoreDisplay` を叩く必要がある。動作自体には影響しない。
- Shift+Option の 1/64 微調整は未対応（Apple 実機は対応）。
- **再ビルドすると ad-hoc 署名の cdhash が変わり、入力監視の許可が失効する。**
  ビルドし直したらトグルを入れ直すこと。
- `-v` を付けると Consumer キーの押下がすべて `/tmp/brtd.out` に記録される。
  切り分けが終わったら外すこと（現在は外してある）。

### 教訓

**「効かない」を「壊れている」と読み替えないこと。** このキーは 3 段階すべてで
正常だった（EC が出す → HID で届く → 標準の usage である）。
壊れていたのは 4 段目の受け手だけで、`HIDIdleTime` と文字割り当てという
権限の要らない 2 つの計測で、そこまで正確に切り分けられた。
`log show` が空だったのを「イベントが無い」と読んでいたら、
`BrightnessKeys.kext` を入れて再起動して、また空振りしていた。

## ★★ 発見 23: 外部ディスプレイは動く。左 USB-C のみで、右は BIOS 側の帰結（2026-08-18 23:20 実測）

Reddit の同型機報告（発見 6 の対照表）で **6 年間誰も回答していない**「外部ディスプレイを
挿すとフリーズ」は、**この構成では発生しない**。実機で拡張デスクトップが成立した。

### 実測: 左 USB-C

```
Display:                          HDMI:
  1920 x 1080 @ 60.00Hz             1920 x 1080 @ 60.00Hz
  30-Bit Color (ARGB2101010)        30-Bit Color (ARGB2101010)
  Main Display: Yes                 Adapter Type: Thunderbolt/DisplayPort
  Mirror: Off                       Mirror: Off
  Connection Type: Internal         Online: Yes
```

`HDMI` という名前はアダプタが申告したもので、経路は DP alt mode である
（`Adapter Type: Thunderbolt/DisplayPort`）。**内蔵パネルと同時に、両方 30bit で、
ミラーではなく拡張**として出た。フリーズも再起動もパニックも無し。

フレームバッファの割り当ても筋が通っている:

| ノード | `IOFBCurrentPixelClock` | 実体 |
|---|---|---|
| `AppleIntelFramebuffer@0` | 138.5 MHz | 内蔵 eDP パネル |
| `AppleIntelFramebuffer@1` | **148.5 MHz** | **左 USB-C（1920x1080@60 の CEA 値）** |
| `AppleIntelFramebuffer@2` | （無し） | 未使用 = TB3 側 |

DP リンクのやり取りも正常で、`IG:: DoDisplayPortTransaction:245 Data 8 / 8`
のように**要求バイト数と転送バイト数が一致**している。`IG::` のエラー/失敗行は 0 件。

### ★ 予測が実測で裏付けられた: `connector-type` パッチは本当に不要だった

発見 6 で「本機は HDMI が無く USB-C×2 なので既定の DP×2 と一致する。
`framebuffer-con1/con2-type` は no-op だから積まない」と**推論で削った**判断が、
ここで実測に変わった。パッチ無しで DP が素直に出た。

### 右 USB-C が映らないのは故障ではなく設定の帰結

右は Thunderbolt 3 ポートで、**DP alt mode の mux は Alpine Ridge (JHL6240) の中にある**。
`docs/bios-settings.md` で **Thunderbolt = Disabled** にしているので、そのコントローラは
電源が落ちている → mux が動かない → 映像が出ない。iGPU の DDI 直結である左とは経路が違う。

つまり `AppleIntelFramebuffer@2`（DP connector 2 本目）は macOS 側に存在しているが、
**その先の物理経路が BIOS で切られている**状態。macOS の設定ミスではない。

### 右を生かす場合の実験と、その根拠

BIOS で Thunderbolt = Enabled に戻す。**`AppleThunderboltNHI` の Block は外さない。**

元のハードリセット（発見なし・`Previous shutdown cause: 5`、2 回再現）は
「BIOS で Disabled なのに PCI には列挙され、レジスタが全部 `0xffffffff` を返す
**死んだデバイス**に対して NHI が DMA リングを確保しようとした」ことが原因だった:

```
AppleThunderboltNHITransmitRingManager::allocateTransmitRing Flags: 0x1
AppleThunderboltNHIReceiveRingManager::allocateReceiveRing  Flags: 0x1
```

Block が入っている限り **NHI はそもそもロードされない**ので、この経路は原理的に
発火しない。そして DP alt mode の mux はコントローラのファームウェア/ハードウェア側で
処理されるため、**OS の Thunderbolt ドライバを必要としない**。だから
「TB3 に電源を入れる + NHI は載せない」で右ポートの映像だけ得られる可能性がある。

**未検証。** 期待できる利点は右ポートの映像と、DP connector が 2 本あるので
**外部 2 画面**。リスクは起動不良だが、**BIOS 内で Disabled に戻すだけで完全に戻せる**
（ESP を書き換えないので OpenCore 側の revert 作業は不要）。

### ★ 外部ディスプレイを繋いだままの S3 も通る（2026-08-18 23:30 実測）

一般に壊れやすい箇所だが、無事だった。**しかもバッテリー駆動での初のスリープ試験**でもある
（発見 10b の 21:44 と 22:24 はいずれも AC 接続だった）。

```
23:30:23  Sleep  'Software Sleep pid=23835'  TCPKeepAlive=active  Using Batt (Charge:79%)  46 secs
23:31:09  Wake   Wake from Normal Sleep [CDNVA] : due to XDCI/UserActivity  Using BATT (79%)
```

復帰後の検証:

| 確認項目 | 結果 |
|---|---|
| `kern.boottime` | **19:17:50 のまま** = 再起動していない |
| パニックファイル | 新規ゼロ（既存は 00:56〜01:12 で、この起動より前） |
| 内蔵 + 外部 | **両方** 1920x1080@60 / 30bit で復帰 |
| フレームバッファ | `@0` 138.5MHz + `@1` 148.5MHz、スリープ前と同一 |
| `brtd`（輝度キー） | **pid 23602 のまま** = 再起動もクラッシュもせず生存 |

`Wake reason` が `XDCI` なのは発見 10b で誤読と確定済みの見え方で、実際の復帰要因は
`UserActivity`（キー押下）である。

### ★ 罠: 復帰時の `[IGFB][ERROR]` は正常な遷移ノイズ

復帰の瞬間、23:31:09〜11 の 2 秒間だけエラー行が並ぶ:

```
[IGFB][LOG][GTPM_SLEEPWAKE] [Transition_wake] Invalidate PIPE-B HTOTAL!
[IGFB][ERROR] FB1 Not waiting for in set gamma to solid color as path state is not active
[IGFB][ERROR] setAttribute called when FB2 is in a sleep state - attribute: 'pwrs'
[IGFB][ERROR] FB1: The color mode = 0x100 is not RGB for DP
[IGFB][ERROR] TxnHang1: FB1: IsTransactionComplete called following fakeVBL notification
[IGFB][ERROR] FB1: Flip called without enabling VBL
[IGFB][ERROR] FB1: VBlank Timeout Timer called in 51ms - fTransactionState = 0x0, fLiveState = 0x0 fOnline: 1
```

**これを故障と読んではいけない。** 最終状態は両画面 30bit で正常、`fOnline: 1` は
オンラインを意味し、`not RGB for DP` も一過性（確定値は `ARGB2101010`）。
パイプの再プログラム中に順序前後があるだけで、2 秒後には収束している。
この機種は本物のグラフィックス障害が「ハードリセット」や「3 分ブラックスクリーン」
という形で出る（発見 6）ので、**画が出ていてログだけ賑やかな状態は追わなくてよい。**

### ★ クラムシェル運用は AC 必須（実測から判明）

復帰後の `PMRD` が毎秒こう出している:

```
PMRD: clamshell closed 0, disabled 0/0, desktopMode 1, ac 0
PMRD: Clamshell enabled / setClamShellSleepDisable(1->0)
```

**`desktopMode 1`** = 外部ディスプレイを認識して「デスクトップモード」に入っている。
これがクラムシェル運用の前提条件。ただし **`ac 0` = バッテリー駆動**であり、この状態で
`setClamShellSleepDisable(1->0)`（クラムシェルスリープを再び有効化）が走っている。

→ **バッテリーのまま蓋を閉じると、外部画面があっても寝る。**
外部画面だけで使うには **AC 接続 + 外部キーボード/マウス**が必要（Apple 純正機と同じ条件）。
発見 21 の `AppleClamshellCausesSleep = Yes` と整合する。

### 未検証として残すもの

- 実際に蓋を閉じたクラムシェル運用（AC + 外部入力を揃えた状態での確認）
- 1920x1080 より高い解像度 / 60Hz より高いリフレッシュレート
- 外部ディスプレイの音声出力（DP audio）

## ★ 発見 24: 「ディスプレイを挿すとキーボード設定アシスタントが出る」の原因はディスプレイではない（2026-08-18 23:29 特定）

外部ディスプレイを接続するたびにキーボード設定アシスタントが起動する。
**ディスプレイは無関係で、ドックのハブにぶら下がった USB ドングルが原因。**

### 計測

```
/Library/Preferences/com.apple.keyboardtype.plist
  "keyboardtype" => {
    "4-8526-0"   => 40      GesturePoint Mouse Dongle (Swiftpoint)  登録済み
    "569-5426-0" => 40      Razer Blade 内蔵キーボード              登録済み
  }
                          ← 2.4G Receiver (Compx) の記録が無い ★
```

キーの書式は `<ProductID>-<VendorID>-<CountryCode>`（すべて 10 進）。
`40` は ANSI。ユーザ側 `~/Library/Preferences/com.apple.keyboardtype.plist` は存在しない。

未登録のデバイスはこれ:

```
IOHIDInterface  "Product" = "2.4G Receiver"
                "VendorID" = 9639 (0x25a7 Compx)   "ProductID" = 64097 (0xfa61)
                "PrimaryUsagePage" = 1   "PrimaryUsage" = 6    ← キーボードとして申告
                "CountryCode" = 0                              ← レイアウト不明
```

USB ツリー上の位置が「ディスプレイと連動する」理由を説明する:

```
USB2.1 Hub (Genesys 05e3:0610) @ 0x14100000/18     ← USB-C ドック
  └ USB2.0 Hub (05e3:0608)     @ 0x14120000/20
      └ 2.4G Receiver          @ 0x14121000/21     ← これ
```

ドックを挿す = ディスプレイが繋がる = 同時にこのハブ鎖が列挙される
= ドングルが再列挙される → アシスタントが出る、という連鎖だった。

時刻の裏付け: ディスプレイを接続した直後の **23:25:43** に
`KeyboardSetupAssistant` が pid 23772 として起動している。

```
23:25:43  runningboardd: Calculated state for
          app<application.com.apple.KeyboardSetupAssistant...(501)>:23772>:
          running-active (role: UserInteractiveFocal)
23:26:30  runningboardd: Invalidating assertion ... from originator
          [osservice<com.apple.WindowServer(88)>:155]
```

注意: **アシスタント起動のログはデバイス名を出さない**ので、この行だけでは
「どのデバイスが引き金か」は決まらない。特定は plist の欠落エントリと USB 階層から来ており、
確定は下記の対処後の再現試験で取った。

### なぜ「毎回」なのか

アシスタントは記録を書くために「shift の隣のキーを押せ」と要求する。
このドングルは**実際のキーボードではない**（無線マウス/リモート系がキーボード
interface を持っているだけ）ので該当キーを送れず、**完了できない → 記録が書かれない
→ 次も出る**。閉じても解決しないのはこのため。同じ理由で
Swiftpoint 側も usage 6 を持っているが、そちらは既に登録されている。

### 対処: 記録を手で書く

```
sudo defaults write /Library/Preferences/com.apple.keyboardtype.plist \
  keyboardtype -dict-add "64097-9639-0" -int 40
```

`-dict-add` なので既存 2 件は保持される。実際にタイプするデバイスではないので
値が ANSI(40) でも実害はない。

### ★ 確定: 修正後に再列挙させてもアシスタントは出ない（2026-08-18 23:40 実測）

「出なくなった」ではなく「**引き金のデバイスを再列挙させた上で出なかった**」ところまで
確認した。これが無いと、単にドックを挿していないだけの状態と区別できない。

```
23:38:18  KeyboardSetupAssistant 起動          ← 修正前の最後の発生
23:38:40  plist に "64097-9639-0" => 40 が書かれた
23:40:45  UniversalControl: Matched Local Keyboard, Mf 'Compx', Nm '2.4G Receiver'
          LocationID 336728064 (= 0x14121000)  ← 同一ハブ位置に再列挙された
          DisplayPort transaction 59 件         ← ディスプレイも挿し直されている
          KeyboardSetupAssistant の起動: 0 件   ★
```

ドングルの `CountryCode` は依然 `0`（レイアウト不明）のままである。
**plist の記録だけでアシスタントは抑止され、デバイス側は何も変わっていない。**
これは「macOS は country code 不明なキーボードのうち、記録の無いものだけ尋ねる」
という当初の読みの裏付けでもある。

### 教訓

「X をすると Y が起きる」の X は、しばしば真の原因ではなく**同時に起きる別の事象**である。
ここでは「ディスプレイ接続」と「ハブ配下の USB 再列挙」がドック 1 本に束ねられていた。
`system_profiler SPUSBDataType` の**階層**を見るまで、ディスプレイ側を疑う理由しかなかった。

## ★★ 発見 25: Wi-Fi はスリープ復帰で落ちることがある → 有線 LAN は外さない（2026-08-19 00:11 実測）

「作業がほぼ終わったので Mac mini と Razer の間の有線 LAN は不要では」という判断を
実測で検証したところ、**否定された**。有線は残す。

### 経緯: 楽観的な読みが直接試験で覆った

先行して 23:30 のスリープ後に `en0` が `status: active` かつアドレス保持だったので、
「Wi-Fi はスリープを越えられる」と読んだ。**この読みは間違いだった。**
Wi-Fi 経由でスリープ→復帰→Wi-Fi 経由で再接続を直接試すと:

```
00:11:49  wake（airportd: systemWokenByWiFi: wake reason <XDCI>, was not woken by WiFi）
          AUTO-JOIN: Auto-join triggered (trigger=screen_off, mode=best)
00:12:4x  ssh 192.168.2.190 → Operation timed out
00:12:5x  ssh 192.168.2.190 → Operation timed out
00:13:01  ssh 192.168.2.190 → 成功（3回目）
00:14:xx  en0 status: inactive / "You are not associated with an AirPort network."
          ping ×60 → 100.0% packet loss ("Host is down")
```

**一度繋がってから完全に落ちた。** つまり「復帰が遅い」ではなく**不安定**である。
23:30 の回は生き残っていたので、決定論的な故障ではなく**間欠**。
これが AirportItlwm（サードパーティ Intel ドライバ）の弱点で、
有線 LAN が保険をかけていたのは正確にこの部分だった。**保険は正当だった。**

### 復旧は sudo 無しの 1 行で足りる

```
networksetup -setairportpower en0 off; sleep 3; networksetup -setairportpower en0 on
```

これで `status: active` / `Current Wi-Fi Network: elecom-4e2303a` に戻り、
ping 0% loss、SSH も通る。再起動は不要。

### 教訓: 「落ちていない」の観測は「落ちない」の証拠にならない

23:30 の観測（復帰 20 分後に `en0` が active）は本物のデータだが、
**間欠故障に対しては 1 サンプルの成功は何も保証しない。**
知りたかったのは「Wi-Fi だけでリモート作業を続けられるか」であり、
それを答えられるのは「Wi-Fi 経由で寝かせて Wi-Fi 経由で戻る」試験だけだった。
遠隔からアクセス手段を捨てる判断は、その手段自体で往復させて確かめる。

### 有線を残すことの副作用（承知の上で受け入れる）

| 事項 | 内容 |
|---|---|
| Mac mini | `bootpd -d -D -i en8`（10.42.0.0/24 の DHCP）+ インターネット共有 + pf 変更が稼働継続。`tools/share-off.sh` は保留 |
| 経路 | Razer の default gateway は `10.42.0.1` = **Mac mini が寝ると Razer のネットが死ぬ** |
| USB | AX88179A が 1 ポート占有、スリープ要因に `USBExternalDevice` が載る |

### 将来ケーブルを捨てたい場合

復帰時に `en0` が未 associated なら上記 1 行を叩く watchdog を LaunchAgent で常駐させる
（`tools/brtd` と同じ形）。**未実装。** それを入れるまでは有線が唯一の信頼できる経路。

### ★ 副産物: `192.168.2.190` のホスト鍵衝突は攻撃ではない

macOS と Windows が同じ IP を共有しているため、OS を切り替えるたびに
`Host key ... has changed` が出る。`known_hosts` の 39〜41 行目は
**Windows の 3 つのホスト鍵**（ed25519 / rsa / ecdsa）である。

鍵が本物であることは**信頼できる有線経路から独立に確認した**（これが正しい検証手順で、
`StrictHostKeyChecking=no` で潰してはいけない）:

```
Wi-Fi で提示   SHA256:hjtOpmZvVJN5qiFJOm7cLyUbHYlIh8VNL5RG1d9ChSs
有線経由で実体 SHA256:hjtOpmZvVJN5qiFJOm7cLyUbHYlIh8VNL5RG1d9ChSs (ED25519) ✅
```

恒久対処は `~/.ssh/config` で `HostKeyAlias` を分けること（`razer-macos` / `razer-windows`）。
有線と Wi-Fi に**同じ** alias を与えると、経路が変わっても 1 エントリで済む。
