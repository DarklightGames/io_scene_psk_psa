[![Blender](https://img.shields.io/badge/Blender->=2.9-blue?logo=blender&logoColor=white)](https://www.blender.org/download/ "Download Blender")
[![GitHub release](https://img.shields.io/github/release/DarklightGames/io_scene_psk_psa?include_prereleases=&sort=semver&color=blue)](https://github.com/DarklightGames/io_scene_psk_psa/releases/)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/L4L3853VR)

This Blender add-on allows you to import and export meshes and animations to and from the [PSK and PSA file formats](https://wiki.beyondunreal.com/PSK_%26_PSA_file_formats) used in many versions of the Unreal Engine.

| Blender Version | Addon Version | [LTS](https://en.wikipedia.org/wiki/Long-term_support) |
|-----------------|---------------|-----|
| 4.0             | [6.0.0](https://github.com/DarklightGames/io_scene_psk_psa/releases/latest) | ✔
| 3.4 - 3.6       | [5.0.6](https://github.com/DarklightGames/io_scene_psk_psa/releases/tag/5.0.6) | ✔
| 2.9 - 3.3       | [4.3.0](https://github.com/DarklightGames/io_scene_psk_psa/releases/tag/4.3.0) |

# Features
* Full PSK/PSA import and export capabilities.
* Non-standard file section data is supported for import only (vertex normals, extra UV channels, vertex colors, shape keys).
* Fine-grained PSA sequence importing for efficient workflow when working with large PSA files.
* PSA sequence metadata (e.g., frame rate, sequence name) is preserved on import, allowing this data to be reused on export.
* Specific bone collections can be excluded from PSK/PSA export (useful for excluding non-contributing bones such as IK controllers).
* PSA sequences can be exported directly from actions or delineated using a scene's [timeline markers](https://docs.blender.org/manual/en/latest/animation/markers.html) or NLA track strips, allowing direct use of the [NLA](https://docs.blender.org/manual/en/latest/editors/nla/index.html) when creating sequences.
* Manual re-ordering of material slots when exporting multiple mesh objects.

## Compatibility

| Blender Version                                              | Addon Version                                                                  | LTS Support       |
|--------------------------------------------------------------|--------------------------------------------------------------------------------|-------------------|
| 4.0+                                                         | [latest](https://github.com/DarklightGames/io_scene_psk_psa/releases/latest)   | TBD               |
| [3.4 - 3.6](https://www.blender.org/download/lts/3-6/)       | [5.0.5](https://github.com/DarklightGames/io_scene_psk_psa/releases/tag/5.0.5) | ✅️ June 2025      |
| [2.93 - 3.3](https://www.blender.org/download/releases/3-3/) | [4.3.0](https://github.com/DarklightGames/io_scene_psk_psa/releases/tag/4.3.0) | ✅️ September 2024 | 

Bug fixes will be issued for legacy addon versions that are under [Blender's LTS maintenance period](https://www.blender.org/download/lts/). Once the LTS period has ended, legacy addon-on versions will no longer be supported by the maintainers of this repository, although we will accept pull requests for bug fixes. 

# Installation
1. Download the zip file for the latest version from the [releases](https://github.com/DarklightGames/io_export_psk_psa/releases) page.
2. Open Blender 4.0.0 or later.
3. Navigate to the Blender Preferences (`Edit` > `Preferences`).
4. Select the `Add-ons` tab.
5. Click the `Install...` button.
6. Select the .zip file that you downloaded earlier and click `Install Add-on`.
7. Enable the newly added `Import-Export: PSK/PSA Importer/Exporter` addon.

# Usage
## Exporting a PSK
1. Select the mesh objects you wish to export.
2. Navigate to `File` > `Export` > `Unreal PSK (.psk)`.
3. Enter the file name and click `Export`.

## Importing a PSK/PSKX
1. Navigate to `File` > `Import` > `Unreal PSK (.psk/.pskx)`.
2. Select the PSK file you want to import and click `Import`.

## Exporting a PSA
1. Select the armature objects you wish to export.
2. Navigate to `File` > `Export` > `Unreal PSA (.psa)`.
3. Enter the file name and click `Export`.

## Importing a PSA
1. Select an armature that you want import animations for.
2. Navigate to `File` > `Import` > `Unreal PSA (.psa)`.
3. Select the PSA file you want to import.
4. Select the sequences that you want to import and click `Import`.

> Note that in order to see the imported actions applied to your armature, you must use the [Dope Sheet](https://docs.blender.org/manual/en/latest/editors/dope_sheet/introduction.html) or [Nonlinear Animation](https://docs.blender.org/manual/en/latest/editors/nla/introduction.html) editors.

# FAQ
## Why are the mesh normals not accurate when importing a PSK extracted from [UE Viewer](https://www.gildor.org/en/projects/umodel)?
If preserving the mesh normals of models is important for your workflow, it is *not recommended* to export PSK files from UE Viewer. This is because UE Viewer makes no attempt to reconstruct the original [smoothing groups](https://en.wikipedia.org/wiki/Smoothing_group). As a result, the normals of imported PSK files will be incorrect when imported into Blender and will need to be manually fixed.

As a workaround, it is recommended to export [glTF](https://en.wikipedia.org/wiki/GlTF) meshes out of UE Viewer instead, since the glTF format has support for explicit normals and UE Viewer can correctly preserve the mesh normals on export. Note, however, that the imported glTF armature may have it's bones oriented incorrectly when imported into Blender. To mitigate this, you can combine the armature of PSK and the mesh of the glTF for best results.
