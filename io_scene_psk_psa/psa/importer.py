import typing
from typing import Iterable, List, Optional, cast as typing_cast

import bpy
import numpy as np
from bpy.types import Armature, Context, FCurve, Object
from mathutils import Vector, Quaternion

from .config import PsaConfig, REMOVE_TRACK_LOCATION, REMOVE_TRACK_ROTATION
from .reader import PsaReader
from ..shared.data import PsxBone


class PsaImportOptions(object):
    def __init__(self,
                 action_name_prefix: str = '',
                 bone_mapping_mode: str = 'CASE_INSENSITIVE',
                 fps_custom: float = 30.0,
                 fps_source: str = 'SEQUENCE',
                 psa_config: PsaConfig = PsaConfig(),
                 sequence_names: List[str] = None,
                 should_convert_to_samples: bool = False,
                 should_overwrite: bool = False,
                 should_stash: bool = False,
                 should_use_config_file: bool = True,
                 should_use_fake_user: bool = False,
                 should_write_keyframes: bool = True,
                 should_write_metadata: bool = True,
                 translation_scale: float = 1.0
                 ):
        self.action_name_prefix = action_name_prefix
        self.bone_mapping_mode = bone_mapping_mode
        self.fps_custom = fps_custom
        self.fps_source = fps_source
        self.psa_config = psa_config
        self.sequence_names = sequence_names if sequence_names is not None else []
        self.should_convert_to_samples = should_convert_to_samples
        self.should_overwrite = should_overwrite
        self.should_stash = should_stash
        self.should_use_config_file = should_use_config_file
        self.should_use_fake_user = should_use_fake_user
        self.should_write_keyframes = should_write_keyframes
        self.should_write_metadata = should_write_metadata
        self.translation_scale = translation_scale


class ImportBone(object):
    def __init__(self, psa_bone: PsxBone):
        self.psa_bone: PsxBone = psa_bone
        self.parent: Optional[ImportBone] = None
        self.armature_bone = None
        self.pose_bone = None
        self.original_location: Vector = Vector()
        self.original_rotation: Quaternion = Quaternion()
        self.post_rotation: Quaternion = Quaternion()
        self.fcurves: List[FCurve] = []


def _calculate_fcurve_data(import_bone: ImportBone, key_data: Iterable[float]):
    # Convert world-space transforms to local-space transforms.
    key_rotation = Quaternion(key_data[0:4])
    key_location = Vector(key_data[4:])
    q = import_bone.post_rotation.copy()
    q.rotate(import_bone.original_rotation)
    rotation = q
    q = import_bone.post_rotation.copy()
    if import_bone.parent is None:
        q.rotate(key_rotation.conjugated())
    else:
        q.rotate(key_rotation)
    rotation.rotate(q.conjugated())
    location = key_location - import_bone.original_location
    location.rotate(import_bone.post_rotation.conjugated())
    return rotation.w, rotation.x, rotation.y, rotation.z, location.x, location.y, location.z


class PsaImportResult:
    def __init__(self):
        self.warnings: List[str] = []


def _get_armature_bone_index_for_psa_bone(psa_bone_name: str, armature_bone_names: List[str], bone_mapping_mode: str = 'EXACT') -> Optional[int]:
    """
    @param psa_bone_name: The name of the PSA bone.
    @param armature_bone_names: The names of the bones in the armature.
    @param bone_mapping_mode: One of `['EXACT', 'CASE_INSENSITIVE']`.
    @return: The index of the armature bone that corresponds to the given PSA bone, or None if no such bone exists.
    """
    for armature_bone_index, armature_bone_name in enumerate(armature_bone_names):
        if bone_mapping_mode == 'CASE_INSENSITIVE':
            if armature_bone_name.lower() == psa_bone_name.lower():
                return armature_bone_index
        else:
            if armature_bone_name == psa_bone_name:
                return armature_bone_index
    return None


