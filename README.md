This Blender add-on allows you to export meshes and animations to the [PSK and PSA file formats](https://wiki.beyondunreal.com/PSK_%26_PSA_file_formats).

# Installation
1. Download the zip file for the latest version from the [releases](https://github.com/DarklightGames/io_export_psk_psa/releases) page.
2. Open Blender 2.80 or later.
3. Navigate to the Blender Preferences (Edit > Preferences).
4. Select the "Add-ons" tab.
5. Click the "Install..." button.
6. Select the .zip file that you downloaded earlier and click "Install Add-on".
7. Enable the newly added "Import-Export: PSK/PSA Exporter" addon.

# Usage
## Exporting a PSK
1. Select the mesh objects you wish to export.
3. Navigate to File > Export > Unreal PSK (.psk)
4. Enter the file name and click "Export".

## Importing a PSK
1. Navigate to File > Import > Unreal PSK (.psk)
2. Select the PSK file you want to import and click "Import"

## Exporting a PSA
1. Select the armature objects you wish to export.
2. Navigate to File > Export > Unreal PSA (.psa)
3. Enter the file name and click "Export".

## Importing a PSA
1. Select the armature object that you wish you import actions to.
2. Navigate to the Object Data Properties tab of the Properties editor.
3. Navigate to the PSA Import panel.
4. Click "Select PSA File".
5. Select the PSA file that you want to import animations from and click "Select".
6. In the Actions box, select which animations you want to import.
7. Click "Import".

# FAQ
## Why are the mesh normals not accurate when importing a PSK extracted from [UE Viewer](https://www.gildor.org/en/projects/umodel)?
If preserving the mesh normals of models is important for your workflow, it is *not recommended* to export PSK files from UE Viewer. This is because UE Viewer makes no attempt to reconstruct the original [smoothing groups](https://en.wikipedia.org/wiki/Smoothing_group). As a result, the normals of imported PSK files will be incorrect when imported into Blender and will need to be manually fixed.

As a workaround, it is recommended to export [glTF](https://en.wikipedia.org/wiki/GlTF) meshes out of UE Viewer instead, since the glTF format has support for explicit normals and UE Viewer can correctly preserve the mesh normals on export. Note, however, that the imported glTF armature may have it's bones oriented incorrectly when imported into blender. To mitigate this, you can combine the armature of PSK and the mesh of the glTF for best results.
