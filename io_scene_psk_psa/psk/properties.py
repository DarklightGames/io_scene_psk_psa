from bpy.props import EnumProperty
from bpy.types import PropertyGroup

mesh_triangle_types_items = (
    ('MTT_Normal', 'Normal', 'Normal one-sided', 0),
    ('MTT_NormalTwoSided', 'Normal Two-Sided', 'Normal but two-sided', 1),
    ('MTT_Translucent', 'Translucent', 'Translucent two-sided', 2),
    ('MTT_Masked', 'Masked', 'Masked two-sided', 3),
    ('MTT_Modulate', 'Modulate', 'Modulation blended two-sided', 4),
    ('MTT_Placeholder', 'Placeholder', 'Placeholder triangle for positioning weapon. Invisible', 8),
)

mesh_triangle_bit_flags_items = (
    ('MTT_Unlit', 'Unlit', 'Full brightness, no lighting', 16),
    ('MTT_Flat', 'Flat', 'Flat surface, don\'t do bMeshCurvy thing', 32),
    ('MTT_Environment', 'Environment', 'Environment mapped', 64),
    ('MTT_NoSmooth', 'No Smooth', 'No bilinear filtering on this poly\'s texture', 128),
)

class PSX_PG_material(PropertyGroup):
    mesh_triangle_type: EnumProperty(items=mesh_triangle_types_items, name='Triangle Type')
    mesh_triangle_bit_flags: EnumProperty(items=mesh_triangle_bit_flags_items, name='Triangle Bit Flags',
                                          options={'ENUM_FLAG'})

mesh_triangle_types_items_dict = {item[0]: item[3] for item in mesh_triangle_types_items}
mesh_triangle_bit_flags_items_dict = {item[0]: item[3] for item in mesh_triangle_bit_flags_items}


def get_poly_flags(material: PSX_PG_material) -> int:
    poly_flags = 0
    poly_flags |= mesh_triangle_types_items_dict[material.mesh_triangle_type]
    for flag in material.mesh_triangle_bit_flags:
        poly_flags |= mesh_triangle_bit_flags_items_dict[flag]
    return poly_flags

classes = (
    PSX_PG_material,
)
