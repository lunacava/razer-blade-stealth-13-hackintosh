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
| OS | Windows 11 build 26100 |
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

Bluetooth 側: USB `VID_8087` が見えず、CNVi の BT も PCH 経由。

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
| **外部ディスプレイ** | **未解決**（接続でフリーズ） | 既定 DP connector が一致。要実機検証 |
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
- 外部ディスプレイを挿すとフリーズ → フェーズ 2 の課題として残す

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

`pmset displaysleepnow` → wake を 4回連続、全部成功:

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
