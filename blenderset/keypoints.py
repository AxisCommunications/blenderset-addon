import bpy
import numpy as np

from blenderset.utils.lens import LensDist


def get_keypoints(name):
    obj = bpy.data.objects[name]
    if obj.pose is None:
        return {}
    if "CC_Base_R_Eye" in obj.pose.bones:
        head_center = (
            obj.pose.bones["CC_Base_R_Eye"].tail + obj.pose.bones["CC_Base_L_Eye"].tail
        ) / 2
        head_center = (np.array(obj.matrix_world) @ np.array(list(head_center) + [1]))[:3]
        left_foot = (
            np.array(obj.matrix_world)
            @ np.array(list(obj.pose.bones["CC_Base_L_ToeBase"].tail) + [1])
        )[:3]
        right_foot = (
            np.array(obj.matrix_world)
            @ np.array(list(obj.pose.bones["CC_Base_R_ToeBase"].tail) + [1])
        )[:3]
        return {
            "head_center": list(head_center),
            "left_foot": list(left_foot),
            "right_foot": list(right_foot),
        }
    elif obj['blenderset.creator_class'] == 'GenerateBedlam':
        keypoints = {}
        for name, bone in obj.pose.bones.items():
            keypoints[name] = list((np.array(obj.matrix_world) @ np.array(list(bone.head) + [1]))[:3])
        keypoints["head_center"] = keypoints["head"]
        return keypoints
    else:
        return {}


def project_keypoints(keypoints, camera_matrix, lens):
    for name, (x, y, z) in list(keypoints.items()):
        x, y, z, _ = camera_matrix @ (x, y, z, 1)
        u, v = lens.world_to_image([x, y, z])[0]
        keypoints[name + "_img"] = (u, v)
    return keypoints


def add_object_keypoints(objects, camera_matrix, lens):
    for obj in objects.values():
        try:
            obj["keypoints"] = project_keypoints(
                get_keypoints(obj["name"]), camera_matrix, lens
            )
        except KeyError:
            obj["keypoints"] = {}
