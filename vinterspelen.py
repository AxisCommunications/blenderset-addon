from pathlib import Path

import bpy

from blenderset.render import PreviewRenderer, Renderer
from blenderset.scenarios import VinterspelenVR, VinterspelenRobotLab

root = Path("renders/vinterspelen")
# renderer = PreviewRenderer(bpy.context, root)
renderer = Renderer(bpy.context, root)


if False:
    # for n in [10, 15, 20, 25, 30, 35, 40]:
    for n in [40, 30, 25, 35]:
        try:
            bpy.ops.wm.open_mainfile(filepath="blank.blend")
            gen = VinterspelenVR(bpy.context, n)
            gen.create()
            renderer.render(f"vr_{n}pers")
        except Exception as e:
            print(e)

if True:
    for n in [40, 30, 20]:
        try:
            bpy.ops.wm.open_mainfile(filepath="blank.blend")
            gen = VinterspelenRobotLab(bpy.context, n)
            gen.create()
            renderer.render(f"robotlab_{n}pers")
        except Exception as e:
            print(e)
