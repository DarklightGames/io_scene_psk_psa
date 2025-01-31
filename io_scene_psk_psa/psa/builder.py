from typing import Optional

from bpy.types import Bone, Action, PoseBone

from .data import *
from ..shared.helpers import *


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
        self.animation_data: Optional[AnimData] = None
        self.sequences: List[PsaBuildSequence] = []
        self.bone_filter_mode: str = 'ALL'
        self.bone_collection_indices: List[int] = []
        self.sequence_name_prefix: str = ''
        self.sequence_name_suffix: str = ''
        self.root_motion: bool = False
        self.scale = 1.0
        self.sampling_mode: str = 'INTERPOLATED'  # One of ('INTERPOLATED', 'SUBFRAME')
        self.export_space = 'WORLD'
        self.forward_axis = 'X'
        self.up_axis = 'Z'


def _get_pose_bone_location_and_rotation(pose_bone: PoseBone, armature_object: Object, root_motion: bool, scale: float, coordinate_system_transform: Matrix) -> Tuple[Vector, Quaternion]:
    if pose_bone.parent is not None:
        pose_bone_matrix = pose_bone.matrix
        pose_bone_parent_matrix = pose_bone.parent.matrix
        pose_bone_matrix = pose_bone_parent_matrix.inverted() @ pose_bone_matrix
    else:
        if root_motion:
            # Get the bone's pose matrix, taking the armature object's world matrix into account.
            pose_bone_matrix = armature_object.matrix_world @ pose_bone.matrix
        else:
            # Use the bind pose matrix for the root bone.
            pose_bone_matrix = pose_bone.matrix

        # The root bone is the only bone that should be transformed by the coordinate system transform, since all
        # other bones are relative to their parent bones.
        pose_bone_matrix = coordinate_system_transform @ pose_bone_matrix

    location = pose_bone_matrix.to_translation()
    rotation = pose_bone_matrix.to_quaternion().normalized()

    location *= scale

    if pose_bone.parent is not None:
        rotation.conjugate()

    return location, rotation


