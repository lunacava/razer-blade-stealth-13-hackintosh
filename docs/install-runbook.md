# macOS Sonoma インストール手順書 — Razer Blade Stealth 13

前提: C: の縮小は完了済み（2026-08-17 07:29）。**未割り当て 580.40 GB** が確保されている。

```
disk0 (931.51GB, GPT)
 #1 RazerRecPar    98 MB
 #2 ESP            98 MB   ← Windows 専用。触らない
 #3 MSR            16 MB
 #4 C:            350 GB   end = 376,043,935,232
    ────── 未割り当て 623,195,979,776 (580.40 GB) ──────
 #5 WinRE        916 MB    off = 999,240,499,200 ← 触らない
```

---

## 全体の流れ

| # | 工程 | 実行場所 | 所要 |
|---|---|---|---|
| 0 | 事前確認 | Mac からリモート | ✅完了 |
| 1 | **ESP#2 (200MB) を作成** | **Windows / diskpart（リモート可）** | ✅完了 |
| 2 | BIOS 確認 | 実機 | 5分 |
| 3 | OpenCore USB から起動 | 実機 | 5分 |
| 4 | ディスクユーティリティで APFS 作成 | 実機 | 3分 |
| 5 | macOS インストール | 実機（自動、数回再起動） | 40〜60分 |
| 6 | 初期設定 | 実機 | 10分 |
| 7 | EFI を内蔵 ESP#2 へコピー | 実機 or リモート | 10分 |
| 8 | Windows が起動するか確認 | 実機 | 5分 |

---

## 工程 1: ESP#2 を作成する ✅ **完了（2026-08-17 08:0x）**

```
 6  System     OCESP   off=376,044,519,424  size=209,715,200 (200MiB)  FAT32  空き 196MB
    GUID = c12a7328-f81f-11d2-ba4b-00a0c93ec93b   ← 正規 ESP
```

C: / WinRE / 既存 ESP / MSR はすべて無変更。未割り当ては **580.20GB** に。

### ハマった点: diskpart は隠し ESP をフォーマットできない

`create partition efi` は成功したが、続く `format quick fs=fat32` が

```
Virtual Disk Service error: The device is in use.
The selected volume or partition is in use.
```

で失敗した。`detail partition` を見ると `Hidden : Yes` / `Fs : RAW`。
**diskpart は Hidden 属性の ESP をフォーマットできない**（`override` を使うと
別のリスクが出るので使わない）。

→ **PowerShell の `Format-Volume` を使う**と通る。offset と size を検証してから実行した:

```powershell
$p = Get-Partition -DiskNumber 0 -PartitionNumber 6
if ($p.Offset -ne 376044519424 -or $p.Size -ne 209715200) { "ABORT"; exit 1 }
$p | Format-Volume -FileSystem FAT32 -NewFileSystemLabel OCESP -Confirm:$false -Force
```

`assign letter=S` も同じ理由で効かない（隠しパーティションにレターは付かない）。
**EFI のコピーは macOS 側から `diskutil mount` で行うので不要。**

---

## 工程 1 の詳細（記録用）: ESP#2 を作成する手順

### なぜ macOS 側でやらないのか

`diskpart` の `create partition efi` は**パーティションタイプ GUID
`C12A7328-F81F-11D2-BA4B-00A0C93EC93B` を自動で設定する**。

macOS のディスクユーティリティで「MS-DOS (FAT)」を作ると GUID が
**Microsoft Basic Data (`EBD0A0A2-...`)** になり、**ファームウェアが ESP として
認識しない**。後から `gdisk` でタイプコードを `EF00` に書き換える必要が出る。

→ **Windows 側で作るほうが確実。**

### なぜ ESP を 2 つにするのか

既存 ESP #2 は 98MB で**空きが 63.26MB しかない**。OpenCore の EFI は **59MB**。
入れると残り 4MB になり、**Windows Update が bootmgfw を更新できずに両方の OS が
起動不能になる**リスクがある。GPT では同じタイプ GUID の ESP が複数あっても合法で、
ファームウェアは両方をスキャンする。

### コマンド

```
diskpart
  select disk 0
  create partition efi size=200
  format quick fs=fat32 label="OCESP"
  assign letter=S
  list partition
  exit
```

**`create partition efi` は「未割り当て領域の先頭」に作られる** = C: の直後。
残り約 580.2GB は未割り当てのまま残る。

⚠ **`create partition primary` にしないこと**（Basic Data GUID になる）
⚠ **`clean` は絶対に打たないこと**（全パーティション消滅）

### 検証

```
Get-Partition -DiskNumber 0 | Format-Table PartitionNumber, Type, Offset, Size, DriveLetter
(Get-Disk 0).LargestFreeExtent / 1GB     # 約 580.2 になるはず
```

`Type` が **`System`** と出れば成功。`Basic` なら失敗なので作り直す。

---

## 工程 2: BIOS 確認（実機）

`docs/bios-settings.md` の ✅ 項目を確認する。特に:

| 項目 | 値 |
|---|---|
| Secure Boot | **Disabled** |
| Fast Boot | **Disabled** |
| CSM Support | Disabled |
| Network Stack | Disabled |
| Thunderbolt | Disabled |
| TPM / PTT | Disabled |

**BIOS は絶対に更新しない**（1.01 のまま。3.02 は起動不能報告あり）。

---

## 工程 3: OpenCore USB から起動（実機）

