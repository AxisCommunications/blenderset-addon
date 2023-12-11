import json
import uuid
from pathlib import Path

import bpy
import numpy as np
from vi3o.image import imwrite

from blenderset.camera import get_current_camera
from blenderset.keypoints import add_object_keypoints
from blenderset.utils.exr import ExrFile


class Renderer:
    samples = 4096
    use_denoising = True
    device = "GPU"

    def __init__(self, context, output_root):
        self.context = context
        self.output_root = Path(output_root)

    def setup(self):
        self.context.scene.render.engine = "CYCLES"
        self.context.scene.cycles.samples = self.samples
        self.context.scene.cycles.use_denoising = self.use_denoising
        self.context.scene.cycles.use_adaptive_sampling = True
        self.context.scene.cycles.adaptive_threshold = 0.005
        self.context.scene.cycles.device = self.device
        self.context.scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
        self.context.scene.render.image_settings.color_mode = "RGB"
        self.context.scene.view_layers["View Layer"].use_pass_cryptomatte_asset = True
        self.context.scene.view_layers["View Layer"].use_pass_z = True
        self.context.scene.render.image_settings.color_depth = "32"

    def render(self, asset_generator, out_dir=None):
        self.setup()
        asset_generator.setup_render()
        if out_dir is None:
            out_dir = str(uuid.uuid1())
        out = self.output_root / out_dir
        out.mkdir(parents=True, exist_ok=True)

        # bpy.ops.file.make_paths_absolute()
        # bpy.ops.wm.save_as_mainfile(filepath=str(out / "scene.blend"))
        layers_path = out / "layers.exr"
        self.context.scene.render.filepath = str(layers_path)

        self.context.view_layer.update()
        bpy.ops.render.render(write_still=True)

        self.context.scene.render.image_settings.file_format = "PNG"
        self.context.scene.render.image_settings.color_depth = "8"
        bpy.data.images["Render Result"].save_render(str(out / "rgb.png"))

        camera_matrix, lens = get_current_camera()
        np.save(out / "camera_matrix.npy", camera_matrix)
        lens.save_json(out / "lens.json")

        exr = ExrFile(layers_path)
        objects, segmentations = exr.get_objects()
        add_object_keypoints(objects, camera_matrix, lens)
        assert len(segmentations) == 1
        np.save(out / "segmentations.npy", segmentations[0])
        with (out / "objects.json").open("w") as fd:
            json.dump(objects, fd)
        head_mask = exr.get_head_mask()
        if head_mask is not None:
            imwrite(255 * head_mask.astype(np.uint8), str(out / "head_mask.png"))

        depth = exr.get_depth_image()
        np.save(out / "depth.npy", depth)

        layers_path.unlink()

        return out


class PreviewRenderer(Renderer):
    samples = 1
    use_denoising = False


class PreviewCPURenderer(PreviewRenderer):
    device = "CPU"
