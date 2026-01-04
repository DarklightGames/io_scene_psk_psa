class PSX_PG_material:
    mesh_triangle_type: str
    mesh_triangle_bit_flags: set[str]


class PskImportMixin:
    should_import_vertex_colors: bool
    vertex_color_space: str
    should_import_vertex_normals: bool
    should_import_extra_uvs: bool
    components: str
    should_import_mesh: bool
    should_import_materials: bool
    should_import_armature: bool
    bone_length: float
    should_import_shape_keys: bool
    scale: float
    bdk_repository_id: str