1. **AC アダプタを接続**（インストール中の電源断は致命的）
2. OpenCore USB（`OPENCORE` ラベル）を挿す
3. 電源投入 → **`F12`** でブートメニュー
4. USB を選択（`UEFI: <USB名>` と表示されるもの。`UEFI:` が付かないものは選ばない）
5. OpenCanopy のピッカーが出る → **`macOS Base System`** を選ぶ

### boot-args は `-v` 付き

```
-v debug=0x100 keepsyms=1 alcid=30 -igfxblt
```

**画面は白いテキストが流れる**（Apple ロゴではない）。これは正常。
問題が起きたときに原因を読むためにわざと verbose にしている。

### ★解決済みの罠: 黒画面で止まる = Bootstrap が動かない（2026-08-17）

**症状:** OpenCore のアイコンを選ぶと黒画面で進まない。3 回試して 3 回同じ。

**ログ**（USB ルートの `opencore-*.txt`。2 行・43ms で終了）:

```
00:000 00:000 OCM: Failed to start image - Already started
00:043 00:043 BS: Failed to start OpenCore image - Already started
```

**原因: Razer BIOS 1.01 のファームウェアバグ。**

`BS:` = **Bootstrap** = `EFI\BOOT\BOOTx64.efi`（24KB）。これは `EFI\OC\OpenCore.efi`
（626KB）を起動するだけの中継役。ソース `Application/Bootstrap/Bootstrap.c:91` に
`Try absolute path: EFI\BOOT\BOOTx64.efi -> EFI\OC\OpenCore.efi` と書かれている。

`Library/OcMiscLib/ImageRunner.c` を読むと落ちている箇所が特定できる:

| 行 | 処理 | 結果 |
|---|---|---|
| 41 | `gBS->LoadImage()` | **成功**（失敗なら `Failed to load image` が出る） |
| 103 | `gBS->StartImage()` | **`EFI_ALREADY_STARTED` を返す** ← ここ |

つまり **OpenCore 本体は一度も実行されていない**。ACPI・kext・OpenCanopy・解像度は
すべて無関係（それらは全部この後の処理）。

**対処: Bootstrap を挟まず、`OpenCore.efi` を `BOOTx64.efi` として直接置く。**

```
（バックアップ）
Copy-Item D:\EFI\BOOT\BOOTx64.efi D:\EFI\BOOT\BOOTx64.efi.bootstrap-orig
（差し替え）
Copy-Item D:\EFI\OC\OpenCore.efi D:\EFI\BOOT\BOOTx64.efi -Force
```

ファームウェアが OpenCore を**直接**起動するので、問題の `StartImage` が発生しない。
`LauncherOption = Disabled` なので設定とも整合する（Bootstrap を NVRAM に登録する
機能を使っていない）。**内蔵 ESP#2 にコピーするときも同じ構成にする。**

### ★その続き: `OC: Failed to load configuration!` （2026-08-17）

`OpenCore.efi` を `BOOTx64.efi` に置いた**だけ**では足りない。次はこれで止まる:

```
OC: Failed to load configuration!
```

`OC:` プレフィックスなので **OpenCore 本体は起動している**（Bootstrap 問題は解決）。

**原因: OpenCore は「自分が置かれたディレクトリ」を基準に config.plist を探す。**

`Application/OpenCore/OpenCore.c`:

```c
mStorageRoot = OcCopyDevicePathFullName (LoadPath, &RemainingPath);  // :207
UnicodeGetParentDirectory (mStorageRoot);                            // :223
```

`EFI\BOOT\BOOTx64.efi` として置いたので基準は `EFI\BOOT\`。
そこに `config.plist` が無いので停止した（`OcMiscEarlyInit` → `CpuDeadLoop()`）。
**`EFI\OC\` は見ない。** `Drivers` / `Kexts` / `ACPI` / `Resources` も同様。

**対処: `EFI\OC\` の中身を丸ごと `EFI\BOOT\` にコピーして自己完結させる。**

```
robocopy D:\EFI\OC D:\EFI\BOOT /E
```

結果（`EFI\OC\` は残しておく。元構成に戻せるように）:

```
\EFI\BOOT\BOOTx64.efi                626,688   ← OpenCore.efi と同一
\EFI\BOOT\BOOTx64.efi.bootstrap-orig  24,576   ← 元の Bootstrap
\EFI\BOOT\config.plist                24,823
\EFI\BOOT\{ACPI,Drivers,Kexts,Resources,Tools}\
```

ファイル数: `EFI\OC` = 518 / `EFI\BOOT` = 520（`BOOTx64.efi` と `.bootstrap-orig` の差）。

**内蔵 ESP#2 にコピーするときも同じ構成にする。**

### ★さらに続き: `OCB: StartImage failed - Already started` （2026-08-17）

config も読めて**ピッカーまで到達**したが、エントリを起動すると失敗する。

```
00:000 OC: Boot failed - Already started
00:115 OCB: StartImage failed - Already started
06:129 （2回目）  22:311 （3回目）  47:578 （4回目）
```

`OCB:` = OpenCore Boot manager。`BootEntryManagement.c:2591` の
`Context->StartImage` → `OpenCore.c:99` の `gBS->StartImage()` が
`EFI_ALREADY_STARTED` を返している。

**タイムスタンプが 6/22/47 秒と離れている = 失敗後にピッカーへ戻れている。**
OpenCanopy と GUI ピッカーは正常。

**注目すべきは、これで 3 段階すべてが同じ `Already Started` だという点:**

| プレフィックス | 段階 | 呼び出し元 |
|---|---|---|
| `BS:` | Bootstrap → OpenCore | `Bootstrap.c:134` |
| `OC:` / `OCB:` | ピッカー → OS | `OpenCore.c:106` / `BootEntryManagement.c:2593` |

→ **このファームウェアの `gBS->StartImage` が、OpenCore の読み込んだイメージを
一貫して拒否している。**

### ★★ RELEASE ビルドでは INFO ログが出ない（重要な落とし穴）

`DisplayLevel` に `DEBUG_INFO` を立てても詳細ログが出ない。理由:

```
RELEASE 版 OpenCore.efi の文字列を検査:
  "OCCPU: Found"             PRESENT
  "Loaded configuration of"  ABSENT (stripped)
  "Storage root"             ABSENT (stripped)
  "OcMiscEarlyInit"          ABSENT (stripped)
