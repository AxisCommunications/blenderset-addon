import bpy, bmesh
from mathutils.bvhtree import BVHTree
import numpy as np

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


def bounding_box(obj_list):
    dg = bpy.context.evaluated_depsgraph_get()
    verts = []
    for obj in obj_list:
        bm = bmesh.new()
        bm.from_object(obj, dg)
        bm.transform(obj.matrix_world)
        verts.append(np.array([v.co for v in bm.verts]))
    verts = np.row_stack(verts)
    x0, x1 = verts[:,0].min(), verts[:,0].max()
    y0, y1 = verts[:,1].min(), verts[:,1].max()
    z0, z1 = verts[:,2].min(), verts[:,2].max()
    bbox = [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)]
    return bbox