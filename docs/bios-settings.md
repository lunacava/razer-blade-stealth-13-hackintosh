# BIOS 設定チェックリスト — Razer Blade Stealth 13 (RZ09-02812E71)

対象 BIOS: **1.01 (2018/11/12)**
入り方: 電源投入直後に `F1` または `DEL` を連打（Razer 機は `F1`）

---

## 最重要: BIOS は絶対に更新しない

現在の **1.01** で全機能が動作している。

- **BIOS 3.02 は本機種で起動不能になった報告が複数ある**
- Reddit の同一機種成功例は 1.06 を改造して DVMT 64MB にしていたが、
  本構成は `framebuffer-stolenmem` / `framebuffer-fbmem` で解決済みなので**フラッシュ不要**
- Windows Update や Razer Synapse が BIOS 更新を促しても**拒否する**

---

## 設定一覧

すでに適用済みの項目には ✅ を付けた（2026-08-16 実施）。

| 項目 | 設定値 | 状態 | 理由 |
|---|---|---|---|
| **Network Stack** | **Disabled** | ✅ | 有効だと起動時に UEFI PXE が DHCP を投げ、`EFI_NOT_READY` + hex ダンプが画面に漏れる。起動も遅くなる |
| **Secure Boot** | **Disabled** | ✅ | OpenCore は署名されていないので必須 |
| **Fast Boot** | **Disabled** | ✅ | USB 初期化をスキップするため、インストーラ USB が見えなくなる |
| **CSM Support** | **Disabled** | ✅ | Windows は `winload.efi` = UEFI ネイティブ起動なので安全に無効化できる（実機確認済み）。macOS は UEFI 専用 |
| **Thunderbolt** | **Disabled** | ✅ | TB3 コントローラ (JHL6240) は macOS で不安定要因。**副作用: 右 USB-C の映像が出ない**（DP mux が JHL6240 内にあるため。左 USB-C は iGPU 直結で動作 → 発見 23） |
| **TPM / PTT** | **Disabled** | ✅ | macOS が扱えない。BitLocker は復号済みなので影響なし |
| **Intel VMX (VT-x)** | **Enabled のまま** | ✅ | macOS に無害。無効にすると WSL2 / Hyper-V が壊れる。macOS が嫌うのは **VT-d** の方で、そちらは `DisableIoMapper=YES` で対処済み（DMAR テーブル存在を確認） |
| **Hyper-Threading** | **Enabled のまま** | ✅ | i7-8565U は 4C/8T。無効にする理由がない |
| **SATA Mode** | AHCI | — | 本機は NVMe 単機なので該当項目なし。RAID/Intel RST が現れたら AHCI にする |
| **DVMT Pre-Allocated** | 項目なし | — | BIOS 1.01 には存在しない（32MB 固定）。`framebuffer-stolenmem=0x01300000` / `framebuffer-fbmem=0x00900000` で回避 |

---

## Windows 側の前提条件（すべて確認済み）

| 項目 | 状態 | 理由 |
|---|---|---|
| BitLocker | **完全に復号済み** ✅ | 暗号化されたままではパーティション操作で復旧不能になる |
| 高速スタートアップ | **無効** ✅ | 有効だと Windows がディスクをロックしたまま休止し、macOS 側からマウントすると破損する |
| 休止状態 (hiberfil.sys) | **無効** ✅ | 同上。`powercfg /hibernate off` 実行済み |
| ブート方式 | **UEFI ネイティブ** ✅ | `\WINDOWS\system32\winload.efi` / SecureBoot=False |
| Rocky Linux | **削除済み** ✅ | NVRAM エントリ `{cdbbd6f6-...}` と `\EFI\rocky` (8.4MB) の両方 |

---

## 既知の挙動（ハマりどころ）

### ~~USB を挿したまま再起動すると途中で止まる~~ → Fast Boot 無効化で解決済み

当初、再起動時に USB 機器が接続されていると POST の途中でハングする現象があった。

**原因は Fast Boot。** Fast Boot は USB 初期化をスキップする最適化で、これが有効だと
USB の列挙で不整合が起きて POST が止まる。

→ **上の設定一覧で Fast Boot = Disabled にした時点で解消済み（✅）。**
以後、USB や外付け HDD を挿したまま再起動して構わない。

**注意: BIOS リセットで Fast Boot が Enabled に戻ると、この現象も復活する。**
症状が再発したら真っ先に Fast Boot を疑う。

### ESP が 100MB しかない

```
disk0 partition 2 : System  100 MB  (使用 32.63MB)
```

OpenCore の EFI は **59MB** あるため、Windows Boot Manager と共存させると余裕がない。
→ **専用 ESP を 200MB で新規作成する**方針（決定済み）。

---

## macOS インストール前の最終確認手順

1. 再起動 → `F1` 連打で BIOS に入る（Fast Boot は無効なので USB は挿したままでよい）
2. 上の表の ✅ 項目が維持されているか確認（BIOS リセットで戻ることがある）
3. **Boot Order** に不要なエントリがないか確認（Rocky Linux は削除済み）
4. BIOS を保存して終了
5. OpenCore USB を挿す
6. 電源投入 → `F12` でブートメニュー → USB を選択

---

## 参照

- 実機ハードウェア調査結果: `docs/hardware-findings.md`
- config.plist 生成元: `build/gen/mkconfig.py`