```

**RELEASE ビルドは `DEBUG_INFO` の文字列自体がバイナリから除去されている。**
`DisplayLevel` をどう設定しても出ない。詳細ログには **DEBUG ビルドが必須。**

→ 公式リリースから `OpenCore-1.0.7-DEBUG.zip` を取得
（sha256 `3644db831dd18344896d7a86077b8c338c0eaa01b1579d7fa00785598cac1f2b`）。

**DEBUG 版に切り替えるときはドライバも DEBUG 版に揃える**（混在は避ける）:

| ファイル | RELEASE | DEBUG |
|---|---|---|
| `OpenCore.efi` | 626,688 | **872,448** |
| `OpenRuntime.efi` | 24,576 | **32,768** |
| `OpenCanopy.efi` | 114,688 | **151,552** |
| `ResetNvramEntry.efi` | 45,056 | **57,344** |
| `OpenShell.efi` | 1,187,840 | **1,290,240** |

`HfsPlus.efi` は別プロジェクト由来なので差し替え不要。

### ✅✅ 解決: `ProtectUefiServices = true` で起動した（2026-08-17）

**これが正解だった。** 3 段階すべての `Already started` が消え、起動が進んだ。

**根本原因: Razer BIOS 1.01 がドライバ読み込み中に UEFI サービスのポインタを
書き換えていた。** そのため OpenCore が保持していた `gBS->StartImage` が壊れ、
どの段階から起動しても `EFI_ALREADY_STARTED` になっていた。

**この機種では `ProtectUefiServices = true` が必須。** 内蔵 ESP#2 に入れる
config.plist も必ずこの設定にする（忘れると同じ症状が再発する）。

解決後の状態:
```
新しい opencore-*.txt が生成されない = エラー停止していない
（Already started のときは即座にログが書かれていた）
USB 無傷 / 内蔵は未割り当て 580.20GB のまま
```

### 対策として入れた `ProtectUefiServices`

`Docs/Configuration.tex:1743` の説明がこの症状そのもの:

> Some modern firmware ... may update pointers to UEFI services during driver
> loading and related actions.

**ファームウェアが UEFI サービスのポインタを書き換えるのを防ぐ** quirk。
3 段階すべてで `StartImage` が壊れている状況と一致するので
`Booter:Quirks:ProtectUefiServices = true` にした（`ocvalidate` OK）。

### ★★ 続き: 起動ループ（ピッカー → ピッカー → ピッカー…）（2026-08-17）

**症状:** 白い文字がざーっと流れた後、また OpenCore を選ぶ画面が出る。選ぶと また出る。

**これは前の対処（`OpenCore.efi` を `BOOTx64.efi` として置く）の副作用だった。**
DEBUG ログに証拠がそのまま出ていた:

```
OCB: Registering entry OPENCORE [Auto] (T:1|F:0|G:1|E:1|B:0) - ...\EFI\BOOT\BOOTX64.EFI
OC: Found previous image, aborting
OC: Boot failed - Already started
```

**原因: `\EFI\BOOT\BOOTx64.efi` は「汎用ブートローダ」として検出される。**

`Library/OcBootManagementLib/PolicyManagement.c:424-432` — パスが
`EFI_REMOVABLE_MEDIA_FILE_NAME`（= `\EFI\BOOT\BOOTx64.efi`）で終わると
`IsGeneric = TRUE` / `OC_BOOT_UNKNOWN` になり、**ピッカーのエントリとして登録される**。
つまり **OpenCore が自分自身をメニューに並べていた**（上の `G:1` がそのフラグ）。

選ぶ → 自分を起動しようとする → `Found previous image` → ピッカーへ戻る → 無限ループ。

**対処: `.contentVisibility` でそのエントリを隠す。**

```
D:\EFI\BOOT\.contentVisibility   内容 = "Disabled"（8 バイト、改行なし）
```

`BootEntryManagement.c:202-298`（`BootEntryDisabled`）がこのファイルを読み、
`Disabled` ならエントリを**ピッカーに出さない**。`EFI\BOOT\` 配置
（`ProtectUefiServices` が効くために必要）を維持したまま自己参照だけ消せる。

⚠ **`EFI\BOOT\` 配置をやめてはいけない。** Bootstrap 経由に戻すと
`ProtectUefiServices` が OpenCore.efi 起動**前**なので効かず、黒画面に戻る。

### ★★ 続き: ピッカーに macOS インストーラが出ない（2026-08-17）

ループ時のログでは登録されたエントリが `OPENCORE` と Windows の 2 つだけ。
`com.apple.recovery.boot`（インストーラ）が無かった。USB が MBR なのが原因かと
疑ったが違った。

**原因: `Misc:Boot:HideAuxiliary = true`。**

`BootEntryManagement.c:1172`:

```c
if (FileSystem->HasSelfRecovery || BootContext->PickerContext->HideAuxiliary) {
  return EFI_UNSUPPORTED;
}
```

**`HideAuxiliary = true` はリカバリ系エントリを完全に列挙対象外にする**（`Space` キーで
出てくるのは「登録済みで隠されたもの」だけ。最初から登録されないので出ない）。
`com.apple.recovery.boot\BaseSystem.dmg` = リカバリ扱いなので消えていた。

**対処: `HideAuxiliary = false`。** `mkconfig.py:235` にも反映済み。

### USB の現在の構成（2026-08-17 10:20）

```
D:\EFI                  ← DEBUG 版 + 3 つの修正（1039 files）
D:\EFI-release-backup   ← 初期の RELEASE 構成（1038 files、戻せる）
D:\oldlogs\             ← 過去のログ
D:\com.apple.recovery.boot\BaseSystem.dmg  789,568,598（健在）
```

3 つの修正の内訳と検証結果:

| # | 修正 | 直す症状 |
|---|---|---|
| a | `ProtectUefiServices = true` | `Already started`（BIOS がポインタを壊す） |
| b | `BOOT\.contentVisibility` = `Disabled` | ピッカー無限ループ（自己参照） |
| c | `HideAuxiliary = false` | インストーラがピッカーに出ない |

```
BOOT\BOOTx64.efi                872,448   ← OpenCore.efi (DEBUG) と同一
BOOT\config.plist                24,823
BOOT\.contentVisibility               8   ← 4469 7361 626c 6564 = "Disabled"
BOOT\Kexts\Lilu.kext\...\Lilu   527,456
BOOT\Drivers\HfsPlus.efi         37,892
BOOT\ACPI\SSDT-PLUG.aml              96
OC\OpenCore.efi                 872,448
OC\config.plist                  24,823
HideAuxiliary <false/> / LauncherOption Disabled / ProtectUefiServices <true/>
（BOOT と OC の両方で確認済み。ocvalidate: No issues found）
```

`config.plist` が Mac 側 24,820 / Windows 側 24,823 と 3 バイト違うが、
キーと値は上記のとおり一致している（プレーンテキストの改行差）。

**戻したいとき:** `Remove-Item D:\EFI -Recurse -Force` →
`robocopy D:\EFI-release-backup D:\EFI /E`

### ログが 2 行しか出ないのは設定のせい（修正済み → 実は RELEASE のせい）

`Misc:Debug:Target = 67` (`0x43`) = 有効 + 画面 + **`0x40` ファイル出力**。
ファイル出力は元から有効だった。しかし:

```
DisplayLevel = 2147483650 = 0x80000002 = ERROR | WARN のみ
```

**`DEBUG_INFO` (`0x40`) が無効**だったため `BS: Read OpenCore image of N bytes` などの
経過が一切残らなかった。→ **`2147483714` (`0x80000042`) に変更**して INFO を有効化。
次に問題が起きたときはログが数百行出るので原因が特定しやすい。

### ★★ ブートローダ完全突破 → カーネルパニック（2026-08-17 12:22）

**ここで OpenCore の問題は全部終わった。** パニック画面が出た = カーネルが動いた:

```
Kernel version: Darwin Kernel Version 23.6.0: Mon Jul 29 21:13:00 PDT 2024
                root:xnu-10063.141.2~1/RELEASE_X86_64          ← Sonoma 14.6.1
