from pathlib import Path

import bpy

from blenderset.render import PreviewRenderer, Renderer

root = Path("renders/delfinen_heights2")
# renderer = PreviewRenderer(bpy.context, root)
renderer = Renderer(bpy.context, root)

try:
    bpy.ops.wm.open_mainfile(filepath="delfinen2.blend")
except RuntimeError as e:
    print("Warning: RuntimeError on load", e)

for height in [3.0, 3.5, 4.0, 5.0, 6.0]:
    bpy.data.objects["Camera"].location[2] = height
    renderer.render(str(height))
