from .data import *


class PsaBuilderOptions(object):
    def __init__(self):
        self.actions = []


# https://git.cth451.me/cth451/blender-addons/blob/master/io_export_unreal_psk_psa.py
class PsaBuilder(object):
    def __init__(self):
        # TODO: add options in here (selected anims, eg.)
        pass

    def build(self, context, options) -> Psa:
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

        for bone in bones:
            psa_bone = Psa.Bone()
            psa_bone.name = bytes(bone.name, encoding='utf-8')
            psa_bone.children_count = len(bone.children)

            try:
                psa_bone.parent_index = bones.index(bone.parent)
            except ValueError:
                psa_bone.parent_index = -1

            if bone.parent is not None:
                rotation = bone.matrix.to_quaternion()
                rotation.x = -rotation.x
                rotation.y = -rotation.y
                rotation.z = -rotation.z
                quat_parent = bone.parent.matrix.to_quaternion().inverted()
                parent_head = quat_parent @ bone.parent.head
                parent_tail = quat_parent @ bone.parent.tail
                location = (parent_tail - parent_head) + bone.head
            else:
                location = armature.matrix_local @ bone.head
                rot_matrix = bone.matrix @ armature.matrix_local.to_3x3()
                rotation = rot_matrix.to_quaternion()

            psa_bone.location.x = location.x
            psa_bone.location.y = location.y
            psa_bone.location.z = location.z

            psa_bone.rotation.x = rotation.x
            psa_bone.rotation.y = rotation.y
            psa_bone.rotation.z = rotation.z
            psa_bone.rotation.w = rotation.w

            psa.bones.append(psa_bone)

        for action in options.actions:
            if len(action.fcurves) == 0:
                continue

            armature.animation_data.action = action
            context.view_layer.update()

            frame_min, frame_max = [int(x) for x in action.frame_range]

            sequence = Psa.Sequence()
            sequence.name = bytes(action.name, encoding='utf-8')
            sequence.frame_count = frame_max - frame_min + 1
            sequence.frame_start_index = 0
            sequence.fps = context.scene.render.fps

            frame_count = frame_max - frame_min + 1

            for frame in range(frame_count):
                context.scene.frame_set(frame_min + frame)

                for bone in pose_bones:
                    key = Psa.Key()
                    pose_bone_matrix = bone.matrix

                    if bone.parent is not None:
                        pose_bone_parent_matrix = bone.parent.matrix
                        pose_bone_matrix = pose_bone_parent_matrix.inverted() @ pose_bone_matrix

                    location = pose_bone_matrix.to_translation()
                    rotation = pose_bone_matrix.to_quaternion().normalized()

                    if bone.parent is not None:
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

            psa.sequences.append(sequence)

        return psa
