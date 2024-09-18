import bpy
from pathlib import Path

if __name__ == "__main__":
    for module in open(Path(__file__).parent / "build" / "blender" / "addons_to_enable").readlines():
        bpy.ops.preferences.addon_enable(module=module.strip())
    bpy.ops.wm.save_userpref()
