# プロジェクトの継続と閲覧状況

MangaCrispは個人で開発している、MIT Licenseの無料ソフトウェアです。この文書では、
任意の支援をどう案内するか、アプリに利用解析を追加せずGitHub上の反応をどう確認するかを
説明します。

## 方針

- 読書履歴、本棚の内容、キャプチャ画像、利用状況を外部へ送信しません。
- 支援による機能解放やライセンス変更はありません。
- 金銭的な支援と、それ以外の協力を同じように歓迎します。
- 支援先は、このリポジトリに掲載したリンクだけを公式とします。

## 支援への導線

英語／日本語READMEでは、任意の支援リンクをダウンロード案内の近くに掲載します。
`.github/FUNDING.yml`によってGitHubのSponsorボタンにも同じBuy Me a Coffeeアカウントを
表示します。アプリ内ヘルプにも、利用中の人向けの控えめなリンクを残します。

支援はコード署名、Windows／macOS実機検証、ビルドサービス、開発用AI・APIなど、
リリースを続けるための費用に使います。Starや共有、再現手順付きの不具合報告、異なる
ハードウェアでのテスト、コード／文書の改善も重要な支援です。

## GitHubで確認できること

管理者は**Insights > Traffic**で、直近14日間のリポジトリ表示数、ユニーク訪問者、
full clone数、ユニークcloner数を確認できます。cloneはインストール数や利用者数ではなく、
開発環境や自動処理が含まれる場合があります。

GitHub Releaseの各assetには累計`download_count`があります。これはファイルごとの取得回数で、
ユニーク人数、起動成功数、継続利用者数ではありません。再ダウンロードや自動処理も含まれます。

Star、fork、issue、pull requestも反応を見る材料ですが、どれもアクティブ利用者数では
ありません。その数字を得るためだけにMangaCrispへ利用解析を追加することはしません。

## メンテナー向け確認手順

認証済みのGitHub CLIで、次のコマンドから再現可能なスナップショットを取得できます。

```bash
gh api repos/jydie5/MangaCrisp/traffic/views
gh api repos/jydie5/MangaCrisp/traffic/clones
gh api repos/jydie5/MangaCrisp/releases --paginate \
  --jq '.[] | .assets[] | [.name, .download_count] | @tsv'
gh repo view jydie5/MangaCrisp \
  --json stargazerCount,forkCount,watchers,issues
```

変動するカウンターをREADMEに置くのではなく、月1回程度、リリースごとのasset取得数、
役立つissue、異なる実機での検証状況を比較します。clone数はリポジトリ活動の目安として扱い、
読者数として公表しません。
