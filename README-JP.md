[![Blender](https://img.shields.io/badge/Blender->=2.9-blue?logo=blender&logoColor=white)](https://www.blender.org/download/ "Download Blender")
[![GitHub release](https://img.shields.io/github/release/DarklightGames/io_scene_psk_psa?include_prereleases=&sort=semver&color=blue)](https://github.com/DarklightGames/io_scene_psk_psa/releases/)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/L4L3853VR)

この Blender アドオンを使用すると、Unreal Engine の多くのバージョンで使用されている [PSK および PSA ファイル形式](https://wiki.beyondunreal.com/PSK_%26_PSA_file_formats) との間でメッシュとアニメーションをインポートおよびエクスポートできます。

# 互換性

| Blenderのバージョン                                              | アドオンのバージョン                                                                  | Long Term Support |
|--------------------------------------------------------------|--------------------------------------------------------------------------------|-------------------|
| 4.0+                                                         | [最新](https://github.com/DarklightGames/io_scene_psk_psa/releases/latest)   | 未定                |
| [3.4 - 3.6](https://www.blender.org/download/lts/3-6/)       | [5.0.5](https://github.com/DarklightGames/io_scene_psk_psa/releases/tag/5.0.5) | ✅️ 2025年6月        |
| [2.93 - 3.3](https://www.blender.org/download/releases/3-3/) | [4.3.0](https://github.com/DarklightGames/io_scene_psk_psa/releases/tag/4.3.0) | ✅️ 202年9月       |

バグ修正は、[Blender の LTS メンテナンス期間](https://www.blender.org/download/lts/)中のレガシー アドオン バージョンに対して発行されます。 LTS 期間が終了すると、レガシー アドオン バージョンはこのリポジトリのメンテナによってサポートされなくなりますが、バグ修正のためのプル リクエストは受け付けます。

# 機能
* PSK および PSA ファイルをインポートする。
* 非標準のファイル セクション データ (頂点法線、追加の UV チャンネル、頂点カラー、シェイプ キーなど) をインポートします。
* 多数のシーケンスを含む PSA ファイルを操作する場合の効率的なワークフローのためのきめ細かい PSA シーケンス インポート。
* PSA シーケンスのメタデータ (フレーム レートなど) はインポート時に保存されるため、このデータをエクスポート時に再利用できます。
* ボーン コレクションは PSK/PSA エクスポートから除外できます。 これは、IK コントローラなどの寄与しないボーンを除外する場合に便利です。
* PSA シーケンスは、アクションから直接エクスポートすることも、シーンの [タイムライン マーカー](https://docs.blender.org/manual/ja/latest/animation/markers.html) または NLA トラック ストリップを使用して描写することもでき、[NLA](https://docs.blender.org/manual/ja/latest/editors/nla/index.html) シーケンスを作成するとき。
* 複数のメッシュ オブジェクトをエクスポートするときにマテリアル スロットを手動で並べ替えます。

# 取り付け
1. 最新バージョンの zip ファイルを [Releases](https://github.com/DarklightGames/io_export_psk_psa/releases) ページからダウンロードします。
2. Blender 4.0.0 以降を開きます。
3. Blender の設定に移動します (`編集` > `プリファレンス`)。
4. `アドオン`タブを選択します。
5. `インストール...`ボタンをクリックします。
6. 先ほどダウンロードした `.zip` ファイルを選択し、`アドオンのインストール`をクリックします。
7. 新しく追加された`インポート-エクスポート: PSK/PSA Importer/Exporter`アドオンを有効にします。

# 使用方法
## PSKのエクスポート
1. エクスポートするアーマチュア オブジェクトを選択します。
2. `ファイル` > `エクスポート` > `Unreal PSK (.psk)`に移動します.
3. ファイル名を入力して`エクスポート`をクリックします.

## PSK/PSKXのインポート
1. `ファイル` > `インポート` > `Unreal PSK (.psk/.pskx)`に移動します.
2. インポートしたい PSK ファイルを選択し、`インポート`をクリックします。

## PSAのエクスポート
1. エクスポートするアーマチュア オブジェクトを選択します。
2. `ファイル` > `エクスポート` > `Unreal PSA (.psa)`に移動します.
3. ファイル名を入力し、`エクスポート`をクリックします。

## PSAのインポート
1. アニメーションを読み込みたいアーマチュアを選択します。
2. `ファイル` > `インポート` > `Unreal PSA (.psa)`に移動します。
3. アニメーションのインポート元となる PSA ファイルを選択します.
4. インポートしたいアニメーションを選択し、`インポート`をクリックします。

> アーマチュアに適用されたインポートされたアクションを確認するには、[ドープ シート](https://docs.blender.org/manual/ja/latest/editors/dope_sheet/introduction.html) エディタまたは [ノンリニアアニメーション](https://docs.blender.org/manual/ja/latest/editors/nla/introduction.html) エディタを使用する必要があります。

## ローカライゼーション

現在、次の言語がサポートされています。

| 言語 | 地位 | 方法 |
|-|-|-|
| 英語 (English) | ✅️ | 🧑 |
| 日本語 | ✅️ | 🤖 | 

翻訳に問題がある場合は、お気軽に [Weblate](https://weblate.darklightgames.com/projects/io_scene_psk_psa/) に修正を送信してください。

自分の母国語に対するサポートの追加をご希望の場合は、[問題を報告して](http://github.com/DarklightGames/io_scene_psk_psa/issues)ください。

# FAQ

## PSA をインポートした後にアニメーションが表示されないのはなぜですか?

PSA アニメーションをインポートしても、アクションはアーマチュアに自動的に適用されません。これは、PSA には複数のシーケンスをインポートできるため、また、インポーターが必要のないときにシーンを変更するのは悪い形式であるためです。

PSA インポーターは、PSA 内の選択されたシーケンスごとに[アクション](https://docs.blender.org/manual/ja/latest/animation/actions.html)を作成します。これらのアクションは、[アクション エディター](https://docs.blender.org/manual/ja/latest/editors/dope_sheet/action.html)または [NLA エディター](https://docs.blender.org/manual/ja/latest/editors/nla/index.html)を介してアーマチュアに適用できます。

## [UE Viewer](https://www.gildor.org/en/projects/umodel) から抽出した PSK をインポートすると、メッシュ面の法線が不正確になるのはなぜですか?

モデルのメッシュ法線を保持することがワークフローにとって重要な場合、UE Viewer から PSK ファイルをエクスポートすることはお勧めできません。これは、UE Viewer が元の[スムージング グループ](https://en.wikipedia.org/wiki/Smoothing_group)を再構築しようとしないためです。その結果、インポートされた PSK ファイルの法線は、Blender にインポートされたときに不正確になるため、手動で修正する必要があります。

回避策として、[glTF](https://en.wikipedia.org/wiki/GlTF) 形式は明示的な法線をサポートしており、UE Viewer はエクスポート時にメッシュ法線を正しく保存できるため、代わりに UE Viewer から glTF メッシュをエクスポートすることをお勧めします。ただし、インポートされた glTF アーマチュアは、Blender にインポートされたときにボーンの方向が間違っている可能性があります。これを軽減するには、PSK のアーマチュアと glTF のメッシュを組み合わせて最良の結果を得ることができます。
