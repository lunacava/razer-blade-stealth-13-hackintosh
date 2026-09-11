# Omarchy Linux を追加してトリプルブートにする — 実測記録

対象機: Razer Blade Stealth 13 (RZ09-02812E71) / 1.0 TB NVMe 単機
実施日: 2026-09-11 〜 09-12
結果: **Windows 11 / macOS Sonoma (OpenCore) / Omarchy 4.0.3 の 3 OS が同一 NVMe で共存**

Omarchy は DHH の Arch + Hyprland ディストロ。**バージョン 4.0.3、インストーラは
`omacom/omarchy-iso` の `quattro` ブランチ**（デフォルトブランチが `quattro`）。

このドキュメントの要点は 2 つ:

1. **Omarchy のインストーラは既存 ESP を絶対に触らない**（推測ではなくソースで確認した）。
   これが「OpenCore の ESP が壊されるのでは」という最大の懸念を消した。
2. 削るべきは Windows ではなく **ほぼ空の APFS コンテナ**だった。これは実測で決めた。

---

## 1. 事前確認: BIOS 要件はすべて既に満たしていた

`docs/bios-settings.md` の設定が偶然そのまま Omarchy の前提条件と一致していた。
新たに変更した BIOS 項目は **ゼロ**。

| Omarchy の要求 | 本機の状態 | 出典 |
|---|---|---|
| Secure Boot 無効 | ✅ Disabled | OpenCore が署名なしなので元から |
| TPM / PTT 無効 | ✅ Disabled | macOS が扱えないので元から |
| BitLocker 非暗号化 | ✅ 完全復号済み | パーティション操作の前提として元から |
| Fast Boot 無効 | ✅ Disabled | USB 列挙で POST が止まる問題の対策で元から |

BIOS に入るのは `F1`、起動デバイス選択は `F12`。
**BIOS は 1.01 のまま。3.02 は本機種で起動不能報告あり（README 参照）。**

---

## 2. インストーラの挙動をソースで確認する

`configurator`（ISO の `airootfs/root/configurator`、1254 行）を読んで確定させた事実:

```
531  # Omarchy always creates its own dedicated ESP in free space and never
532  # adopts an existing (Windows) ESP. ... the typical 100-260MiB
534  # Windows ESP is far too small for our Unified Kernel Images ...
594  local EFI_SIZE_B=$((2 * gib))          # 専用 ESP は 2 GiB 固定
595  local MIN_INSTALL_B=$((32 * gib))      # Omarchy 全体の最小サイズ
708  create_partition "$disk" "$ROOT_START_B" "$ROOT_END_B" btrfs OMARCHY_ROOT
751  mkfs.btrfs -f -L OMARCHY "$root_mapper"
756  for subvol in @ @home @log @pkg; do
```

したがって:

- **既存 ESP は読みも書きもされない。** 2 GiB の専用 ESP を空き領域に新規作成する。
  理由は UKI（Unified Kernel Image）が 100〜260 MiB の Windows ESP に入らないから。
  結果として `SYSTEM` (100M) と `OCESP` (200M) は無傷で残る。
- **最小 32 GiB**、うち 2 GiB が ESP。
- root は **LUKS の中に btrfs**、サブボリューム `@ @home @log @pkg`、
  `noatime,compress=zstd`。
- ブートローダは **Limine**（ESP パス `/EFI/limine`）。GRUB ではない。
- インストール先は**空き領域のうち最大のもの**を自動選択する（awk で領域を列挙して
  最大を採る）。したがって「空き領域を 1 つだけ作る」のが安全な運び方になる。

---

## 3. どこを削るか — 実測で決めた

最初は「macOS 側は削らない方がいい」と考えたが、測ったら逆だった。

```
APFS コンテナ (disk1 / 物理ストア disk0s6)
  容量          622,986,264,576 B  (623 GB)
  使用          33.4 GB
  最小          36.3 GB
  推奨最小      47.0 GB
```

**623 GB のコンテナに 33.4 GB しか入っていない。** 一方 Windows 側は 375.8 GB で
それなりに使っていた。Windows を `diskpart` で縮めるより、空の APFS を
`diskutil` で縮める方が操作も戻し方も単純。よって **APFS を縮める**方針に変更した。

分割は **macOS 400 GB : Linux 223 GB** に決定。

---

## 4. 作業手順と実際の出力

### 4-1. バックアップ（これが本番作業より重要）

