from bpy.props import EnumProperty
from bpy.types import PropertyGroup

mesh_triangle_types_items = (
    ('NORMAL', 'Normal', '', 0),
    ('NORMAL_TWO_SIDED', 'Normal Two-Sided', '', 1),
    ('TRANSLUCENT', 'Translucent', '', 2),
    ('MASKED', 'Masked', '', 3),
    ('MODULATE', 'Modulate', '', 4),
    ('PLACEHOLDER', 'Placeholder', '', 8),
)

mesh_triangle_bit_flags_items = (
    ('UNLIT', 'Unlit', '', 16),
    ('FLAT', 'Flat', '', 32),
    ('ENVIRONMENT', 'Environment', '', 64),
    ('NO_SMOOTH', 'No Smooth', '', 128),
)

class PSX_PG_material(PropertyGroup):
    mesh_triangle_type: EnumProperty(items=mesh_triangle_types_items, name='Triangle Type')
    mesh_triangle_bit_flags: EnumProperty(items=mesh_triangle_bit_flags_items, name='Triangle Bit Flags',
                                          options={'ENUM_FLAG'})

mesh_triangle_types_items_dict = {item[0]: item[3] for item in mesh_triangle_types_items}
mesh_triangle_bit_flags_items_dict = {item[0]: item[3] for item in mesh_triangle_bit_flags_items}


def triangle_type_and_bit_flags_to_poly_flags(mesh_triangle_type: str, mesh_triangle_bit_flags: set[str]) -> int:
    poly_flags = 0
    poly_flags |= mesh_triangle_types_items_dict.get(mesh_triangle_type, 0)
    for flag in mesh_triangle_bit_flags:
        poly_flags |= mesh_triangle_bit_flags_items_dict.get(flag, 0)
    return poly_flags


def poly_flags_to_triangle_type_and_bit_flags(poly_flags: int) -> (str, set[str]):
    try:
        triangle_type = next(item[0] for item in mesh_triangle_types_items if item[3] == (poly_flags & 15))
    except StopIteration:
        triangle_type = 'NORMAL'
    triangle_bit_flags = {item[0] for item in mesh_triangle_bit_flags_items if item[3] & poly_flags}
    return triangle_type, triangle_bit_flags


classes = (
    PSX_PG_material,
)