Boot args: -v debug=0x100 keepsyms=1 alcid=30 -igfxblt         ← 全部適用されている
Mac OS version: Not yet set
Panic diags file unavailable, panic occurred prior to initialization
System uptime in nanoseconds: 789747091                        ← 0.79 秒で落ちた
```

`Backtrace` は `kernel_trap` → `sync_iss_to_iks` → `panic` のみで、**サードパーティ
kext の名前が 1 つも出ていない**。`Fault CPU: 0x0` / `Error code: 0x3`（ページ保護違反）。
`Process name ... Unknown` / `Mac OS version: Not yet set` = **kext 読み込み直後、
起動のごく初期**。

#### ★ 発見: `ECEnabler.kext/Contents/Info.plist` が壊れていた

全 kext の Info.plist を機械的に検査して見つけた（`plistlib` で 1 個だけパース不能）:

```
kext                              plist  ID  EXE  PERS  ver
ECEnabler.kext                      217  PARSE ERROR Invalid file    ← これ
AirportItlwm.kext                  3852  ok  ok  ok   2.3.0
（他 14 個はすべて正常）
```

公式 zip の中身は **2210 バイト**だが、配置されていたのは **217 バイト**。
中身は `OSBundleLibraries` の辞書だけで、**`CFBundleIdentifier` /
`CFBundleExecutable` / `IOKitPersonalities` が全部欠落**していた
（バイナリ本体 29,992 バイトは公式と `cmp` 一致）。

原因は当初の展開作業のミス。**公式 zip から入れ直して修復済み**
（`build/EFI`, `build/usb/EFI`, `build/EFI-fix`, `build/EFI-debug` の BOOT/OC 全 8 箇所）。

教訓: **kext は Info.plist をパースして検証する。** ファイル数とサイズの確認だけでは
この種の破損は見逃す。

#### ✅✅ 真因判明: `MAT support is 0` なのに `RebuildAppleMemoryMap` を使っていた

`PanicNoKextDump = false` にして再度パニックさせたら、犯人が名指しされた:

```
last started kext at 646730695: as.vit9696.VirtualSMC 1.3.7 (addr 0xffffff800f70f000, size 86016)
loaded kexts:
  as.vit9696.VirtualSMC 1.3.7
  as.vit9696.Lilu 1.7.2
  （以降はすべて Apple 純正）
