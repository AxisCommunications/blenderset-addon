from pathlib import Path

from cv2 import imwrite

import bpy

from blenderset.character import GenerateGalleryCharacter
from blenderset.render import PreviewRenderer, Renderer

root = Path("renders/gallery")
# renderer = PreviewRenderer(bpy.context, root)
renderer = Renderer(bpy.context, root)

character_ids = GenerateGalleryCharacter(bpy.context).model_data.keys()

for name in character_ids:
    out = Path(name).parent.name
    if (root / out).exists():
        continue
    bpy.ops.wm.open_mainfile(filepath="gallery_background.blend")
    gen = GenerateGalleryCharacter(bpy.context, pose_tags="Standing")
    gen.create(override_character=gen.model_data[name])
    renderer.render(str(out))
    (root / "new" / f"{out}.png").hardlink_to(root / out / "rgb.png")
