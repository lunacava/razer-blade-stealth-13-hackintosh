# Mac mini → Razer 有線インターネット共有

macOS インストール中の Razer にネットワークを供給するための構成。
**macOS 26.5.1 (25F80) で確立**。2026-08-17。

## なぜ必要か

| 経路 | 状態 |
|---|---|
| Razer の WiFi | **インストーラでは使えない**。AirportItlwm 2.3.0 は Sonoma 14.4 用ビルドで、リカバリは 14.6.1 |
| Razer の有線 (ASIX USB-GbE) | ケーブルは Mac mini と**直結**。ルータには繋がっていないので単体では外に出られない |

→ Mac mini の WiFi を有線側に NAT して渡す。

## 構成

```
インターネット
    │
  ルータ 192.168.2.1
    │ WiFi
Mac mini en1 192.168.2.108   ← SSH はここ。無変更
         en8 10.42.0.1       ← NAT ゲートウェイ + DHCP サーバ
    │ USB-LAN 直結
Razer    10.42.0.10          ← DHCP で取得
```

### ⚠ サブネットを 192.168.2.0/24 にしてはいけない

**macOS のインターネット共有はデフォルトで `192.168.2.0/24` を配る。**
既存 LAN がまさにそれなので、素で有効にすると en8 が `192.168.2.1` を主張して
**ルータと IP が衝突し、WiFi 経由の SSH が落ちる**。

→ `10.42.0.0/24` にずらして回避した。既存 LAN には一切触らない。

## 使い方

```sh
# 有効化（GUI 認証ダイアログが出る）
osascript -e 'do shell script "/Users/macmini/dev/Razer_mac/tools/share-on.sh" with administrator privileges'

# 無効化（元の設定に復元）
osascript -e 'do shell script "/Users/macmini/dev/Razer_mac/tools/share-off.sh" with administrator privileges'
```

`sudo` は TTY が無いと動かない（`!` 経由も不可）ので `osascript ... with
administrator privileges` を使う。**パスワードが会話に出ない**利点もある。

## ハマった点（4 つ、すべて解決）

### 1. サービス名が変わっている

macOS 26 では **`com.apple.InternetSharing` → `com.apple.NetworkSharing`**。
`/System/Library/LaunchDaemons/com.apple.InternetSharing.plist` は**存在しない**。
バイナリは `/usr/libexec/InternetSharing` のまま。

### 2. bootpd は launchctl では起動できない

`/System/Library/LaunchDaemons/bootps.plist` は:

```
"Disabled" => true                    ← plist に直接書かれている
"inetdCompatibility" => {"Wait" => true}   ← オンデマンド起動
```

`launchctl enable` は override DB を書くだけで**この `Disabled` には勝てない**。
さらに inetd 互換モードなので「UDP/67 にパケットが来たら起動」する設計だが、
誰も 67 番を LISTEN していないので**そのトリガーが永久に成立しない**。

→ 独自の常駐デーモンとして動かす（`tools/bootpd-daemon.plist`）:

```
/usr/libexec/bootpd -d -D -i en8    # -d 前景 / -D DHCP サーバ
→ /Library/LaunchDaemons/local.razer.bootpd.plist
```

### 3. ★ pf.conf はルールの順序が固定

これが NAT が効かなかった真因。

```
/etc/pf.conf:28: Rules must be in order:
  options -> normalization -> queueing -> translation -> filtering
```

`nat-anchor` は **translation** なので `anchor "com.apple/*"`（filtering）より
**前**に置く必要がある。末尾に追記すると**ルールセット全体がパース失敗**し、
NAT ルールが 1 つもロードされない（`pfctl -a ... -s nat` が
`DIOCGETRULES: Invalid argument`）。しかも**エラーは静かに無視される**。

→ `rdr-anchor "com.apple/*"` の直後に挿入する。`load anchor` は順序制約の無い
ディレクティブなので末尾でよい:

```
scrub-anchor "com.apple/*"
nat-anchor "com.apple/*"
rdr-anchor "com.apple/*"
nat-anchor "local.razer.share"      ← ここ
dummynet-anchor "com.apple/*"
anchor "com.apple/*"
load anchor "com.apple" from "/etc/pf.anchors/com.apple"
load anchor "local.razer.share" from "/etc/pf.anchors/local.razer.share"
```

投入前に `pfctl -n -f` で検証し、失敗したら自動で `/etc/pf.conf.razer-orig`
に戻すようにした。

### 4. `set -e` + `lsof` でスクリプトが自死

`lsof` は該当なしで **exit 1** を返す。`set -e` と組み合わせると表示処理の途中で
スクリプトが止まり、「エラーで失敗した」ように見えて**実際は設定済み**という
紛らわしい状態になる。→ 報告系コマンドは全部 `|| true` を付けた。

## 検証結果

```
bootpd  71426 root  3u  IPv4  UDP *:67          ← DHCP サーバ稼働
/var/db/dhcpd_leases:  DESKTOP-XXXXXXX = 10.42.0.10
pfctl -a local.razer.share -s nat:
  nat on en1 inet from 10.42.0.0/24 to any -> (en1) round-robin

Razer 側（送信元を有線に固定して検証）:
  ping 1.1.1.1 -S 10.42.0.10        → 0% loss, 9ms
  TCP 443 → 17.253.144.10 (Apple)   → CONNECTED, local 10.42.0.10:50671
  Resolve-DnsName apple.com          → OK
```

## 注意

- **WiFi を無効化して検証してはいけない。** SSH が WiFi 経由なので切断される
  （実際にやって切れた。`Enable-NetAdapter` で約 40 秒後に自動復帰した）。
  送信元 IP を固定する `ping -S` / `Socket.Bind()` で有線経路だけを検証できる。
- **有線側は SSH が通らない**（`10.42.0.10:22` タイムアウト）。Windows Firewall が
  有線を別プロファイル扱いしているため。WiFi 経由の SSH を使う。
- **macOS インストーラで ASIX USB-GbE が認識されるかは未検証。** 認識されなければ
  この共有も無意味なので、実機で `ifconfig` を確認する必要がある。
  （ルータ直結にしても同じ問題が出るので、共有方式固有の弱点ではない）

## 作業完了後

```sh
osascript -e 'do shell script "/Users/macmini/dev/Razer_mac/tools/share-off.sh" with administrator privileges'
```

`/etc/bootpd.plist` / `com.apple.nat.plist` / `/etc/pf.conf` を
`tools/backup-netshare/` と `/etc/pf.conf.razer-orig` から復元し、
`local.razer.bootpd` を削除、forwarding を 0 に戻す。