| 対象 | 保存先 | 検証 |
|---|---|---|
| OpenCore ESP | `backup/ocesp-20260818-1629/ocesp-EFI-backup.tar.gz` | 101 MB / 1206 ファイル、`EFI/BOOT` + `EFI/OC` 全体（`config-vesa/accel/bt/bt2/dpcd0A/fb3EA5` の各バリアント含む）|
| インストール USB 丸ごと | `backup/usb-opencore-20260911/` | 1.8 GB。EFI バリアント 8 世代 + `opencore-2026-08-17-*.txt` 19 本 + `oldlogs/` + `pmc-revert`。`diff -rq` クリーン、ファイル数 9383 = 9383 |

USB の中身は **再生成不可のデバッグ資料**（動かなかった構成のスナップショットと
そのときのログ）だった。ISO を焼く前に気づけたのは運が良かった。
`bin/mkusb` で再構築できるのは「動く EFI + BaseSystem.dmg」だけで、
過去のバリアントは復元できない。

> **落とし穴:** rsync が exit 23 で止まる。原因は AppleDouble
> (`/Volumes/OPENCORE/EFI-panic-backup/._.` を stat できない)。
> `--exclude '._*'` を付けて再実行し、`diff -rq` とファイル数で検証した。

### 4-2. ISO の取得と検証

```
omarchy-4.0.3.iso   6,260,654,080 B (5.83 GiB)
sha256 -c omarchy-4.0.3.iso.sha256  →  omarchy-4.0.3.iso: OK
```

USB への書き込みは生デバイス指定で 8 分（23:04:03 → 23:12:20）:

```sh
sudo dd if=downloads/omarchy-4.0.3.iso of=/dev/rdiskN bs=4m
```

macOS の BSD dd に `status=progress` は無い。進捗は `Ctrl+T`（SIGINFO）で見る。
書き込み後は `FDisk_partition_scheme` + `0xEF` パーティションのハイブリッド ISO
として見える。

> **落とし穴:** 書き戻し検証の `sudo -n dd if=/dev/rdiskN` は
> パスワードプロンプトを出せずに失敗し、空入力の SHA-256
> (`e3b0c442…`) を返す。これを「一致した」と誤読しないこと。
> `ps -o pid,ppid` で dd が 2 プロセス見えるのも `sudo → sudo → dd` の
> 連鎖であって二重書き込みではない。

### 4-3. APFS コンテナの縮小

```sh
sudo diskutil apfs resizeContainer disk1 400g
```

```
Shrinking APFS Physical Store disk0s6 from 622,986,264,576 to 400,000,000,000 bytes
...
Finished APFS operation
```

FileVault はアンロック状態で実行。ストレージ整合性チェックは exit 0。

縮小後（macOS 側 `diskutil list` の見え方）:

```
s4  Blade Stealth (C:)   375.8 GB   変更なし
s5  EFI OCESP            209.7 MB   変更なし
s6  Apple_APFS           400.0 GB   縮小
    (free space)         223.0 GB   ← Omarchy の取り分
s7  Windows Recovery     960.5 MB   変更なし
```

> **注意:** 空き領域は 1 か所だけにしておく。インストーラは最大の空き領域を
> 自動選択するので、複数あると意図しない場所に入る。

### 4-4. インストール後の実際のパーティション構成

Omarchy 側 `lsblk` の出力（UUID は公開記録から除去）:

```
nvme0n1                931.5G
├─nvme0n1p1    100M  ntfs         RazerRecPar     Razer 回復パーティション
├─nvme0n1p2    100M  vfat         SYSTEM          Windows ESP      ← 無傷
├─nvme0n1p3     16M               (MSR)           Microsoft 予約
├─nvme0n1p4    350G  ntfs         Blade Stealth   Windows 11
├─nvme0n1p5    200M  vfat         OCESP           OpenCore ESP     ← 無傷
├─nvme0n1p6  372.5G  apfs                         macOS (= 400 GB 十進)
├─nvme0n1p7    916M  ntfs                         Windows RE
├─nvme0n1p8      2G  vfat         OMARCHY_EFI     ← 新規作成された専用 ESP
└─nvme0n1p9  205.7G  crypto_LUKS  OMARCHY_ROOT
  └─omarchy_root    btrfs         OMARCHY
```

**ESP が 3 つ並ぶ構成になる。** 宣言どおり既存 2 つは触られていない。

---

## 5. Limine の設定と起動順

### 5-1. `/etc/default/limine`

```
ESP_PATH="/boot"
KERNEL_CMDLINE[default]+="cryptdevice=UUID=<LUKS UUID>:omarchy_root root=/dev/mapper/omarchy_root
                          zswap.enabled=0 rootflags=subvol=@ rw rootfstype=btrfs"
ENABLE_LIMINE_FALLBACK=no
```

