import bpy

if __name__ == "__main__":
    for module in ["blenderset", "cc_blender_tools-2_0_0"]:
        bpy.ops.preferences.addon_enable(module=module)
        bpy.ops.wm.save_userpref()
