from .data import *


class PsaBuilderOptions(object):
    def __init__(self):
        self.actions = []
        self.bone_filter_mode = 'NONE'
        self.bone_group_indices = []


# https://git.cth451.me/cth451/blender-addons/blob/master/io_export_unreal_psk_psa.py
class PsaBuilder(object):
    def __init__(self):
        # TODO: add options in here (selected anims, eg.)
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
        pose_bones.sort(key=lambda x: x[0])
        pose_bones = [x[1] for x in pose_bones]

        bone_indices = list(range(len(bones)))

        if options.bone_filter_mode == 'BONE_GROUPS':
            # Get a list of the bone indices that are explicitly part of the bone groups we are including.
            bone_index_stack = []
            for bone_index, pose_bone in enumerate(pose_bones):
                if pose_bone.bone_group_index in options.bone_group_indices:
                    bone_index_stack.append(bone_index)

            # For each bone that is explicitly being added, recursively walk up the hierarchy and ensure that all of
            # those bone indices are also in the list.
            bone_indices = set()
            while len(bone_index_stack) > 0:
                bone_index = bone_index_stack.pop()
                bone = bones[bone_index]
                if bone.parent is not None:
                    parent_bone_index = bone_names.index(bone.parent.name)
                    if parent_bone_index not in bone_indices:
                        bone_index_stack.append(parent_bone_index)
                bone_indices.add(bone_index)

        del bone_names

        # Sort out list of bone indices to be exported.
        bone_indices = sorted(list(bone_indices))

        # The bone lists now contains only the bones that are going to be exported.
        bones = [bones[bone_index] for bone_index in bone_indices]
        pose_bones = [pose_bones[bone_index] for bone_index in bone_indices]

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
            sequence.name = bytes(action.name, encoding='utf-8')
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
