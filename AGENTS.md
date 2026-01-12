# AGENTS.md

This is an Blender addon for importing and exporting Unreal Engine PSK (skeletal mesh) and PSX (animation) files.

# PSK/PSA File Format Notes
* PSK and PSA bone hierarchies must have a single root bone. The root bone's `parent_index` is always `0`.
* All indices in PSK/PSX files are zero-based.
* All string fields in PSK/PSX files use Windows-1252 encoding and are null-terminated if they do not use the full length of the field.
* Bone transforms are in parent bone space, except for root bones, which are in world space.

# Naming Conventions
* The `PSX` prefix is used when refer to concepts that are shared between PSK and PSX files.
