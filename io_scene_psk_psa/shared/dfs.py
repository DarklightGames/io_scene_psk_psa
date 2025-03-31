"""
Depth-first object iterator functions for Blender collections and view layers.

These functions are used to iterate over objects in a collection or view layer in a depth-first manner, including
instances. This is useful for exporters that need to traverse the object hierarchy in a predictable order.
"""

from typing import Optional, Set, Iterable, List

from bpy.types import Collection, Object, ViewLayer, LayerCollection
from mathutils import Matrix


class DfsObject:
    """
    Represents an object in a depth-first search.
    """
    def __init__(self, obj: Object, instance_objects: List[Object], matrix_world: Matrix):
        self.obj = obj
        self.instance_objects = instance_objects
        self.matrix_world = matrix_world

    @property
    def is_visible(self) -> bool:
        """
        Check if the object is visible.

        @return: True if the object is visible, False otherwise.
        """
        if self.instance_objects:
            return self.instance_objects[-1].visible_get()
        return self.obj.visible_get()

    @property
    def is_selected(self) -> bool:
        """
        Check if the object is selected.
        @return: True if the object is selected, False otherwise.
        """
        if self.instance_objects:
            return self.instance_objects[-1].select_get()
        return self.obj.select_get()


def _dfs_object_children(obj: Object, collection: Collection) -> Iterable[Object]:
    """
    Construct a list of objects in hierarchy order from `collection.objects`, only keeping those that are in the
    collection.

    @param obj: The object to start the search from.
    @param collection:  The collection to search in.
    @return: An iterable of objects in hierarchy order.
    """
    yield obj
    for child in obj.children:
        if child.name in collection.objects:
            yield from _dfs_object_children(child, collection)


def dfs_objects_in_collection(collection: Collection) -> Iterable[Object]:
    """
    Returns a depth-first iterator over all objects in a collection, only keeping those that are directly in the
    collection.

    @param collection: The collection to search in.
    @return: An iterable of objects in hierarchy order.
    """
    objects_hierarchy = []
    for obj in collection.objects:
        if obj.parent is None or obj.parent not in set(collection.objects):
            objects_hierarchy.append(obj)
    for obj in objects_hierarchy:
        yield from _dfs_object_children(obj, collection)


def dfs_collection_objects(collection: Collection, visible_only: bool = False) -> Iterable[DfsObject]:
    """
    Depth-first search of objects in a collection, including recursing into instances.

    @param collection: The collection to search in.
    @return: An iterable of tuples containing the object, the instance objects, and the world matrix.
    """
    yield from _dfs_collection_objects_recursive(collection)


def _dfs_collection_objects_recursive(
        collection: Collection,
        instance_objects: Optional[List[Object]] = None,
        matrix_world: Matrix = Matrix.Identity(4),
        visited: Optional[Set[Object]]=None
) -> Iterable[DfsObject]:
    """
    Depth-first search of objects in a collection, including recursing into instances.
    This is a recursive function.

    @param collection: The collection to search in.
    @param instance_objects: The running hierarchy of instance objects.
    @param matrix_world: The world matrix of the current object.
    @param visited: A set of visited object-instance pairs.
    @return: An iterable of tuples containing the object, the instance objects, and the world matrix.
    """

    # We want to also yield the top-level instance object so that callers can inspect the selection status etc.
    if visited is None:
        visited = set()

    if instance_objects is None:
        instance_objects = list()

    # First, yield all objects in child collections.
    for child in collection.children:
        yield from _dfs_collection_objects_recursive(child, instance_objects, matrix_world.copy(), visited)

    # Then, evaluate all objects in this collection.
    for obj in dfs_objects_in_collection(collection):
        visited_pair = (obj, instance_objects[-1] if instance_objects else None)
        if visited_pair in visited:
            continue
        # If this an instance, we need to recurse into it.
        if obj.instance_collection is not None:
            # Calculate the instance transform.
            instance_offset_matrix = Matrix.Translation(-obj.instance_collection.instance_offset)
            # Recurse into the instance collection.
            yield from _dfs_collection_objects_recursive(obj.instance_collection,
                                                         instance_objects + [obj],
                                                         matrix_world @ (obj.matrix_world @ instance_offset_matrix),
                                                         visited)
        else:
            # Object is not an instance, yield it.
            yield DfsObject(obj, instance_objects, matrix_world @ obj.matrix_world)
            visited.add(visited_pair)


def dfs_view_layer_objects(view_layer: ViewLayer) -> Iterable[DfsObject]:
    """
    Depth-first iterator over all objects in a view layer, including recursing into instances.

    @param view_layer: The view layer to inspect.
    @return: An iterable of tuples containing the object, the instance objects, and the world matrix.
    """
    visited = set()
    def layer_collection_objects_recursive(layer_collection: LayerCollection):
        for child in layer_collection.children:
            yield from layer_collection_objects_recursive(child)
        # Iterate only the top-level objects in this collection first.
        yield from _dfs_collection_objects_recursive(layer_collection.collection, visited=visited)

    yield from layer_collection_objects_recursive(view_layer.layer_collection)


def _is_dfs_object_visible(obj: Object, instance_objects: List[Object]) -> bool:
    """
    Check if a DFS object is visible.

    @param obj: The object.
    @param instance_objects: The instance objects.
    @return: True if the object is visible, False otherwise.
    """
    if instance_objects:
        return instance_objects[-1].visible_get()
    return obj.visible_get()
