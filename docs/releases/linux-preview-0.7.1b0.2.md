# MangaCrisp for Linux — Preview 0.7.1b0.2

This update fixes importing RAR/CBR books on Linux. If RAR files did not appear
on your bookshelf with 0.7.1b0.1, please update.

## Fixes

- **RAR and CBR import now works without a system `unrar`.** Pages are
  extracted with the bundled, pinned 7-Zip when no unrar-compatible tool is
  installed.
- **Multi-volume archives split correctly.** An archive that contains several
  volumes in separate folders now becomes one book per volume with only that
  volume's pages. Previously each book could receive every page when the
  bundled 7-Zip was used (this affected all platforms).

Everything else is unchanged from
[0.7.1b0.1](https://github.com/jydie5/MangaCrisp/releases/tag/linux-preview-0.7.1b0.1).

## Update

Extract the new archive and run `MangaCrisp/install.sh` again. Your library and
settings are kept. Verify the download with `SHA256SUMS.txt`.

## Support MangaCrisp

MangaCrisp is free, MIT-licensed, and made by one independent developer. If it
makes your reading better, **[please support it on Buy Me a Coffee](https://buymeacoffee.com/jydie5)**.
Support pays for AMD/Intel test hardware for Linux, build services, and
development time. Stars, shares, and GPU/distribution reports help too.

---

## 日本語

Linux で RAR／CBR の本を取り込めなかった問題を修正しました。0.7.1b0.1 で RAR が
本棚に入らなかった場合は更新してください。

- **システムに `unrar` がなくても RAR／CBR を取り込めます。** unrar 互換のツールがない
  場合は、同梱の固定・検証済み 7-Zip でページを展開します。
- **複数巻をまとめたアーカイブを正しく分割します。** 巻ごとのフォルダを含むアーカイブが、
  巻ごとに 1 冊ずつ、その巻のページだけで取り込まれます。これまでは同梱の 7-Zip を
  使った場合に、各冊に全ページが入ることがありました（全 OS 共通の不具合）。

更新するには、新しいアーカイブを展開して `MangaCrisp/install.sh` をもう一度実行します。
ライブラリと設定はそのまま残ります。

MangaCrisp は個人開発の無料・MIT ライセンスのソフトウェアです。役に立ったら
**[Buy Me a Coffee で支援していただけるとうれしいです](https://buymeacoffee.com/jydie5)**。
支援は Linux 用の AMD／Intel 検証機材、ビルドサービス、開発時間に使います。
