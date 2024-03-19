langs = {'ja': {('*', 'Action Metadata'): 'アクションメタデータ',
        ('*', 'Additional data will be written to the properties of the Action (e.g., frame rate)'): 'アクションのプロパティに追加データが書き込まれます '
                                                                                                     '(フレームレートなど)',
        ('*', 'All bones will be exported'): 'すべてのボーンがエクスポートされます',
        ('*', 'All selected meshes must have the same armature modifier, encountered {count} ({names})'): '選択したすべてのメッシュには同じアーマチュア修飾子が必要です。検出されたアーマチュア修飾子は '
                                                                                                          '{count} '
                                                                                                          '({names})',
        ('*', 'An armature must be selected'): 'アーマチュアを選択する必要があります',
        ('*', 'An armature object must be supplied'): 'アーマチュアオブジェクトを指定する必要があります',
        ('*', 'Assign each imported action a fake user so that the data block is always saved'): 'インポートされた各アクションにフェイクユーザーを割り当てて、データブロックが常に保存されるようにします',
        ('*', 'At least one bone must be marked for export'): '少なくとも 1 '
                                                              'つのボーンをエクスポート対象としてマークする必要があります',
        ('*', 'At least one mesh must be selected'): '少なくとも 1 '
                                                     'つのメッシュを選択する必要があります',
        ('*', 'Bone Collections'): 'ボーンコレクション',
        ('*', 'Bone Filter'): 'ボーンフィルター',
        ('*', 'Bone Length'): 'ボーンの長さ',
        ('*', 'Bone Name Mapping'): 'ボーン名マッピング',
        ('*', 'Bone name "{name}" contains characters that cannot be encoded in the Windows-1252 codepage'): 'ボーン名「{name}」には、Windows-1252 '
                                                                                                             'コードページではエンコードできない文字が含まれています',
        ('*', 'Bone names must match exactly'): 'ボーン名は正確に一致する必要があります',
        ('*', 'Bone names restrictions will be enforced. Note that bone names without properly formatted names may not be able to be referenced by some versions of the Unreal Engine'): 'ボーン名の制限が適用されます。ボーン名が正しくフォーマットされていないと、Unreal '
                                                                                                                                                                                         'Engine '
                                                                                                                                                                                         'のバージョンによっては参照できない場合があることに注意してください',
        ('*', 'Bones'): 'ボーンズ',
        ('*', "Bones names must match, ignoring case (e.g., the PSA bone 'aBcDeF' can be mapped to the armature bone 'ABCDEF')"): 'ボーンの名前は大文字と小文字を区別しないで一致する必要があります '
                                                                                                                                  '(例:PSAボーン '
                                                                                                                                  "'abcDef' "
                                                                                                                                  'はアーマチュアボーン '
                                                                                                                                  "'ABCDEF' "
                                                                                                                                  'にマッピングできます)',
        ('*', 'Case Insensitive'): '大文字と小文字を区別しない',
        ('*', 'Compression Ratio'): '圧縮率',
        ('*', 'Context'): 'コンテキスト',
        ('*', 'Convert keyframes to read-only samples. Recommended if you do not plan on editing the actions directly'): 'キーフレームを読み取り専用サンプルに変換します。アクションを直接編集する予定がない場合におすすめです',
        ('*', 'Convert to Samples'): 'サンプルに変換',
        ('*', 'Custom FPS'): 'カスタム FPS',
        ('*', 'Deselect All'): 'すべて選択解除',
        ('*', 'Deselect all bone collections'): 'すべてのボーンコレクションを選択解除',
        ('*', 'Deselect all visible sequences'): '表示されているシーケンスをすべて選択解除',
        ('*', 'Discarded {count} invalid face(s)'): '{count} 個の無効なフェースが廃棄されました',
        ('*', 'Each sequence name should be on a new line'): '各シーケンス名は新しい行にする必要があります',
        ('*', 'Enforce Bone Name Restrictions'): 'ボーン名制限を強制',
        ('*', 'Enforce that bone names must only contain letters, numbers, spaces, hyphens and underscores.\n\nDepending on the engine, improper bone names might not be referenced correctly by scripts'): 'ボーン名には文字、数字、スペース、ハイフン、アンダースコアのみを含めるようにしてください。\n'
                                                                                                                                                                                                            '\n'
                                                                                                                                                                                                            'エンジンによっては、不適切なボーン名がスクリプトで正しく参照されない場合があります',
        ('*', 'Exact'): '正確',
        ('*', 'Export'): 'エクスポート',
        ('*', 'Export actions to PSA'): 'アクションを PSA にエクスポート',
        ('*', 'Export mesh and armature to PSK'): 'メッシュとアーマチュアを PSK にエクスポート',
        ('*', 'Extra UVs'): '追加のUV',
        ('*', 'FPS Source'): 'FPS ソース',
        ('*', 'Failed to read PSA config file: {error}'): 'PSA '
                                                          '構成ファイルを読み込めませんでした:{error}',
        ('*', 'Fake User'): 'フェイクユーザー',
        ('*', 'File Path'): 'ファイルパス',
        ('*', 'File path used for exporting the PSA file'): 'PSA '
                                                            'ファイルのエクスポートに使用するファイルパス',
        ('*', 'File path used for exporting the PSK file'): 'PSK '
                                                            'ファイルのエクスポートに使用するファイルパス',
        ('*', 'File path used for importing the PSA file'): 'PSA '
                                                            'ファイルのインポートに使用するファイルパス',
        ('*', 'Filter by Name'): '名前で絞り込む',
        ('*', 'Filter using regular expressions'): '正規表現を使用してフィルタリングする',
        ('*', 'Flags'): '国旗',
        ('*', "If an action with a matching name already exists, the existing action will have it's data overwritten instead of a new action being created"): '一致する名前のアクションが既に存在する場合、新しいアクションが作成されるのではなく、既存のアクションのデータが上書きされます',
        ('*', 'Import'): 'インポート',
        ('*', 'Import Extra UVs'): '追加の UV をインポート',
        ('*', 'Import Shape Keys'): 'シェイプキーをインポート',
        ('*', 'Import Vertex Colors'): '頂点カラーをインポート',
        ('*', 'Import Vertex Normals'): '頂点法線をインポート',
        ('*', 'Import extra UVs, if available'): '追加の UV (可能な場合) をインポートする',
        ('*', 'Import shape keys, if available'): 'シェイプキーをインポートする (可能な場合)',
        ('*', 'Import the selected animations into the scene as actions'): '選択したアニメーションをアクションとしてシーンにインポートします',
        ('*', 'Import vertex colors, if available'): '頂点カラーをインポート (可能な場合)',
        ('*', 'Import vertex normals, if available'): '頂点法線 (可能な場合) をインポートする',
        ('*', 'Invert filtering (show hidden items, and vice versa)'): '反転フィルタリング '
                                                                       '(隠しアイテムを表示、その逆)',
        ('*', 'Keyframe Quota'): 'キーフレームクォータ',
        ('*', 'Load a PSK file'): 'PSK ファイルを読み込む',
        ('*', 'Material name "{name}" contains characters that cannot be encoded in the Windows-1252 codepage'): 'マテリアル名「{name}」には、Windows-1252 '
                                                                                                                 'コードページではエンコードできない文字が含まれています',
        ('*', 'Material slot cannot be empty (index {index})'): 'マテリアルスロットを空にすることはできません '
                                                                '(index '
                                                                '{index})',
        ('*', 'Materials'): 'マテリアル',
        ('*', 'Metadata'): 'メタデータ',
        ('*', 'Modulate'): '変調する',
        ('*', 'Move the selected material down one slot'): '選択したマテリアルを 1 '
                                                           'スロット下に移動',
        ('*', 'Move the selected material up one slot'): '選択したマテリアルを 1 '
                                                         'つ上のスロットに移動',
        ('*', 'NLA Track'): 'NLA トラック',
        ('*', 'NLA Track Index'): 'NLA トラックインデックス',
        ('*', 'NLA Track Strips'): 'NLA トラックストリップ',
        ('*', 'No NLA track strips were selected for export'): 'エクスポート対象の NLA '
                                                               'トラックストリップが選択されていません',
        ('*', 'No Smooth'): 'スムーズなし',
        ('*', 'No actions were selected for export'): 'エクスポートするアクションが選択されていません',
        ('*', 'No animation data for object "{name}"'): 'オブジェクト「{name}」のアニメーションデータはありません',
        ('*', 'No bones available for export'): 'エクスポートできるボーンはありません',
        ('*', 'No modifiers will be evaluated as part of the exported mesh'): 'エクスポートされたメッシュの一部として評価されるモディファイヤはありません',
        ('*', 'No sequences selected'): 'シーケンスが選択されていません',
        ('*', 'No text block selected'): 'テキストブロックが選択されていません',
        ('*', 'No timeline markers were selected for export'): 'エクスポートするタイムラインマーカーが選択されていません',
        ('*', 'Normal Two-Sided'): 'ノーマル両面',
        ('*', 'Nothing to import'): 'インポートするものはありません',
        ('*', 'Only Show Selected'): '選択したものだけを表示',
        ('*', 'Only bones belonging to the selected bone collections and their ancestors will be exported'): '選択したボーンコレクションに属するボーンとその祖先だけがエクスポートされます',
        ('*', "Only show items matching this name (use '*' as wildcard)"): 'この名前に一致するアイテムのみを表示 '
                                                                           '(ワイルドカードとして「*」を使用)',
        ('*', 'Only show selected sequences'): '選択したシーケンスのみを表示',
        ('*', 'Override Animation Data'): 'アニメーションデータをオーバーライドする',
        ('*', 'PSA Export'): 'PSA エクスポート',
        ('*', 'PSA export successful'): 'PSA のエクスポートが成功しました',
        ('*', 'PSK Material'): 'PSK マテリアル',
        ('*', 'PSK export successful'): 'PSK のエクスポートが成功しました',
        ('*', 'PSK imported ({name})'): 'PSK がインポートされました ({name})',
        ('*', 'PSK imported with {count} warning(s)'): 'PSK が {count} '
                                                       'という警告とともにインポートされました',
        ('*', 'PSK/PSA Import/Export (.psk/.psa)'): 'PSK/PSA インポート/エクスポート '
                                                    '(.psk/.psa)',
        ('*', 'PSK/PSA Importer/Exporter'): 'PSK/PSA インポーター/エクスポーター',
        ('*', 'Prefix Action Name'): 'プレフィックスアクション名',
        ('*', 'Raw Mesh Data'): '未加工メッシュデータ',
        ('*', 'Regular Expression'): '正規表現',
        ('*', 'RemoveTracks'): 'トラックを削除',
        ('*', 'Reversed'): '逆転しました',
        ('*', 'Root Motion'): 'ルートモーション',
        ('*', 'Select All'): 'すべて選択',
        ('*', 'Select By Text List'): 'テキストリストで選択',
        ('*', 'Select a PSA file'): 'PSA ファイルを選択',
        ('*', 'Select all bone collections'): 'すべてのボーンコレクションを選択',
        ('*', 'Select all visible sequences'): '表示されているシーケンスをすべて選択',
        ('*', 'Select sequences by name from text list'): 'テキストリストから名前でシーケンスを選択',
        ('*', 'Selected object must be an Armature'): '選択したオブジェクトはアーマチュアでなければなりません',
        ('*', 'Selected {count} sequence(s)'): '選択した {count} シーケンス',
        ('*', 'Sequence'): 'シーケンス',
        ('*', 'Sequence name "{name}" contains characters that cannot be encoded in the Windows-1252 codepage'): 'シーケンス名「{name}」には、Windows-1252 '
                                                                                                                 'コードページではエンコードできない文字が含まれています',
        ('*', 'Sequences'): 'シーケンス',
        ('*', 'Sequences are delineated by scene timeline markers'): 'シーケンスはシーンのタイムラインマーカーによって描かれます',
        ('*', 'Sequences are delineated by the start & end times of strips on the selected NLA track'): 'シーケンスは、選択した '
                                                                                                        'NLA '
                                                                                                        'トラックのストリップの開始時間と終了時間によって示されます',
        ('*', 'Sequences will be exported using actions'): 'シーケンスはアクションを使用してエクスポートされます',
        ('*', 'Shape Keys'): 'シェイプキー',
        ('*', 'Show actions that belong to an asset library'): 'アセットライブラリに属するアクションを表示',
        ('*', 'Show reversed sequences'): '逆のシーケンスを表示',
        ('*', 'Source'): 'ソース',
        ('*', 'Stash each imported action as a strip on a new non-contributing NLA track'): 'インポートした各アクションを、コントリビューションされていない新しい '
                                                                                            'NLA '
                                                                                            'トラックにストリップとして保存する',
        ('*', 'The active object must be an armature'): 'アクティブオブジェクトはアーマチュアでなければなりません',
        ('*', 'The frame rate of the exported sequence'): 'エクスポートされたシーケンスのフレームレート',
        ('*', 'The frame rate to which the imported sequences will be resampled to'): 'インポートしたシーケンスをリサンプリングするときのフレームレート',
        ('*', "The frame rate will be determined by action's FPS property found in the PSA Export panel.\n\nIf the Sequence Source is Timeline Markers, the lowest value of all contributing actions will be used"): 'フレームレートは、PSA '
                                                                                                                                                                                                                     'Export '
                                                                                                                                                                                                                     'パネルにあるアクションの '
                                                                                                                                                                                                                     'FPS '
                                                                                                                                                                                                                     'プロパティによって決まります。\n'
                                                                                                                                                                                                                     '\n'
                                                                                                                                                                                                                     'シーケンスソースがタイムラインマーカーの場合、関連するすべてのアクションのうち最も低い値が使用されます',
        ('*', 'The keyframe sampling ratio of the exported sequence.\n\nA compression ratio of 1.0 will export all frames, while a compression ratio of 0.5 will export half of the frames'): 'エクスポートされたシーケンスのキーフレームサンプリング比。\n'
                                                                                                                                                                                              '\n'
                                                                                                                                                                                              '圧縮率が '
                                                                                                                                                                                              '1.0 '
                                                                                                                                                                                              'の場合はすべてのフレームがエクスポートされ、圧縮率が '
                                                                                                                                                                                              '0.5 '
                                                                                                                                                                                              'の場合はフレームの半分がエクスポートされます',
        ('*', 'The method by which bones from the PSA file are mapped to the bones of the armature'): 'PSA '
                                                                                                      'ファイルのボーンをアーマチュアのボーンにマッピングする方法',
        ('*', 'The minimum number of keyframes to be exported'): 'エクスポートするキーフレームの最小数',
        ('*', 'The selected object must be an armature'): '選択したオブジェクトはアーマチュアでなければなりません',
        ('*', 'The sequence frame rate matches the original frame rate'): 'シーケンスのフレームレートは元のフレームレートと一致します',
        ('*', 'The sequence is resampled to a custom frame rate'): 'シーケンスはカスタムフレームレートにリサンプリングされます',
        ('*', 'The sequence is resampled to the frame rate of the scene'): 'シーケンスはシーンのフレームレートに合わせてリサンプリングされます',
        ('*', 'The source vertex color space'): 'ソース頂点カラースペース',
        ('*', 'Translucent'): '半透明',
        ('*', 'Triangle Bit Flags'): 'トライアングルビットフラグ',
        ('*', 'Triangle Type'): 'トライアングルタイプ',
        ('*', 'Unlit'): '明かりなし',
        ('*', 'Unreal PSA (.psa)'): 'アンリアルスパ (.psa)',
        ('*', 'Unreal PSK (.psk)'): 'アンリアルPSK (.psk)',
        ('*', 'Unreal PSK (.psk/.pskx)'): 'アンリアルPSK (.psk/.pskx)',
        ('*', 'Unrecognized wedge format'): '認識されないウェッジフォーマット',
        ('*', 'Use Config File'): '設定ファイルを使用',
        ('*', 'Use the .config file that is sometimes generated when the PSA file is exported from UEViewer. This file contains options that can be used to filter out certain bones tracks from the imported actions'): 'PSA '
                                                                                                                                                                                                                         'ファイルを '
                                                                                                                                                                                                                         'UEViewer '
                                                                                                                                                                                                                         'からエクスポートしたときに生成されることがある.config '
                                                                                                                                                                                                                         'ファイルを使用してください。このファイルには、インポートしたアクションから特定のボーントラックを除外するためのオプションが含まれています',
        ('*', 'Use the animation data from a different object instead of the selected object'): '選択したオブジェクトの代わりに別のオブジェクトのアニメーションデータを使用する',
        ('*', 'Vertex Color Space'): '頂点カラースペース',
        ('*', 'Vertex Colors'): '頂点カラー',
        ('*', 'Vertex Normals'): '頂点法線',
        ('*', 'When enabled, the root bone will be transformed as it appears in the scene.\n\nYou might want to disable this if you are exporting an animation for an armature that is attached to another object, such as a weapon or a shield'): '有効にすると、ルートボーンはシーンに表示されているとおりにトランスフォームされます。\n'
                                                                                                                                                                                                                                                   '\n'
                                                                                                                                                                                                                                                   '武器や盾など、別のオブジェクトにアタッチされているアーマチュアのアニメーションをエクスポートする場合は、これを無効にすると良いかもしれません',
        ('*', 'Write'): '書き込み',
        ('*', 'sRGBA'): 'sRGBA'}}