def _resample_sequence_data_matrix(sequence_data_matrix: np.ndarray, frame_step: float = 1.0) -> np.ndarray:
    """
    Resamples the sequence data matrix to the target frame count.

    @param sequence_data_matrix: FxBx7 matrix where F is the number of frames, B is the number of bones, and X is the
    number of data elements per bone.
    @param frame_step: The step between frames in the resampled sequence.
    @return: The resampled sequence data matrix, or sequence_data_matrix if no resampling is necessary.
    """

    def _get_sample_frame_times(source_frame_count: int, frame_step: float) -> Iterable[float]:
        # TODO: for correctness, we should also emit the target frame time as well (because the last frame can be a
        #  fractional frame).
        assert frame_step > 0.0, 'Frame step must be greater than 0'
        time = 0.0
        while time < source_frame_count - 1:
            yield time
            time += frame_step
        yield source_frame_count - 1

    if frame_step == 1.0:
        # No resampling is necessary.
        return sequence_data_matrix

    source_frame_count, bone_count = sequence_data_matrix.shape[:2]
    sample_frame_times = list(_get_sample_frame_times(source_frame_count, frame_step))
    target_frame_count = len(sample_frame_times)
    resampled_sequence_data_matrix = np.zeros((target_frame_count, bone_count, 7), dtype=float)

    for sample_frame_index, sample_frame_time in enumerate(sample_frame_times):
        frame_index = int(sample_frame_time)
        if sample_frame_time % 1.0 == 0.0:
            # Sample time has no fractional part, so just copy the frame.
            resampled_sequence_data_matrix[sample_frame_index, :, :] = sequence_data_matrix[frame_index, :, :]
        else:
            # Sample time has a fractional part, so interpolate between two frames.
            next_frame_index = frame_index + 1
            for bone_index in range(bone_count):
                source_frame_1_data = sequence_data_matrix[frame_index, bone_index, :]
                source_frame_2_data = sequence_data_matrix[next_frame_index, bone_index, :]
                factor = sample_frame_time - frame_index
                q = Quaternion((source_frame_1_data[:4])).slerp(Quaternion((source_frame_2_data[:4])), factor)
                q.normalize()
                l = Vector(source_frame_1_data[4:]).lerp(Vector(source_frame_2_data[4:]), factor)
                resampled_sequence_data_matrix[sample_frame_index, bone_index, :] = q.w, q.x, q.y, q.z, l.x, l.y, l.z

    return resampled_sequence_data_matrix