カーネルは 7.2.3-arch1-3、UKI が `boot():/EFI/Linux/omarchy_linux.efi` に置かれ、
`limine-snapper-sync` が btrfs スナップショット（インストール直後の `4.0.3-1` が 1 本）を
サブメニューとして自動生成する。`hash_mismatch_panic: no`。

### 5-2. `limine-scan` は対話式で、1 回 1 エントリしか追加しない

これは事前に知っておくと楽だった点。`sudo limine-scan`（中身は
`limine-entry-tool --scan`）を実行すると、他 OS の EFI を列挙して選択を求めてくる:

```
#  | Name                 | EFI Path
1  | Windows Boot Manager | /EFI/MICROSOFT/BOOT/BOOTMGFW.EFI
2  | UEFI OS              | /EFI/BOOT/BOOTX64.EFI          ← OCESP 上の OpenCore
3  | Limine               | /EFI/limine/limine_x64.efi     ← 自分自身
Choice:
New entry name:
```

- **`os-prober` は使わない**（未インストール）。ESP を自前で走査している。
- 番号を選ぶと **エントリ名を聞かれる**。`#2` の既定名は `UEFI OS` で何だか
  分からないので `macOS` に上書きした。
- 追加は 1 回 1 件。Windows と macOS の 2 つを入れるには 2 回実行する。
- `#2` が本当に OpenCore かは GPT UUID を `lsblk -o NAME,PARTUUID,LABEL` と
  突き合わせて確認した（`OCESP` = nvme0n1p5）。ここは推測しない方がいい。

結果の `/boot/limine.conf`:

```
/+Omarchy               order-priority=50   → linux 7.2.3-arch1-3 + Snapshots
/Windows Boot Manager   order-priority=20   → uuid(<SYSTEM の PARTUUID>):/EFI/Microsoft/Boot/bootmgfw.efi
/macOS                  order-priority=20   → uuid(<OCESP の PARTUUID>):/EFI/BOOT/BOOTx64.efi
```

### 5-3. ファームウェアの起動順 — OpenCore は独立して残る

```
BootOrder: 0003,0001,0000,0002
  0003* Limine                (p8 OMARCHY_EFI)   ← 既定
  0001* UEFI OS               (p5 OCESP)         ← OpenCore を直接起動
  0000* Windows Boot Manager  (p2 SYSTEM)
  0002* UEFI: USB CDROM       ← インストール USB（抜けば消える）
```

先頭が Limine なので、**通常起動で `F12` を押す必要はない**。電源を入れれば
Limine のメニューが出て、そこから 3 つの OS を選ぶ。

**これが一番重要な安全網:** Limine が壊れても OpenCore の NVRAM エントリは
独立して生きているので、`F12` → `UEFI OS` で macOS に直行できる。
Limine 経由の macOS 起動は「Limine が OpenCore を chainload し、
OpenCore が自分のピッカーを出す」二段構えになる。

### 5-4. fwupd は入っていない

BIOS 誤更新を防ぐために `fwupd` を無効化しようとしたが、**Omarchy には
`fwupd` も `os-prober` も入っていない**（`systemctl list-unit-files 'fwupd*'`
が 0 件、`pacman -Q fwupd` が not found）。無効化作業は不要。
ただし後から何かの依存で入る可能性はあるので、`pacman -Q fwupd` は
時々見ておくとよい。

---

## 6. 容量を後から再配分したい場合

**APFS を増やす方向は素直にはできない。** ディスク上の並びが

```
… [ p6 APFS ] [ p7 WinRE ] [ p8 OMARCHY_EFI ] [ p9 OMARCHY_ROOT ] 末端
```

なので、p9 を縮めて空けた領域は **p6 と隣接しない**（間に p7 と p8 が挟まる）。
APFS は末尾方向にしか伸ばせないため、隣接しない空きは使えない。

現実的な手段:

- **Linux を増やす方向**は簡単。p9 の後ろに空きを作れば `btrfs` を伸ばせる。
- **macOS を増やしたい**なら、間に挟まる p7 / p8 を動かす必要がある。
  素直にやるなら「Linux を消して APFS を伸ばし、また入れ直す」。
- あるいは **btrfs のマルチデバイス機能**を使う。別領域を
  `btrfs device add` で足して 1 つのファイルシステムとして扱い、
  不要になったら `btrfs device delete` で抜く（データは自動で退避される）。
  パーティションが物理的に連続していなくても構わないのが利点。

---

## 7. ハマりどころ（本機固有）

### 7-1. インストーラのキーボードレイアウトで `@` が打てない