```

**サードパーティ kext は Lilu と VirtualSMC の 2 つしか読み込まれていない。**
つまり下記の AirportItlwm 説は**外れ**。WiFi kext に到達する前に落ちていた
（だから WiFi を無効化しても症状が変わらなかった）。

**アドレスを突き合わせると原因が確定する:**

| 値 | 意味 |
|---|---|
| `Error code: 0x3` | bit0(present) + bit1(write) = **存在する読み取り専用ページへの書き込み** |
| `RIP  0xffffff8010c47251` | 実行中のコード |
| `CR2  0xffffff8010c4c72e` | 書こうとした番地。**RIP から 0x54dd = 21,725 バイト**（ほぼ自分のコード領域） |

Lilu は他 kext の関数を実行時に書き換えて動作するので、**コード領域への書き込み
権限が必須**。それが拒否されて落ちていた。

**決定的な証拠は過去の DEBUG ログにあった:**

```
OCABC: MAT support is 0                      ← ★これ
OCABC: ... WRUNPROT 0 ...                    ← EnableWriteUnprotector = false
OCABC: ... RBMAP 1 VMAP 1 ... RTPERMS 1      ← RebuildAppleMemoryMap = true
```

`Docs/Configuration.tex:1631-1633`:

> \emph{Note}: This quirk may potentially weaken firmware security. Please use
> `RebuildAppleMemoryMap` **if the firmware supports memory attributes table (MAT)**.
> Refer to the **`OCABC: MAT support is 1/0`** log entry to determine whether MAT is supported.

同 `:1839-1840`（`RebuildAppleMemoryMap` 側の記述）:

> This quirk replaces `EnableWriteUnprotector` on firmware **supporting Memory
> Attribute Tables (MAT)**.

→ **この BIOS は MAT 非対応 (0) なので `RebuildAppleMemoryMap` は使えない。**
`EnableWriteUnprotector` が正しい。設定が逆だった。

**修正:**

| quirk | 誤 | 正 |
|---|---|---|
| `EnableWriteUnprotector` | false | **true** |
| `RebuildAppleMemoryMap` | true | **false** |
| `SyncRuntimePermissions` | true | **false** |

後ろ 2 つは同じメモリ属性テーブルを操作するので `EnableWriteUnprotector` と排他。
`ProtectUefiServices` は維持（BIOS のポインタ破壊対策として別問題）。

⚠ **`EnableWriteUnprotector` は `OpenRuntime.efi` の `OC_FIRMWARE_RUNTIME`
プロトコルに依存する**（`Configuration.tex:1628`）。DEBUG 版 32,768 バイトが
入っていることを確認済み。ドライバを外すとこの quirk も無効になる。

**教訓: メモリ関連 quirk は推測せず `OCABC: MAT support is N` を見て決める。**

#### ~~本命の容疑者: `AirportItlwm.kext` 2.3.0~~ ← 外れだった

| 項目 | 値 |
|---|---|
| ビルド対象 | Sonoma **14.4** |
| 実機カーネル | Sonoma **14.6.1** (Darwin 23.6.0) |
| 依存 | `com.apple.iokit.IO80211Family 1.5.0`, `IOSkywalkFamily 1.0` |

AirportItlwm は **`IO80211Family` の非公開 API に直接リンクする**ため OS バージョン
ごとにビルドが切られている。14.4 用バイナリを 14.6.1 で読むと構造体オフセットが
ずれて**即パニック**する。0.79 秒・`Not yet set`・kext 名なしという症状と一致する
（Lilu 系はバージョンチェックで自ら退避するのでこうはならない）。

これは**前から想定していたリスク**で、`itlwm.kext` を無効状態で同梱してあった。

#### 対処: WiFi kext を両方 OFF にして切り分ける

```
D:\EFI                  ← AirportItlwm=false / itlwm=false（1038 files）
D:\EFI-panic-backup     ← パニックした構成（戻せる）
D:\EFI-release-backup   ← 初期の RELEASE 構成
```

同時に `Kernel:Quirks:PanicNoKextDump = false` にした。**次にパニックしたら
読み込まれた kext の一覧が画面に出る**ので、犯人を名指しで特定できる。

ローカルには切り分け用の構成も用意した:

| ツリー | 内容 | 用途 |
|---|---|---|
| `build/EFI-nowifi` | WiFi 2 個だけ OFF（14 個 ON） | **これをデプロイ済み** |
| `build/EFI-min` | Lilu / VirtualSMC / WhateverGreen / NVMeFix の 4 個だけ | nowifi でも落ちる場合 |

`EFI-min` でも落ちるなら原因は kext ではなく ACPI / Booter quirks 側。

#### ⚠ カーネルパニックは `opencore-*.txt` に残らない

パニック後にログを取ったが 2 秒・40 行で終わっていた:

```
02:252 OC: Not deleting NVRAM ...prev-lang:kbd, matches add   ← ここで終わり
```

**OpenCore はカーネルに制御を渡した時点でファイル書き込みをやめる。**
カーネル以降の情報はログに一切入らない。→ **パニック画面の撮影が唯一の情報源。**
特に `Backtrace` と `Boot args` と `System uptime` の 3 つを写す。

#### ✅ 修正版デプロイ済み（USB `D:\EFI`）

| 項目 | 値 |
|---|---|
| `EnableWriteUnprotector` | `<true/>` ← 修正 |
| `RebuildAppleMemoryMap` | `<false/>` ← 修正 |
| `SyncRuntimePermissions` | `<false/>` ← 修正 |
| `ProtectUefiServices` | `<true/>` 維持 |
| `AvoidRuntimeDefrag` / `DevirtualiseMmio` / `SetupVirtualMap` | `<true/>` 維持 |
| `Drivers\OpenRuntime.efi` | 32,768 bytes = DEBUG 版（この quirk の前提） |
| `BOOT\Kexts\ECEnabler.kext\...\Info.plist` | 2,210 bytes（修復済み） |
| `com.apple.recovery.boot\BaseSystem.dmg` | 789,568,598 bytes 無傷 |
| ファイル数 | 1,038 |

`D:\EFI\BOOT\config.plist` と `D:\EFI\OC\config.plist` の**両方**で確認済み。
WiFi kext は依然 OFF、`PanicNoKextDump = false` も維持（また落ちたら kext 一覧が出る）。
戻す場合は `D:\EFI-wifi-off-backup`。

ローカルも同じ quirk に揃えた（`build/EFI`, `build/usb/EFI`, `build/gen/mkconfig.py`)。
**`mkconfig.py` を再生成してもパニック構成に戻らない。**

### ✅✅ パニック突破を確認（実機ログ撮影）

**パニックせずカーネルが起動した。** 撮影された verbose ログに以下が出ている:

```
IOThunderboltFamily (build 20:58:38 Jul 29 2024)
IONVMeController::start(IOService *)::852: Successfully initialized NVMe drive
apfs_module_start:3232: load: com.apple.filesystems.apfs, v2236.141.1, apfs-2236.141.1, 2024/07/29
AppleKeyStore:331:0: starting (BUILT: Jul 29 2024 21:10:56)
CoreAnalyticsHub start completed
SMCBatteryManager  binfo: 0 battery 0 reports lower design capacity than maximum charged (4602/4743)
```

| 確認できたこと | 意味 |
|---|---|
| NVMe `Successfully initialized` | **内蔵 SSD が見えている** → Disk Utility でパーティション作成可能 |
| `apfs_module_start` | APFS ドライバ稼働 |
| **`SMCBatteryManager binfo: 0 battery 0 ...`** | **VirtualSMC + SMCBatteryManager + ECEnabler が動作**。バッテリー実容量 4602/4743 mAh を読めている = **ECEnabler の 16bit EC 読み対策が効いている** |
| `AppleKeyStore` / `CoreAnalyticsHub` | 通常のブート進行。パニックしていない |

→ `EnableWriteUnprotector` の修正で **VirtualSMC/Lilu のパニックは解消**。

### ⚠ ただし VoodooI2C が読み込めていない

同じログに:

```
Can't load kext com.alexandred.VoodooI2C - failed to resolve library dependencies.
kext com.alexandred.VoodooI2C failed to load (0xdc008016).
Failed to load kext com.alexandred.VoodooI2C (error 0xdc008016).
Couldn't alloc class "VoodooI2CPCIController"
```

**原因: OpenCore は `Contents/PlugIns` を再帰的に読まない。** `Kernel:Add` に書いた
バンドルだけを注入する。`VoodooI2C.kext` は `OSBundleLibraries` に

- `com.alexandred.VoodooI2CServices`
- `org.coolstar.VoodooGPIO`

を要求するが、これらは `VoodooI2C.kext/Contents/PlugIns/` の中にあり、
**個別に登録していなかったので依存解決に失敗した**（`0xdc008016` =
`kOSKextReturnDependencies`）。

**修正: プラグイン 3 個を親より前に個別登録する。**

```
13 ON  VoodooI2C.kext/Contents/PlugIns/VoodooI2CServices.kext   → Contents/MacOS/VoodooI2CServices
14 ON  VoodooI2C.kext/Contents/PlugIns/VoodooGPIO.kext          → Contents/MacOS/VoodooGPIO
15 ON  VoodooI2C.kext/Contents/PlugIns/VoodooInput.kext         → Contents/MacOS/VoodooInput
16 ON  VoodooI2C.kext
17 ON  VoodooI2CHID.kext
```

`VoodooInput`(me.kishorprins.VoodooInput) は VoodooI2CHID のマルチタッチ経路が使う。
計 16 → **19 エントリ**。`ocvalidate`: No issues found。全パスの実体存在も確認済み。

⚠ **`BundlePath` に `.kext/Contents/PlugIns/...kext` とネストして書くのが正解。**
プラグインを `Kexts/` 直下にコピーして平らに並べてはいけない（親が
`Contents/PlugIns` 内を参照する前提で作られている）。

なお**内蔵キーボードは USB 接続 (1532:0239 = キーボード + Chroma 複合デバイス)**
なので VoodooI2C とは無関係に動く。効かないのはトラックパッドだけ。

**→ 修正後、実機ログで解決を確認:**

```
VoodooI2CPCIController::pci8086,9de9 Starting I2C controller
VoodooI2CControllerDriver: Found valid Synopsys component, continuing with initialisation
VoodooI2CControllerDriver: Found I2C device: 1A581000
VoodooI2CDeviceNub::TPD0 Found valid resources from _CRS method
VoodooI2CDeviceNub::TPD0 Found valid APIC interrupt pin (0x1f)
VoodooI2CHIDDevice::1A581000 Device initiated reset accomplished
VoodooI2CPrecisionTouchpadHIDEventDriver::1A581000 Putting device into Precision Touchpad Mode
VoodooInputSimulatorDevice open by AppleMultitouchTrackpadHIDEventDriver
VoodooInputActuatorDevice  open by AppleActuatorHIDEventDriver
```

`1A581000` は本機のトラックパッド（`docs/hardware-findings.md:126` の `ACPI\1A581000`）。
Precision Touchpad Mode で `AppleMultitouchTrackpad` に接続されている。
**`VoodooI2CSynaptics` は不要**という当初の読みも裏付けられた。

### ★★ 続き: パニックせずにピッカーへ戻る（Thunderbolt）

パニック画面が出ないまま再起動してピッカーに戻る。**これは起動ループではない。**
`.contentVisibility` で直したループとは別物で、**カーネルが起動した後に
ハードウェアリセットが掛かっている**。

**2回撮影して最後の 2 行が同一だった**（`6776205us`/`6776250us` と
`6815512us`/`6815569us` — わずか 40ms 差の同じ関数）:

```
AppleThunderboltNHITransmitRingManager::allocateTransmitRing Flags: 0x1
AppleThunderboltNHIReceiveRingManager::allocateReceiveRing  Flags: 0x1
                                                          ← ここで終わり
