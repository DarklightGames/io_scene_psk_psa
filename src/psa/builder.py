import bpy
import mathutils
from .data import *

class PsaBuilder(object):
    def __init__(self):
        # TODO: add options in here (selected anims, eg.)
        pass

    def build(self, context) -> Psa:
        object = context.view_layer.objects.active

        if object.type != 'ARMATURE':
            raise RuntimeError('Selected object must be an Armature')

        armature = object

        if armature.animation_data is None:
            raise RuntimeError('No animation data for armature')

        psa = Psa()

        bones = list(armature.data.bones)

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

        print('---- ACTIONS ----')

        frame_start_index = 0
        for action in bpy.data.actions:
            if len(action.fcurves) == 0:
                continue

            armature.animation_data.action = action
            context.view_layer.update()

            frame_min, frame_max = [int(x) for x in action.frame_range]

            sequence = Psa.Sequence()
            sequence.name = bytes(action.name, encoding='utf-8')
            sequence.frame_count = frame_max - frame_min + 1
            sequence.frame_start_index = frame_start_index
            sequence.fps = 30  # TODO: fill in later with r

            for frame in range(frame_min, frame_max + 1):
                context.scene.frame_set(frame)

                print(frame)

                for bone_index, bone in enumerate(armature.pose.bones):
                    # TODO: is the cast-to-matrix necesssary? (guessing no)
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

            psa.sequences.append(sequence)

        return psa
