from bpy.types import Panel


class PSK_PT_material(Panel):
    bl_label = 'PSK Material'
    bl_idname = 'PSK_PT_material'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        material = context.material
        layout.prop(material.psk, 'mesh_triangle_type')
        col = layout.column()
        col.prop(material.psk, 'mesh_triangle_bit_flags', expand=True, text='Flags')


classes = (
    PSK_PT_material,
)
