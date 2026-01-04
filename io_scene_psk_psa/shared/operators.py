from bpy.types import Operator
from bpy.props import BoolProperty

from .types import PsxBoneExportMixin
from typing import cast as typing_cast

from .helpers import get_collection_export_operator_from_context, get_psk_input_objects_for_collection, populate_bone_collection_list



class PSK_OT_bone_collection_list_populate(Operator):
    bl_idname = 'psk.bone_collection_list_populate'
    bl_label = 'Populate Bone Collection List'
    bl_description = 'Populate the bone collection list from the armature that will be used in this collection export'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No valid export operator found in context')
            return {'CANCELLED'}
        if context.collection is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No active collection')
            return {'CANCELLED'}
        try:
            input_objects = get_psk_input_objects_for_collection(context.collection)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}
        if not input_objects.armature_objects:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No armature modifiers found on mesh objects')
            return {'CANCELLED'}
        export_operator = typing_cast(PsxBoneExportMixin, export_operator)

        # Save and restore the selected status of the bones collections.
        selected_status: dict[int, bool] = dict()
        for bone_collection in export_operator.bone_collection_list:
            selected_status[hash(bone_collection)] = bone_collection.is_selected

        populate_bone_collection_list(export_operator.bone_collection_list, input_objects.armature_objects)

        for bone_collection in export_operator.bone_collection_list:
            bone_collection.is_selected = selected_status[hash(bone_collection)]

        return {'FINISHED'}


class PSK_OT_bone_collection_list_select_all(Operator):
    bl_idname = 'psk.bone_collection_list_select_all'
    bl_label = 'Select All'
    bl_description = 'Select all bone collections'
    bl_options = {'INTERNAL'}

    is_selected: BoolProperty(default=True)

    def execute(self, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No valid export operator found in context')
            return {'CANCELLED'}
        export_operator = typing_cast(PsxBoneExportMixin, export_operator)
        for item in export_operator.bone_collection_list:
            item.is_selected = self.is_selected
        return {'FINISHED'}


_classes = (
    PSK_OT_bone_collection_list_populate,
    PSK_OT_bone_collection_list_select_all,
)
from bpy.utils import register_classes_factory
register, unregister = register_classes_factory(_classes)
