import bpy, bmesh
from mathutils.bvhtree import BVHTree

from itertools import chain


def intersects(obj_list1, obj_list2, tree_cache=None):
    dg = bpy.context.evaluated_depsgraph_get()
    if tree_cache is None:
        tree_cache = {}
    for obj in chain(obj_list1, obj_list2):
        if obj.name in tree_cache:
            continue
        bm = bmesh.new()
        bm.from_object(obj, dg)
        bm.transform(obj.matrix_world)
        tree_cache[obj.name] = BVHTree.FromBMesh(bm)

    for obj1 in obj_list1:
        obj1_tree = tree_cache[obj1.name]
        for obj2 in obj_list2:
            obj2_tree = tree_cache[obj2.name]
            if obj1_tree.overlap(obj2_tree):
                return True
    return False