def build_psa(context: bpy.types.Context, options: PsaBuildOptions) -> Psa:
    active_object = context.view_layer.objects.active

    psa = Psa()

    armature_object = active_object
    armature_data = typing.cast(Armature, armature_object.data)
    bones: List[Bone] = list(iter(armature_data.bones))

    # The order of the armature bones and the pose bones is not guaranteed to be the same.
    # As a result, we need to reconstruct the list of pose bones in the same order as the
    # armature bones.
    bone_names = [x.name for x in bones]

    # Get a list of all the bone indices and instigator bones for the bone filter settings.
    export_bone_names = get_export_bone_names(armature_object, options.bone_filter_mode, options.bone_collection_indices)
    bone_indices = [bone_names.index(x) for x in export_bone_names]

    # Make the bone lists contain only the bones that are going to be exported.
    bones = [bones[bone_index] for bone_index in bone_indices]

    # No bones are going to be exported.
    if len(bones) == 0:
        raise RuntimeError('No bones available for export')

    # The bone building code should be shared between the PSK and PSA exporters, since they both need to build a nearly identical bone list.

    # Build list of PSA bones.
    psa.bones = convert_blender_bones_to_psx_bones(
        bones=bones,
        bone_class=Psa.Bone,
        export_space=options.export_space,
        armature_object_matrix_world=armature_object.matrix_world,
        scale=options.scale,
        forward_axis=options.forward_axis,
        up_axis=options.up_axis
    )

    # Add prefixes and suffices to the names of the export sequences and strip whitespace.
    for export_sequence in options.sequences:
        export_sequence.name = f'{options.sequence_name_prefix}{export_sequence.name}{options.sequence_name_suffix}'
        export_sequence.name = export_sequence.name.strip()

    # Save the current action and frame so that we can restore the state once we are done.
    saved_frame_current = context.scene.frame_current
    saved_action = options.animation_data.action

    # Now build the PSA sequences.
    # We actually alter the timeline frame and simply record the resultant pose bone matrices.
    frame_start_index = 0

    context.window_manager.progress_begin(0, len(options.sequences))

    coordinate_system_transform = get_coordinate_system_transform(options.forward_axis, options.up_axis)

    for export_sequence_index, export_sequence in enumerate(options.sequences):
        # Look up the pose bones for the bones that are going to be exported.
        pose_bones = [(bone_names.index(bone.name), bone) for bone in export_sequence.armature_object.pose.bones]
        pose_bones.sort(key=lambda x: x[0])
        pose_bones = [x[1] for x in pose_bones]
        pose_bones = [pose_bones[bone_index] for bone_index in bone_indices]

        # Link the action to the animation data and update view layer.
        export_sequence.anim_data.action = export_sequence.nla_state.action
        context.view_layer.update()

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

        sequence_duration = frame_count_raw / export_sequence.fps

        # If this is a reverse sequence, we need to reverse the frame step.
        if frame_start > frame_end:
            frame_step = -frame_step

        psa_sequence = Psa.Sequence()
        try:
            psa_sequence.name = bytes(export_sequence.name, encoding='windows-1252')
        except UnicodeEncodeError:
            raise RuntimeError(f'Sequence name "{export_sequence.name}" contains characters that cannot be encoded in the Windows-1252 codepage')
        psa_sequence.frame_count = frame_count
        psa_sequence.frame_start_index = frame_start_index
        psa_sequence.fps = frame_count / sequence_duration
        psa_sequence.bone_count = len(pose_bones)
        psa_sequence.track_time = frame_count
        psa_sequence.key_reduction = 1.0

        frame = float(frame_start)

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
                            for pose_bone in pose_bones:
                                location, rotation = _get_pose_bone_location_and_rotation(
                                    pose_bone,
                                    export_sequence.armature_object,
                                    root_motion=options.root_motion,
                                    scale=options.scale,
                                    coordinate_system_transform=coordinate_system_transform
                                )
                                last_frame_bone_poses.append((location, rotation))

                        next_frame = None
                        next_frame_bone_poses.clear()

                    # If this is not a subframe, just use the last frame's bone poses.
                    if frame % 1.0 == 0:
                        for i in range(len(pose_bones)):
                            add_key(*last_frame_bone_poses[i])
                    else:
                        # Otherwise, this is a subframe, so we need to interpolate the pose between the next frame and the last frame.
                        if next_frame is None:
                            next_frame = last_frame + 1
                            context.scene.frame_set(frame=next_frame)
                            for pose_bone in pose_bones:
                                location, rotation = _get_pose_bone_location_and_rotation(
                                    pose_bone,
                                    export_sequence.armature_object,
                                    root_motion=options.root_motion,
                                    scale=options.scale,
                                    coordinate_system_transform=coordinate_system_transform
                                )
                                next_frame_bone_poses.append((location, rotation))

                        factor = frame % 1.0

                        for i in range(len(pose_bones)):
                            last_location, last_rotation = last_frame_bone_poses[i]
                            next_location, next_rotation = next_frame_bone_poses[i]

                            location = last_location.lerp(next_location, factor)
                            rotation = last_rotation.slerp(next_rotation, factor)

                            add_key(location, rotation)

                    frame += frame_step
            case 'SUBFRAME':
                for _ in range(frame_count):
                    context.scene.frame_set(frame=int(frame), subframe=frame % 1.0)

                    for pose_bone in pose_bones:
                        location, rotation = _get_pose_bone_location_and_rotation(pose_bone, export_sequence.armature_object, options)
                        add_key(location, rotation)

                    frame += frame_step

        frame_start_index += frame_count

        psa.sequences[export_sequence.name] = psa_sequence

        context.window_manager.progress_update(export_sequence_index)

    # Restore the previous action & frame.
    options.animation_data.action = saved_action
    context.scene.frame_set(saved_frame_current)

    context.window_manager.progress_end()

    return psa
