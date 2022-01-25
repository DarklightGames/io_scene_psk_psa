from .data import *
from ..helpers import *


class PsaBuilderOptions(object):
    def __init__(self):
        self.actions = []
        self.bone_filter_mode = 'ALL'
        self.bone_group_indices = []
        self.should_use_original_sequence_names = False


class PsaBuilder(object):
    def __init__(self):
        pass

    def build(self, context, options: PsaBuilderOptions) -> Psa:
        object = context.view_layer.objects.active

        if object.type != 'ARMATURE':
            raise RuntimeError('Selected object must be an Armature')

        armature = object

        if armature.animation_data is None:
            raise RuntimeError('No animation data for armature')

        psa = Psa()

        bones = list(armature.data.bones)

        # The order of the armature bones and the pose bones is not guaranteed to be the same.
        # As as a result, we need to reconstruct the list of pose bones in the same order as the
        # armature bones.
        bone_names = [x.name for x in bones]
        pose_bones = [(bone_names.index(bone.name), bone) for bone in armature.pose.bones]
        del bone_names
        pose_bones.sort(key=lambda x: x[0])
        pose_bones = [x[1] for x in pose_bones]

        bone_indices = list(range(len(bones)))

        # If bone groups are specified, get only the bones that are in that specified bone groups and their ancestors.
        if options.bone_filter_mode == 'BONE_GROUPS':
            bone_indices = get_export_bone_indices_for_bone_groups(armature, options.bone_group_indices)

        # Make the bone lists contain only the bones that are going to be exported.
        bones = [bones[bone_index] for bone_index in bone_indices]
        pose_bones = [pose_bones[bone_index] for bone_index in bone_indices]

        if len(bones) == 0:
            # No bones are going to be exported.
            raise RuntimeError('No bones available for export')

        # Ensure that the exported hierarchy has a single root bone.
        root_bones = [x for x in bones if x.parent is None]
        if len(root_bones) > 1:
            root_bone_names = [x.name for x in bones]
            raise RuntimeError('Exported bone hierarchy must have a single root bone.'
                               f'The bone hierarchy marked for export has {len(root_bones)} root bones: {root_bone_names}')

        for pose_bone in bones:
            psa_bone = Psa.Bone()
            psa_bone.name = bytes(pose_bone.name, encoding='utf-8')

            try:
                parent_index = bones.index(pose_bone.parent)
                psa_bone.parent_index = parent_index
                psa.bones[parent_index].children_count += 1
            except ValueError:
                psa_bone.parent_index = -1

            if pose_bone.parent is not None:
                rotation = pose_bone.matrix.to_quaternion()
                rotation.x = -rotation.x
                rotation.y = -rotation.y
                rotation.z = -rotation.z
                quat_parent = pose_bone.parent.matrix.to_quaternion().inverted()
                parent_head = quat_parent @ pose_bone.parent.head
                parent_tail = quat_parent @ pose_bone.parent.tail
                location = (parent_tail - parent_head) + pose_bone.head
            else:
                location = armature.matrix_local @ pose_bone.head
                rot_matrix = pose_bone.matrix @ armature.matrix_local.to_3x3()
                rotation = rot_matrix.to_quaternion()

            psa_bone.location.x = location.x
            psa_bone.location.y = location.y
            psa_bone.location.z = location.z

            psa_bone.rotation.x = rotation.x
            psa_bone.rotation.y = rotation.y
            psa_bone.rotation.z = rotation.z
            psa_bone.rotation.w = rotation.w

            psa.bones.append(psa_bone)

        frame_start_index = 0

        for action in options.actions:
            if len(action.fcurves) == 0:
                continue

            armature.animation_data.action = action
            context.view_layer.update()

            frame_min, frame_max = [int(x) for x in action.frame_range]

            sequence = Psa.Sequence()

            sequence_name = get_psa_sequence_name(action, options.should_use_original_sequence_names)

            sequence.name = bytes(sequence_name, encoding='windows-1252')
            sequence.frame_count = frame_max - frame_min + 1
            sequence.frame_start_index = frame_start_index
            sequence.fps = context.scene.render.fps

            frame_count = frame_max - frame_min + 1

            for frame in range(frame_count):
                context.scene.frame_set(frame_min + frame)

                for pose_bone in pose_bones:
                    key = Psa.Key()
                    pose_bone_matrix = pose_bone.matrix

                    if pose_bone.parent is not None:
                        pose_bone_parent_matrix = pose_bone.parent.matrix
                        pose_bone_matrix = pose_bone_parent_matrix.inverted() @ pose_bone_matrix

                    location = pose_bone_matrix.to_translation()
                    rotation = pose_bone_matrix.to_quaternion().normalized()

                    if pose_bone.parent is not None:
                        rotation.x = -rotation.x
                        rotation.y = -rotation.y
                        rotation.z = -rotation.z

                    key.location.x = location.x
                    key.location.y = location.y
                    key.location.z = location.z
                    key.rotation.x = rotation.x
                    key.rotation.y = rotation.y
                    key.rotation.z = rotation.z
                    key.rotation.w = rotation.w
                    key.time = 1.0 / sequence.fps

                    psa.keys.append(key)

                frame_start_index += 1

                sequence.bone_count = len(pose_bones)
                sequence.track_time = frame_count

            psa.sequences[action.name] = sequence

        return psa