def import_psa(context: Context, psa_reader: PsaReader, armature_object: Object, options: PsaImportOptions) -> PsaImportResult:
    result = PsaImportResult()
    sequences = [psa_reader.sequences[x] for x in options.sequence_names]
    armature_data = typing_cast(Armature, armature_object.data)

    # Create an index mapping from bones in the PSA to bones in the target armature.
    psa_to_armature_bone_indices = {}
    armature_to_psa_bone_indices = {}
    armature_bone_names = [x.name for x in armature_data.bones]
    psa_bone_names = []
    duplicate_mappings = []

    for psa_bone_index, psa_bone in enumerate(psa_reader.bones):
        psa_bone_name: str = psa_bone.name.decode('windows-1252')
        armature_bone_index = _get_armature_bone_index_for_psa_bone(psa_bone_name, armature_bone_names, options.bone_mapping_mode)
        if armature_bone_index is not None:
            # Ensure that no other PSA bone has been mapped to this armature bone yet.
            if armature_bone_index not in armature_to_psa_bone_indices:
                psa_to_armature_bone_indices[psa_bone_index] = armature_bone_index
                armature_to_psa_bone_indices[armature_bone_index] = psa_bone_index
            else:
                # This armature bone has already been mapped to a PSA bone.
                duplicate_mappings.append((psa_bone_index, armature_bone_index, armature_to_psa_bone_indices[armature_bone_index]))
            psa_bone_names.append(armature_bone_names[armature_bone_index])
        else:
            psa_bone_names.append(psa_bone_name)

    # Warn about duplicate bone mappings.
    if len(duplicate_mappings) > 0:
        for (psa_bone_index, armature_bone_index, mapped_psa_bone_index) in duplicate_mappings:
            psa_bone_name = psa_bone_names[psa_bone_index]
            armature_bone_name = armature_bone_names[armature_bone_index]
            mapped_psa_bone_name = psa_bone_names[mapped_psa_bone_index]
            result.warnings.append(f'PSA bone {psa_bone_index} ({psa_bone_name}) could not be mapped to armature bone {armature_bone_index} ({armature_bone_name}) because the armature bone is already mapped to PSA bone {mapped_psa_bone_index} ({mapped_psa_bone_name})')

    # Report if there are missing bones in the target armature.
    missing_bone_names = set(psa_bone_names).difference(set(armature_bone_names))
    if len(missing_bone_names) > 0:
        result.warnings.append(
            f'The armature \'{armature_object.name}\' is missing {len(missing_bone_names)} bones that exist in '
            'the PSA:\n' +
            str(list(sorted(missing_bone_names)))
        )
    del armature_bone_names

    # Create intermediate bone data for import operations.
    import_bones = []
    psa_bone_names_to_import_bones = dict()

    for (psa_bone_index, psa_bone), psa_bone_name in zip(enumerate(psa_reader.bones), psa_bone_names):
        if psa_bone_index not in psa_to_armature_bone_indices:
            # PSA bone does not map to armature bone, skip it and leave an empty bone in its place.
            import_bones.append(None)
            continue
        import_bone = ImportBone(psa_bone)
        import_bone.armature_bone = armature_data.bones[psa_bone_name]
        import_bone.pose_bone = armature_object.pose.bones[psa_bone_name]
        psa_bone_names_to_import_bones[psa_bone_name] = import_bone
        import_bones.append(import_bone)

    bones_with_missing_parents = []

    for import_bone in filter(lambda x: x is not None, import_bones):
        armature_bone = import_bone.armature_bone
        has_parent = armature_bone.parent is not None
        if has_parent:
            if armature_bone.parent.name in psa_bone_names:
                import_bone.parent = psa_bone_names_to_import_bones[armature_bone.parent.name]
            else:
                # Add a warning if the parent bone is not in the PSA.
                bones_with_missing_parents.append(armature_bone)
        # Calculate the original location & rotation of each bone (in world-space maybe?)
        if has_parent:
            import_bone.original_location = armature_bone.matrix_local.translation - armature_bone.parent.matrix_local.translation
            import_bone.original_location.rotate(armature_bone.parent.matrix_local.to_quaternion().conjugated())
            import_bone.original_rotation = armature_bone.matrix_local.to_quaternion()
            import_bone.original_rotation.rotate(armature_bone.parent.matrix_local.to_quaternion().conjugated())
            import_bone.original_rotation.conjugate()
        else:
            import_bone.original_location = armature_bone.matrix_local.translation.copy()
            import_bone.original_rotation = armature_bone.matrix_local.to_quaternion().conjugated()

        import_bone.post_rotation = import_bone.original_rotation.conjugated()

    # Warn about bones with missing parents.
    if len(bones_with_missing_parents) > 0:
        count = len(bones_with_missing_parents)
        message = f'{count} bone(s) have parents that are not present in the PSA:\n' + str([x.name for x in bones_with_missing_parents])
        result.warnings.append(message)

    context.window_manager.progress_begin(0, len(sequences))

    # Create and populate the data for new sequences.
    actions = []
    for sequence_index, sequence in enumerate(sequences):
        # Add the action.
        sequence_name = sequence.name.decode('windows-1252')
        action_name = options.action_name_prefix + sequence_name

        # Get the bone track flags for this sequence, or an empty dictionary if none exist.
        sequence_bone_track_flags = dict()
        if sequence_name in options.psa_config.sequence_bone_flags.keys():
            sequence_bone_track_flags = options.psa_config.sequence_bone_flags[sequence_name]

        if options.should_overwrite and action_name in bpy.data.actions:
            action = bpy.data.actions[action_name]
        else:
            action = bpy.data.actions.new(name=action_name)

        # Calculate the target FPS.
        match options.fps_source:
            case 'CUSTOM':
                target_fps = options.fps_custom
            case 'SCENE':
                target_fps = context.scene.render.fps
            case 'SEQUENCE':
                target_fps = sequence.fps
            case _:
                assert False, f'Invalid FPS source: {options.fps_source}'

        if options.should_write_keyframes:
            # Remove existing f-curves.
            action.fcurves.clear()

            # Create f-curves for the rotation and location of each bone.
            for psa_bone_index, armature_bone_index in psa_to_armature_bone_indices.items():
                bone_track_flags = sequence_bone_track_flags.get(psa_bone_index, 0)
                import_bone = import_bones[psa_bone_index]
                pose_bone = import_bone.pose_bone
                rotation_data_path = pose_bone.path_from_id('rotation_quaternion')
                location_data_path = pose_bone.path_from_id('location')
                add_rotation_fcurves = (bone_track_flags & REMOVE_TRACK_ROTATION) == 0
                add_location_fcurves = (bone_track_flags & REMOVE_TRACK_LOCATION) == 0
                import_bone.fcurves = [
                    action.fcurves.new(rotation_data_path, index=0, action_group=pose_bone.name) if add_rotation_fcurves else None,  # Qw
                    action.fcurves.new(rotation_data_path, index=1, action_group=pose_bone.name) if add_rotation_fcurves else None,  # Qx
                    action.fcurves.new(rotation_data_path, index=2, action_group=pose_bone.name) if add_rotation_fcurves else None,  # Qy
                    action.fcurves.new(rotation_data_path, index=3, action_group=pose_bone.name) if add_rotation_fcurves else None,  # Qz
                    action.fcurves.new(location_data_path, index=0, action_group=pose_bone.name) if add_location_fcurves else None,  # Lx
                    action.fcurves.new(location_data_path, index=1, action_group=pose_bone.name) if add_location_fcurves else None,  # Ly
                    action.fcurves.new(location_data_path, index=2, action_group=pose_bone.name) if add_location_fcurves else None,  # Lz
                ]

            # Read the sequence data matrix from the PSA.
            sequence_data_matrix = psa_reader.read_sequence_data_matrix(sequence_name)

            if options.translation_scale != 1.0:
                # Scale the translation data.
                sequence_data_matrix[:, :, 4:] *= options.translation_scale

            # Convert the sequence's data from world-space to local-space.
            for bone_index, import_bone in enumerate(import_bones):
                if import_bone is None:
                    continue
                for frame_index in range(sequence.frame_count):
                    # This bone has writeable keyframes for this frame.
                    key_data = sequence_data_matrix[frame_index, bone_index]
                    # Calculate the local-space key data for the bone.
                    sequence_data_matrix[frame_index, bone_index] = _calculate_fcurve_data(import_bone, key_data)

            # Resample the sequence data to the target FPS.
            # If the target frame count is the same as the source frame count, this will be a no-op.
            resampled_sequence_data_matrix = _resample_sequence_data_matrix(sequence_data_matrix,
                                                                            frame_step=sequence.fps / target_fps)

            # Write the keyframes out.
            # Note that the f-curve data consists of alternating time and value data.
            target_frame_count = resampled_sequence_data_matrix.shape[0]
            fcurve_data = np.zeros(2 * target_frame_count, dtype=float)
            fcurve_data[0::2] = range(0, target_frame_count)

            for bone_index, import_bone in enumerate(import_bones):
                if import_bone is None:
                    continue
                for fcurve_index, fcurve in enumerate(import_bone.fcurves):
                    if fcurve is None:
                        continue
                    fcurve_data[1::2] = resampled_sequence_data_matrix[:, bone_index, fcurve_index]
                    fcurve.keyframe_points.add(target_frame_count)
                    fcurve.keyframe_points.foreach_set('co', fcurve_data)
                    for fcurve_keyframe in fcurve.keyframe_points:
                        fcurve_keyframe.interpolation = 'LINEAR'

            if options.should_convert_to_samples:
                # Bake the curve to samples.
                for fcurve in action.fcurves:
                    fcurve.convert_to_samples(start=0, end=sequence.frame_count)

        # Write meta-data.
        if options.should_write_metadata:
            action.psa_export.fps = target_fps

        action.use_fake_user = options.should_use_fake_user

        actions.append(action)

        context.window_manager.progress_update(sequence_index)

    # If the user specifies, store the new animations as strips on a non-contributing NLA track.
    if options.should_stash:
        if armature_object.animation_data is None:
            armature_object.animation_data_create()
        for action in actions:
            nla_track = armature_object.animation_data.nla_tracks.new()
            nla_track.name = action.name
            nla_track.mute = True
            nla_track.strips.new(name=action.name, start=0, action=action)

    context.window_manager.progress_end()

    return result
