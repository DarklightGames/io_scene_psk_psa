from bpy.types import Action, AnimData, Context, Object, PoseBone

from .data import Psa
from typing import Dict, List, Optional, Tuple
from mathutils import Matrix, Quaternion, Vector

from ..shared.helpers import create_psx_bones, get_coordinate_system_transform


class PsaBuildSequence:
    class NlaState:
        def __init__(self):
            self.action: Optional[Action] = None
            self.frame_start: int = 0
            self.frame_end: int = 0

    def __init__(self, armature_object: Object, anim_data: AnimData):
        self.armature_object = armature_object
        self.anim_data = anim_data
        self.name: str = ''
        self.nla_state: PsaBuildSequence.NlaState = PsaBuildSequence.NlaState()
        self.compression_ratio: float = 1.0
        self.key_quota: int = 0
        self.fps: float = 30.0


class PsaBuildOptions:
    def __init__(self):
        self.armature_objects: List[Object] = []
        self.animation_data: Optional[AnimData] = None
        self.sequences: List[PsaBuildSequence] = []
        self.bone_filter_mode: str = 'ALL'
        self.bone_collection_indices: List[Tuple[str, int]] = []
        self.sequence_name_prefix: str = ''
        self.sequence_name_suffix: str = ''
        self.scale = 1.0
        self.sampling_mode: str = 'INTERPOLATED'  # One of ('INTERPOLATED', 'SUBFRAME')
        self.export_space = 'WORLD'
        self.forward_axis = 'X'
        self.up_axis = 'Z'
        self.root_bone_name = 'ROOT'


def _get_pose_bone_location_and_rotation(
        pose_bone: Optional[PoseBone],
        armature_object: Optional[Object],
        export_space: str,
        scale: Vector,
        coordinate_system_transform: Matrix,
        has_false_root_bone: bool,
) -> Tuple[Vector, Quaternion]:
    is_false_root_bone = pose_bone is None and armature_object is None

    if is_false_root_bone:
        pose_bone_matrix = coordinate_system_transform
    elif pose_bone.parent is not None:
        pose_bone_matrix = pose_bone.matrix
        pose_bone_parent_matrix = pose_bone.parent.matrix
        pose_bone_matrix = pose_bone_parent_matrix.inverted() @ pose_bone_matrix
    else:
        # Root bone
        if has_false_root_bone:
            pose_bone_matrix = armature_object.matrix_world @ pose_bone.matrix
        else:
            # Get the bone's pose matrix and transform it into the export space.
            # In the case of an 'ARMATURE' export space, this will be the inverse of armature object's world matrix.
            # Otherwise, it will be the identity matrix.
            match export_space:
                case 'ARMATURE':
                    pose_bone_matrix = pose_bone.matrix
                case 'WORLD':
                    pose_bone_matrix = armature_object.matrix_world @ pose_bone.matrix
                case 'ROOT':
                    pose_bone_matrix = Matrix.Identity(4)
                case _:
                    assert False, f'Invalid export space: {export_space}'

            # The root bone is the only bone that should be transformed by the coordinate system transform, since all
            # other bones are relative to their parent bones.
            pose_bone_matrix = coordinate_system_transform @ pose_bone_matrix

    location = pose_bone_matrix.to_translation()
    rotation = pose_bone_matrix.to_quaternion().normalized()

    # Don't apply scale to the root bone of armatures if we have a false root.
    if not has_false_root_bone or (pose_bone is None or pose_bone.parent is not None):
        location *= scale

    if has_false_root_bone:
        is_child_bone = not is_false_root_bone
    else:
        is_child_bone = pose_bone.parent is not None

    if is_child_bone:
        rotation.conjugate()

    return location, rotation