内蔵キーボードは **US / ANSI**。根拠は macOS 側の登録値
（`docs/hardware-findings.md` の該当節）:

```
/Library/Preferences/com.apple.keyboardtype.plist
  "569-5426-0" => 40      Razer Blade 内蔵キーボード     # 40 = ANSI
```

インストーラで JP を選ぶと `@` `[` `]` の位置がずれる。レイアウトは `us` にする。

> **危険:** LUKS のパスフレーズを**間違ったレイアウトで設定してしまうと、
> 起動時（正しいレイアウト）では二度と入力できなくなる。**
> 記号を含むパスフレーズを入れる前にレイアウトを確定させること。

インストール後に直す場合:

- Hyprland 側: `~/.config/hypr/input.conf` の `kb_layout = us`
  （または `omarchy-menu` → Settings → Keyboard）
- コンソール側: `sudo localectl set-keymap us` / `set-x11-keymap us`

### 7-2. macOS と Omarchy が同じ IP を取り合う

同一 NIC なので DHCP で同じアドレスが振られる。`docs/hardware-findings.md` に
macOS / Windows で同じ問題を記録済み（ホスト鍵の衝突）。今回は Omarchy 用に
**known_hosts を分離**して回避した:

```
Host razer-omarchy
    HostName <LAN IP>
    User <user>
    IdentityFile ~/.ssh/razer_hackintosh
    UserKnownHostsFile ~/.ssh/known_hosts.omarchy
    StrictHostKeyChecking accept-new
```

`StrictHostKeyChecking=no` で警告を潰すのは**やってはいけない**（本物の
中間者攻撃と区別がつかなくなる）。恒久対処はルータ側の DHCP 予約を分けるか、
どちらかを固定 IP にすること。

### 7-3. Omarchy は初期状態で SSH が閉じている

`sshd` が起動していないだけでなく、**ufw が incoming deny** なので両方開ける:

```sh
sudo systemctl enable --now sshd
sudo ufw allow 22/tcp && sudo ufw reload
```

### 7-4. Mac から `!` プレフィクスで sudo は通らない

Claude Code のセッション内コマンドや非対話 SSH では TTY が無く、

```
sudo: a terminal is required to read the password
sudo: timed out reading password
```

で失敗する。実 TTY を用意する回避策:

```sh
osascript -e 'tell application "Terminal" to do script "ssh -t razer-omarchy \"sudo ...\""'
```

パスワードプロンプトはすぐ出る。放置するとタイムアウトして
**コマンドは実行されないまま次に進む**（`limine-scan` が走っていないのに
後続の `cp` だけ成功して騙されかけた）。

---

## 8. Claude Code (Amazon Bedrock 経由) を Omarchy 側に通す

Omarchy は **Claude Code を最初から入れる**（`install/user/mise.sh` の
`omarchy-mise-install claude`、`manual/17-ai.md` にも記載）。バイナリは
`~/.local/share/mise/shims/claude`。よって移す必要があるのは認証設定だけ。

Bedrock 認証は `~/.claude/settings.json` の `env` ブロックにある:

```
CLAUDE_CODE_USE_BEDROCK / AWS_REGION / AWS_BEARER_TOKEN_BEDROCK
ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL
ANTHROPIC_CUSTOM_MODEL_OPTION{,_NAME,_DESCRIPTION}
```

Bearer Token 方式なので `~/.aws/credentials` は不要。

移送は **値を一切画面に出さずに** 行う:

1. 必要なキーだけ抜いた JSON を送出側で生成（`chmod 600`）
2. `scp` で相手の `/tmp` に置く
3. 既存 `settings.json` があるので**上書きせずマージ**（Omarchy は
   `{"theme": "dark"}` を先に書いている）。バックアップを取ってから
   `env` だけ更新し、`chmod 600`
4. 相手側の一時ファイルを `shred -u`、送出側の一時ファイルも削除
5. 動作確認は `claude -p "Reply with exactly: BEDROCK OK"`

> **注意:** これで **AWS Bedrock の長期 API キーがノート PC 上に置かれる**。
> root は LUKS 暗号化なので保存時は保護されるが、紛失・譲渡時は AWS 側で
> ローテートすること。

---

## 9. 次回起動時に確認すること

- `limine.conf` の `default_entry: 2` はインストーラが他 OS 追加前に書いた値。
  メニューで既定選択されるのが Omarchy かどうかを目で見て確認する。
- `#timeout: 3` はコメントアウトされているので Limine の既定（5 秒）で動く。
- macOS 側の Wi-Fi はスリープ復帰で落ちることがある（README 発見 25）。
  トリプルブートとは無関係だが、遠隔作業中に見失う原因になる。
