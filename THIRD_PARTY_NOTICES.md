# Third-Party Notices

MangaCrispのstandalone版が同梱する第三者コンポーネントと、
プラットフォームごとの由来を以下に記録します。

## 7-Zip（Windows版）

Windows one-folder版は、RAR/CBRの展開用に公式7-Zip x64版の
`7z.exe`と`7z.dll`を改変せず同梱します。

- Project: [7-Zip](https://www.7-zip.org/)
- Version: 26.02 x64
- License: GNU LGPL 2.1 or later、BSD 3-Clauseの構成要素、unRAR restriction
- Source: [7-Zip source](https://www.7-zip.org/download.html)

配布物の`licenses/`には7-Zipの`License.txt`、`readme.txt`、
取得元とSHA-256を記録した`7zip-provenance.json`を収録します。
7-Zipに含まれるunRARコードはRARアーカイブの展開だけに使用し、
RAR互換アーカイバの作成には使用しません。

## Real-CUGAN ncnn Vulkan

- Project: [nihui/realcugan-ncnn-vulkan](https://github.com/nihui/realcugan-ncnn-vulkan)
- Release: [20220728 macOS](https://github.com/nihui/realcugan-ncnn-vulkan/releases/tag/20220728)
- Archive: `realcugan-ncnn-vulkan-20220728-macos.zip`
- Archive SHA256: `0df908cbb98b480f85897221b96d37b0bdb70f82d81b2c7037fe950dd5c0fa33`
- Executable SHA256: `a59aa9acd89115e33d7d71d7e413b405237833f331bdc87d4e20099af0e5e819`
- License: MIT
- Copyright: Copyright (c) 2019 nihui

実行ファイルとモデルは公式リリースZIPから取得し、内容を改変せずアプリへ収録します。ビルドスクリプトはダウンロードしたZIPと実行ファイルのSHA256を照合します。

## Real-CUGAN models

- Project: [bilibili/ailab Real-CUGAN](https://github.com/bilibili/ailab/tree/main/Real-CUGAN)
- License: MIT
- Copyright: Copyright (c) 2022 bilibili

公式`realcugan-ncnn-vulkan`リポジトリと20220728リリースZIPには、`models-se`、`models-pro`、`models-nose`のモデルが含まれています。

## Statically linked dependencies

公式macOS実行ファイルのビルド定義に基づき、次のライセンス全文もstandaloneアプリへ収録します。

- [Tencent ncnn](https://github.com/Tencent/ncnn): BSD 3-Clauseおよび同梱第三者ライセンス
- [libwebp](https://github.com/webmproject/libwebp): BSD 3-Clause、追加特許許諾
- [MoltenVK v1.1.1](https://github.com/KhronosGroup/MoltenVK/releases/tag/v1.1.1): Apache License 2.0
- [LLVM OpenMP 11.0.0](https://github.com/llvm/llvm-project/tree/llvmorg-11.0.0/openmp): Apache License 2.0 with LLVM Exceptions

ライセンス全文は`MangaCrisp.app/Contents/Resources/licenses/`へ収録されます。PyInstallerのmacOSバンドル構造によっては、同じ場所へのシンボリックリンクが`Contents/Frameworks`側にも作られます。

## Python runtime and libraries

standalone版はPythonランタイム、PySide6/Qt、Pillow、py7zr、rarfileと、それらが利用するライブラリを同梱します。ビルド時にインストール済みパッケージのライセンスファイルを収集し、すべて`MangaCrisp.app/Contents/Resources/licenses/`へ収録します。

- Python: Python Software Foundation License
- PyInstaller bootloader/runtime: GPL 2.0 or later with the PyInstaller Bootloader Exception
- PySide6 / Qt: LGPL v3（または各プロジェクトが提示する選択ライセンス）
- Pillow: MIT-CMU
- py7zrおよび一部の圧縮ライブラリ: LGPL 2.1 or later
- rarfile: ISC
- setuptoolsおよびpackaging: MIT、Apache 2.0またはBSD系ライセンス

PySide6/Qtの正確なバージョン、対応ソース、動的リンクされたQtライブラリの場所と差し替え後の再署名方法は、アプリ内の`Qt-PySide6-source-and-relinking.txt`に記載します。Pillowが同梱する画像形式ライブラリなどの第三者表示は、Pillowのライセンスファイルに含まれます。

## Relationship to RAIV

MangaCrispは旧称RAIV for macとして[nalltama/RAIV](https://github.com/nalltama/RAIV)に着想を得た独立実装です。本家RAIVのコードをコピーしたforkではなく、本家の公式リリースでもありません。

この文書は同梱物の由来とライセンス表示を記録するもので、法的助言ではありません。