def build_psa(context: Context, options: PsaBuildOptions) -> Psa:
    psa = Psa()

    psx_bone_create_result = create_psx_bones(
        armature_objects=options.armature_objects,
        export_space=options.export_space,
        root_bone_name=options.root_bone_name,
        forward_axis=options.forward_axis,
        up_axis=options.up_axis,
        scale=options.scale,
        bone_filter_mode=options.bone_filter_mode,
        bone_collection_indices=options.bone_collection_indices,
    )

    # Build list of PSA bones.
    # Note that the PSA bones are just here to validate the hierarchy.
    # The bind pose information is not used by the engine.
    psa.bones = [psx_bone for psx_bone, _ in psx_bone_create_result.bones]

    # No bones are going to be exported.
    if len(psa.bones) == 0:
        raise RuntimeError('No bones available for export')

    # Add prefixes and suffices to the names of the export sequences and strip whitespace.
    for export_sequence in options.sequences:
        export_sequence.name = f'{options.sequence_name_prefix}{export_sequence.name}{options.sequence_name_suffix}'
        export_sequence.name = export_sequence.name.strip()

    # Save each armature object's current action and frame so that we can restore the state once we are done.
    saved_armature_object_actions = {o: o.animation_data.action for o in options.armature_objects}
    saved_frame_current = context.scene.frame_current

    # Now build the PSA sequences.
    # We actually alter the timeline frame and simply record the resultant pose bone matrices.
    frame_start_index = 0

    context.window_manager.progress_begin(0, len(options.sequences))

    coordinate_system_transform = get_coordinate_system_transform(options.forward_axis, options.up_axis)

    for export_sequence_index, export_sequence in enumerate(options.sequences):
        frame_start = export_sequence.nla_state.frame_start
        frame_end = export_sequence.nla_state.frame_end

        # Calculate the frame step based on the compression factor.
        frame_extents = abs(frame_end - frame_start)
        frame_count_raw = frame_extents + 1
        frame_count = max(1, max(export_sequence.key_quota, int(frame_count_raw * export_sequence.compression_ratio)))

        try:
            frame_step = frame_extents / (frame_count - 1)
        except ZeroDivisionError:
            frame_step = 0.0

        # If this is a reverse sequence, we need to reverse the frame step.
        if frame_start > frame_end:
            frame_step = -frame_step

        sequence_duration = frame_count_raw / export_sequence.fps

        psa_sequence = Psa.Sequence()
        try:
            psa_sequence.name = bytes(export_sequence.name, encoding='windows-1252')
        except UnicodeEncodeError:
            raise RuntimeError(
                f'Sequence name "{export_sequence.name}" contains characters that cannot be encoded in the Windows-1252 codepage')
        psa_sequence.frame_count = frame_count
        psa_sequence.frame_start_index = frame_start_index
        psa_sequence.fps = frame_count / sequence_duration
        psa_sequence.bone_count = len(psa.bones)
        psa_sequence.track_time = frame_count
        psa_sequence.key_reduction = 1.0

        frame = float(frame_start)

        # Link the action to the animation data and update view layer.
        for armature_object in options.armature_objects:
            armature_object.animation_data.action = export_sequence.nla_state.action

        context.view_layer.update()

        def add_key(location: Vector, rotation: Quaternion):
            key = Psa.Key()
            key.location.x = location.x
            key.location.y = location.y
            key.location.z = location.z
            key.rotation.x = rotation.x
            key.rotation.y = rotation.y
            key.rotation.z = rotation.z
            key.rotation.w = rotation.w
            key.time = 1.0 / psa_sequence.fps
            psa.keys.append(key)

        class PsaExportBone:
            def __init__(self, pose_bone: Optional[PoseBone], armature_object: Optional[Object], scale: Vector):
                self.pose_bone = pose_bone
                self.armature_object = armature_object
                self.scale = scale

        armature_scales: Dict[Object, Vector] = {}

        # Extract the scale from the world matrix of the evaluated armature object.
        for armature_object in options.armature_objects:
            evaluated_armature_object = armature_object.evaluated_get(context.evaluated_depsgraph_get())
            _, _, scale = evaluated_armature_object.matrix_world.decompose()
            scale *= options.scale
            armature_scales[armature_object] = scale

        # Create a list of export pose bones, in the same order as the bones as they appear in the armature.
        # The object contains the pose bone, the armature object, and a pre-calculated scaling value to apply to the
        # locations.
        export_bones: List[PsaExportBone] = []

        for psx_bone, armature_object in psx_bone_create_result.bones:
            if armature_object is None:
                export_bones.append(PsaExportBone(None, None, Vector((1.0, 1.0, 1.0))))
                continue

            pose_bone = armature_object.pose.bones[psx_bone.name.decode('windows-1252')]

            export_bones.append(PsaExportBone(pose_bone, armature_object, armature_scales[armature_object]))

        for export_bone in export_bones:
            print(export_bone.pose_bone, export_bone.armature_object, export_bone.scale)

        match options.sampling_mode:
            case 'INTERPOLATED':
                # Used as a store for the last frame's pose bone locations and rotations.
                last_frame: Optional[int] = None
                last_frame_bone_poses: List[Tuple[Vector, Quaternion]] = []

                next_frame: Optional[int] = None
                next_frame_bone_poses: List[Tuple[Vector, Quaternion]] = []

                for _ in range(frame_count):
                    if last_frame is None or last_frame != int(frame):
                        # Populate the bone poses for frame A.
                        last_frame = int(frame)

                        # TODO: simplify this code and make it easier to follow!
                        if next_frame == last_frame:
                            # Simply transfer the data from next_frame to the last_frame so that we don't need to
                            # resample anything.
                            last_frame_bone_poses = next_frame_bone_poses.copy()
                        else:
                            last_frame_bone_poses.clear()
                            context.scene.frame_set(frame=last_frame)
                            for export_bone in export_bones:
                                location, rotation = _get_pose_bone_location_and_rotation(
                                    export_bone.pose_bone,
                                    export_bone.armature_object,
                                    options.export_space,
                                    export_bone.scale,
                                    coordinate_system_transform=coordinate_system_transform,
                                    has_false_root_bone=psx_bone_create_result.has_false_root_bone,
                                )
                                last_frame_bone_poses.append((location, rotation))

                        next_frame = None
                        next_frame_bone_poses.clear()

                    # If this is not a subframe, just use the last frame's bone poses.
                    if frame % 1.0 == 0:
                        for i in range(len(export_bones)):
                            add_key(*last_frame_bone_poses[i])
                    else:
                        # Otherwise, this is a subframe, so we need to interpolate the pose between the next frame and the last frame.
                        if next_frame is None:
                            next_frame = last_frame + 1
                            context.scene.frame_set(frame=next_frame)
                            for export_bone in export_bones:
                                location, rotation = _get_pose_bone_location_and_rotation(
                                    pose_bone=export_bone.pose_bone,
                                    armature_object=export_bone.armature_object,
                                    export_space=options.export_space,
                                    scale=export_bone.scale,
                                    coordinate_system_transform=coordinate_system_transform,
                                    has_false_root_bone=psx_bone_create_result.has_false_root_bone,
                                )
                                next_frame_bone_poses.append((location, rotation))

                        factor = frame % 1.0

                        for i in range(len(export_bones)):
                            last_location, last_rotation = last_frame_bone_poses[i]
                            next_location, next_rotation = next_frame_bone_poses[i]

                            location = last_location.lerp(next_location, factor)
                            rotation = last_rotation.slerp(next_rotation, factor)

                            add_key(location, rotation)

                    frame += frame_step
            case 'SUBFRAME':
                for _ in range(frame_count):
                    context.scene.frame_set(frame=int(frame), subframe=frame % 1.0)

                    for export_bone in export_bones:
                        location, rotation = _get_pose_bone_location_and_rotation(
                            pose_bone=export_bone.pose_bone,
                            armature_object=export_bone.armature_object,
                            export_space=options.export_space,
                            scale=export_bone.scale,
                            coordinate_system_transform=coordinate_system_transform,
                            has_false_root_bone=psx_bone_create_result.has_false_root_bone,
                        )
                        add_key(location, rotation)

                    frame += frame_step

        frame_start_index += frame_count

        psa.sequences[export_sequence.name] = psa_sequence

        context.window_manager.progress_update(export_sequence_index)

    # Restore the previous actions & frame.
    for armature_object, action in saved_armature_object_actions.items():
        armature_object.animation_data.action = action

    context.scene.frame_set(saved_frame_current)

    context.window_manager.progress_end()

    return psa