```

直前の行が原因を示している:

```
Thunderbolt 255 PCI - LS=0x3043 LC=0x0c40 SS=0x0040 SC=0x1028 PMCSR=0x0000
   RT=0xffffffff NLRT=0xffffffff LWRT=0xffffffff PRRT=0xffffffff
```

**`0xffffffff` が4つ並ぶ = PCI コンフィグ読み出しが全ビット1 = デバイスが応答していない。**
`Thunderbolt 255` の `255` も異常値。BIOS で Thunderbolt を Disabled にしているため
コントローラ (JHL6240 Alpine Ridge LP) は PCI 上に列挙されるが電源が入っていない。
そこへ macOS が DMA リングを確保しようとしてリセットが掛かる。

**もう1つの裏付け:** 次のブートのログに

```
Previous shutdown cause: 5
```

`5` = 正常なシャットダウンではない。カーネル自身が異常終了を記録している。
パニック画面が出ないのは、パニックではなく**ハードウェアレベルのリセット**だから。

#### 対処: TB ドライバを Block する

```
com.apple.iokit.IOThunderboltFamily    Strategy=Disable
com.apple.driver.AppleThunderboltNHI   Strategy=Disable
```

`Strategy` は **`Disable`**（kmod の起動コードを強制的に失敗させる）。
`Exclude` はキャッシュから plist ごと削除する方式で、他が依存する kext には危険
（`Configuration.pdf:1449-1453`）。

⚠ **BIOS で Thunderbolt = Disabled にしてあっても、macOS 側の Block は別に必要。**
BIOS で無効にしてもコントローラは PCI 上から消えない。**両方必要。**

フェーズ2で TB3 を再検証するときはここを外す。Reddit の同一機種報告
（`OpaqueWalrus`）が6年解けていない「外部ディスプレイを挿すとフリーズ」も、
おそらく同じ TB3 経路。

`build/EFI-notb` として構成。`mkconfig.py` の `BLOCKED_KEXTS` にも入れたので
再生成しても消えない。ローカル 4 ツリーすべてに反映済み（`ocvalidate` 通過）。

### 止まったら

| 症状 | 見るところ |
|---|---|
| ピッカーが出ない | USB の EFI が読めていない。BIOS で Secure Boot を再確認 |
| `[EB|#LOG:EXITBS:START]` で停止 | ブート初期化。`DevirtualiseMmio` / メモリマップ系 |
| リンゴマークで進捗バーが止まる | グラフィック。`-igfxblt` の綴り確認（`-igfxblr` ではない） |
| `Still waiting for root device` | NVMe/USB。USBMap 未実施が原因のことがある |
| トラックパッドが効かない | VoodooI2C。**USB マウスを挿して回避**して先に進む。内蔵キーボードは USB (1532:0239) なので VoodooI2C とは無関係に動く |
| `Can't load kext com.alexandred.VoodooI2C - failed to resolve library dependencies` | **`Contents/PlugIns` の 3 個を config.plist に個別登録する**（下記） |
| **パニック画面が出ずにピッカーへ戻る** | **ループではない。カーネル起動後のハードウェアリセット。verbose 最後の 2 行を見る。`allocateTransmitRing` / `allocateReceiveRing` なら Thunderbolt を Block する（下記）。次のブートの `Previous shutdown cause: 5` も証拠になる** |
| **カーネルパニック（レジスタと Backtrace が並ぶ画面）** | **まず `PanicNoKextDump=false` で kext 一覧を出す。`Error code 0x3` かつ CR2 ≈ RIP なら kext ではなくメモリ quirk（`OCABC: MAT support is N` を見る）。kext が疑わしければ `build/EFI-min` で切り分ける** |

**verbose の最後の 5 行を撮影する。** それがあれば原因を特定できる。

---

## 工程 4: ディスクユーティリティで APFS を作成（実機）

インストーラのメニュー → **ディスクユーティリティ**

1. 左上の表示ボタン → **「すべてのデバイスを表示」**（重要）
2. 内蔵ディスク（931.51GB）を選ぶ
3. **「パーティション作成」**（消去ではない！）
4. 円グラフの**未割り当て領域**を選び **`+`**
5. 設定:
   - 名前: `Macintosh HD`
   - フォーマット: **APFS**
   - サイズ: **残り全部**（約 580.2GB）
6. 適用

### ⚠ 絶対にやってはいけないこと

- **「消去」をディスク全体に対して実行する** → Windows が消える
- **既存の ESP / C: / WinRE / RazerRecPar を選択して操作する**
- パーティションを **GUID パーティションマップで初期化し直す** → 全消去

「パーティション作成」で**未割り当て領域だけ**を対象にする。他のパーティションの
サイズが変わっていないか、適用前に必ず確認する。

---

## 工程 5〜6: インストールと初期設定（実機）

1. ディスクユーティリティを閉じる → **「macOS をインストール」**
2. インストール先に `Macintosh HD` を選ぶ
3. 数回再起動する。**そのたびに `F12` → USB を選ぶ**
   ピッカーでは `macOS Installer` → 後半は `Macintosh HD` を選ぶ
4. 初期設定では:
   - **Apple ID でのサインインは後回しにする**（SMBIOS 検証前にサインインしない）
   - ネットワークは有線 USB-C Ethernet があればそちらが確実

### WiFi が使えない場合

`AirportItlwm.kext` は **Sonoma 14.4 まで**の対応。リカバリは 14.6.1。
つまり **AirportItlwm がロードされない可能性が高い**。

その場合:
1. `config.plist` で `AirportItlwm.kext` を `Enabled = false`
2. `itlwm.kext` を `Enabled = true`
3. macOS 側で **HeliPort** アプリを使って接続する

判定方法（インストーラのターミナルで）:
```
kextstat | grep -i itlwm
ifconfig | grep -A2 en1
```

---

## 工程 7: EFI を内蔵 ESP#2 へコピー

USB なしで起動できるようにする。**macOS 上で作業する。**

```sh
diskutil list                      # ESP#2 の識別子を確認（disk0s6 など）
diskutil mount disk0s6
sudo cp -R /Volumes/OPENCORE/EFI /Volumes/OCESP/
diskutil unmount disk0s6
```

USB 側で **Bootstrap 回避 + `EFI\BOOT\` 自己完結**の構成にしてあるので、
そのままコピーすれば内蔵側も同じ構成になる。確認:

```sh
ls /Volumes/OCESP/EFI/BOOT/           # config.plist と Kexts/ があること
cmp /Volumes/OCESP/EFI/BOOT/BOOTx64.efi /Volumes/OCESP/EFI/OC/OpenCore.efi  # 一致すること
```

**この 2 点が満たされていないと内蔵から起動できない**（BIOS 1.01 のバグのため）。

⚠ **`disk0s2`（Windows の ESP）にコピーしないこと。** 容量が足りず両方壊れる。
サイズで見分ける: Windows ESP = 98MB / 新 ESP#2 = 200MB。

その後、**USB を抜いて**再起動して内蔵から起動するか確認する。
起動しない場合は BIOS の Boot Order に新 ESP のエントリを追加する。

---

## 工程 8: Windows が起動するか確認

OpenCanopy のピッカーに **Windows** のエントリが出るので選ぶ。
出ない場合は `F12` → `Windows Boot Manager`。

**この確認までは「成功」と言わない。** macOS が入っても Windows が起動しなければ
デュアルブートは失敗。

---

## 復旧手段（すでに用意済み）

| 手段 | 場所 |
|---|---|
| ディスクイメージ 157.5GB | 外付け HDD 上の AOMEI `.adi` |
| BCD バックアップ 24KB | `bcdedit /export` の出力 |
| **Windows インストール USB** | **disk14 (`ESD-USB`)。スタートアップ修復 / `Shift`+`F10` で diskpart** |
| WinRE | disk0 #5（健在、Enabled） |
| OpenCore USB のバックアップ | `backup/usb15-20260816-2030/` |

Windows が起動しなくなった場合の最短復旧:
```
（ESD-USB で起動 → Shift+F10）
bootrec /fixboot
bcdboot C:\Windows /s S: /f UEFI
```

---

## フェーズ 2（macOS 起動後にやる）

| 項目 | 内容 |
|---|---|
| USBMap | USB ポートのマッピング。スリープ・復帰の安定に必要 |
| CPUFriend + SSDT-CPUF | 省電力・バッテリー持ち |
| `_WAK` フック | 復帰時に dGPU を再度切る（電力削減） |
| CodecCommander | 復帰後に音が歪む場合のみ |
| Thunderbolt 再検証 | BIOS で有効に戻して安定性を見る |

---

## 作業完了後: Windows 側の設定を戻す

リモート作業のために開けた穴を閉じる。

```powershell
Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Public
Stop-Service sshd
Set-Service -Name sshd -StartupType Disabled
Remove-Item "$env:ProgramData\ssh\administrators_authorized_keys"
```
