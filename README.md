[![Blender](https://img.shields.io/badge/Blender->=2.9-blue?logo=blender&logoColor=white)](https://www.blender.org/download/ "Download Blender")
[![GitHub release](https://img.shields.io/github/release/DarklightGames/io_scene_psk_psa?include_prereleases=&sort=semver&color=blue)](https://github.com/DarklightGames/io_scene_psk_psa/releases/)
[![Build Extension](https://github.com/DarklightGames/io_scene_psk_psa/actions/workflows/main.yml/badge.svg)](https://github.com/DarklightGames/io_scene_psk_psa/actions/workflows/main.yml)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/L4L3853VR)

This Blender addon allows you to import and export meshes and animations to and from the [PSK and PSA file formats](https://wiki.beyondunreal.com/PSK_%26_PSA_file_formats) used in many versions of the Unreal Engine.

This software is licensed under the [GPLv3](https://www.gnu.org/licenses/gpl-3.0.html) license.

# Features
* Full PSK/PSA import and export capabilities.
* Non-standard file section data is supported for import only (vertex normals, extra UV channels, vertex colors, shape keys).
* Fine-grained PSA sequence importing for efficient workflow when working with large PSA files.
* PSA sequence metadata (e.g., frame rate) is preserved on import, allowing this data to be reused on export.
* Specific bone collections can be excluded from PSK/PSA export (useful for excluding non-contributing bones such as IK controllers).
* PSA sequences can be exported directly from actions or delineated using a scene's [timeline markers](https://docs.blender.org/manual/en/latest/animation/markers.html), pose markers, or NLA track strips, allowing direct use of the [NLA](https://docs.blender.org/manual/en/latest/editors/nla/index.html) when creating sequences.
* Manual re-ordering of material slots when exporting multiple mesh objects.

# Installation
For Blender 4.2 and higher, it is recommended to download the latest version from the [Blender Extensions](https://extensions.blender.org/add-ons/io-scene-psk-psa/) platform.

For Blender 4.1 and lower, you can install the addon manually by following these steps:

1. Download the .zip file of the latest compatible version for your Blender version (see [Legacy Compatibility](#legacy-compatibility)).
2. Open Blender.
3. Navigate to the Blender Preferences (`Edit` > `Preferences`).
4. Select the `Add-ons` tab.
5. Click the `Install...` button.
6. Select the .zip file that you downloaded earlier and click `Install Add-on`.
7. Enable the newly added `Import-Export: PSK/PSA Importer/Exporter` addon.

# Legacy Compatibility

Below is a table of the latest addon versions that are compatible with older versions of Blender. These versions are no longer maintained and may contain bugs that have been fixed in newer versions. It is recommended to use the latest version of the addon for the best experience.

Critical bug fixes may be issued for legacy addon versions that are under [Blender's LTS maintenance period](https://www.blender.org/download/lts/). Once the LTS period has ended, legacy addon versions will no longer be supported by the maintainers of this repository, although the releases will still be available for download.

| Blender Version| Addon Version                                                                  | Long Term Support |
|-|--------------------------------------------------------------------------------|-----------------|
| [4.1](https://www.blender.org/download/releases/4-1/)        | [7.0.0](https://github.com/DarklightGames/io_scene_psk_psa/releases/tag/7.0.0) | No              |
| [4.0](https://www.blender.org/download/releases/4-0/)        | [6.2.1](https://github.com/DarklightGames/io_scene_psk_psa/releases/tag/6.2.1) | No              |
| [3.4 - 3.6](https://www.blender.org/download/lts/3-6/)       | [5.0.6](https://github.com/DarklightGames/io_scene_psk_psa/releases/tag/5.0.6) | June 2025       |
| [2.93 - 3.3](https://www.blender.org/download/releases/3-3/) | [4.3.0](https://github.com/DarklightGames/io_scene_psk_psa/releases/tag/4.3.0) | September 2024  |

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

## Why can't I see the animations imported from my PSA?
Simply importing an animation into the scene will not automatically apply the action to the armature. This is in part because a PSA can have multiple sequences imported from it, and also that it's generally bad form for importers to modify the scene when they don't need to.

The PSA importer creates [Actions](https://docs.blender.org/manual/en/latest/animation/actions.html) for each of the selected sequences in the PSA. These actions can be applied to your armature via the [Action Editor](https://docs.blender.org/manual/en/latest/editors/dope_sheet/action.html) or [NLA Editor](https://docs.blender.org/manual/en/latest/editors/nla/index.html).

## Why are imported PSKs too big/too small?
The PSK format, unlike other more modern formats, has no explicit or implicit unit system. Each game has its own convention as to what the base distance unit will represent. As such, this addon makes no assumptions as to the unit scale of the imported PSKs. If you think that your models are being imported into Blender either too big or too small, there are a couple ways to remedy this.

The method I prefer is to simply change the Blender [scene properties](https://docs.blender.org/manual/en/4.4/scene_layout/scene/properties.html#units) to match the unit system and scale for the game you're using. This is non-destructive and ensures that the actual raw unit scaling of any PSK or PSA exports from Blender will match the source file from which it was derived.

The second option is to simply change the `Scale` value on the PSK import dialog. This will scale the armature by the factor provided. Note that this is more destructive, but may be preferable if you don't intend on exporting PSKs or PSAs to a game engine.

## Why are the mesh normals not accurate when importing a PSK extracted from [UE Viewer](https://www.gildor.org/en/projects/umodel)?
If preserving the mesh normals of models is important for your workflow, it is *not recommended* to export PSK files from UE Viewer. This is because UE Viewer makes no attempt to reconstruct the original [smoothing groups](https://en.wikipedia.org/wiki/Smoothing_group). As a result, the normals of imported PSK files will be incorrect when imported into Blender and will need to be manually fixed.

There is a [pull request](https://github.com/gildor2/UEViewer/pull/277) to add support for exporting explicit normals from UE Viewer in the future.
