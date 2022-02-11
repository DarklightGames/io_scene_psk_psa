from .data import *
from ..helpers import *
from typing import Dict


class PsaBuilderOptions(object):
    def __init__(self):
        self.sequence_source = 'ACTIONS'
        self.actions = []
        self.marker_names = []
        self.bone_filter_mode = 'ALL'
        self.bone_group_indices = []
        self.should_use_original_sequence_names = False
        self.should_trim_timeline_marker_sequences = True


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

        # Ensure that we actually have items that we are going to be exporting.
        if options.sequence_source == 'ACTIONS' and len(options.actions) == 0:
            raise RuntimeError('No actions were selected for export')
        elif options.sequence_source == 'TIMELINE_MARKERS' and len(options.marker_names) == 0:
            raise RuntimeError('No timeline markers were selected for export')

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
            root_bone_names = [x.name for x in root_bones]
            raise RuntimeError('Exported bone hierarchy must have a single root bone.'
                               f'The bone hierarchy marked for export has {len(root_bones)} root bones: {root_bone_names}')

        # Build list of PSA bones.
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

        # Populate the export sequence list.
        class ExportSequence:
            def __init__(self):
                self.name = ''
                self.frame_min = 0
                self.frame_max = 0
                self.action = None
                self.nla_strips_to_be_muted = []

        export_sequences = []

        if options.sequence_source == 'ACTIONS':
            for action in options.actions:
                if len(action.fcurves) == 0:
                    continue
                export_sequence = ExportSequence()
                export_sequence.action = action
                export_sequence.name = get_psa_sequence_name(action, options.should_use_original_sequence_names)
                export_sequence.frame_min, export_sequence.frame_max = [int(x) for x in action.frame_range]
                export_sequences.append(export_sequence)
            pass
        elif options.sequence_source == 'TIMELINE_MARKERS':
            sequence_frame_ranges = self.get_timeline_marker_sequence_frame_ranges(armature, context, options)
            for name, (frame_min, frame_max) in sequence_frame_ranges.items():
                export_sequence = ExportSequence()
                export_sequence.action = None
                export_sequence.name = name
                export_sequence.frame_min = frame_min
                export_sequence.frame_max = frame_max
                export_sequence.nla_strips_to_be_muted = get_nla_strips_ending_at_frame(armature, frame_min)
                export_sequences.append(export_sequence)
        else:
            raise ValueError(f'Unhandled sequence source: {options.sequence_source}')

        frame_start_index = 0

        # Now build the PSA sequences.
        # We actually alter the timeline frame and simply record the resultant pose bone matrices.
        for export_sequence in export_sequences:
            armature.animation_data.action = export_sequence.action
            context.view_layer.update()

            psa_sequence = Psa.Sequence()

            frame_min = export_sequence.frame_min
            frame_max = export_sequence.frame_max

            psa_sequence.name = bytes(export_sequence.name, encoding='windows-1252')
            psa_sequence.frame_count = frame_max - frame_min + 1
            psa_sequence.frame_start_index = frame_start_index
            psa_sequence.fps = context.scene.render.fps

            frame_count = frame_max - frame_min + 1

            # Store the mute state of the NLA strips we need to mute so we can restore the state after we are done.
            nla_strip_mute_statuses = {x: x.mute for x in export_sequence.nla_strips_to_be_muted}
            for nla_strip in export_sequence.nla_strips_to_be_muted:
                nla_strip.mute = True

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
                    key.time = 1.0 / psa_sequence.fps

                    psa.keys.append(key)

                export_sequence.bone_count = len(pose_bones)
                export_sequence.track_time = frame_count

            # Restore the mute state of the NLA strips we muted beforehand.
            for nla_strip, mute in nla_strip_mute_statuses.items():
                nla_strip.mute = mute

            frame_start_index += frame_count

            psa.sequences[export_sequence.name] = psa_sequence

        return psa

    def get_timeline_marker_sequence_frame_ranges(self, object, context, options: PsaBuilderOptions) -> Dict:
        # Timeline markers need to be sorted so that we can determine the sequence start and end positions.
        sequence_frame_ranges = dict()
        sorted_timeline_markers = list(sorted(context.scene.timeline_markers, key=lambda x: x.frame))
        sorted_timeline_marker_names = list(map(lambda x: x.name, sorted_timeline_markers))

        for marker_name in options.marker_names:
            marker = context.scene.timeline_markers[marker_name]
            frame_min = marker.frame
            # Determine the final frame of the sequence based on the next marker.
            # If no subsequent marker exists, use the maximum frame_end from all NLA strips.
            marker_index = sorted_timeline_marker_names.index(marker_name)
            next_marker_index = marker_index + 1
            frame_max = 0
            if next_marker_index < len(sorted_timeline_markers):
                # There is a next marker. Use that next marker's frame position as the last frame of this sequence.
                frame_max = sorted_timeline_markers[next_marker_index].frame
                if options.should_trim_timeline_marker_sequences:
                    nla_strips = get_nla_strips_in_timeframe(object, marker.frame, frame_max)
                    frame_max = min(frame_max, max(map(lambda x: x.frame_end, nla_strips)))
                    frame_min = max(frame_min, min(map(lambda x: x.frame_start, nla_strips)))
            else:
                # There is no next marker.
                # Find the final frame of all the NLA strips and use that as the last frame of this sequence.
                for nla_track in object.animation_data.nla_tracks:
                    for strip in nla_track.strips:
                        frame_max = max(frame_max, strip.frame_end)

            if frame_min == frame_max:
                continue

            sequence_frame_ranges[marker_name] = int(frame_min), int(frame_max)

        return sequence_frame_ranges
