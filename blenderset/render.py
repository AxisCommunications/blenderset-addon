import json
import uuid
from pathlib import Path

import bpy
import numpy as np
from vi3o.image import imwrite, imread
import gzip

from blenderset.camera import get_current_camera
from blenderset.keypoints import add_object_keypoints
from blenderset.utils.exr import ExrFile


class Renderer:
    samples = 4096
    use_denoising = True
    device = "GPU"

    def __init__(self, context, output_root, save_blend=False, save_exr=False, output_format='JPEG'):
        self.context = context
        self.output_root = Path(output_root)
        self.save_blend = save_blend
        self.save_exr = save_exr
        self.output_format = output_format

    def setup(self):
        self.context.scene.render.engine = "CYCLES"
        self.context.scene.cycles.samples = self.samples
        self.context.scene.cycles.use_denoising = self.use_denoising
        self.context.scene.cycles.use_adaptive_sampling = True
        self.context.scene.cycles.adaptive_threshold = 0.01
        self.context.scene.cycles.device = self.device
        self.context.scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"
        self.context.scene.render.image_settings.color_mode = "RGB"
        self.context.window.view_layer.use_pass_cryptomatte_asset = True
        self.context.window.view_layer.use_pass_z = True
        self.context.scene.render.image_settings.color_depth = "32"

    def render_all_frames(self, asset_generator, out_dir=None):
        if out_dir is None:
            out_dir = str(uuid.uuid1())
        for f in range(self.context.scene.frame_start, self.context.scene.frame_end + 1):
            bpy.context.scene.frame_set(f)
            self.render_all_cameras(asset_generator, out_dir + '/' + str(f))

    def render_all_cameras(self, asset_generator, out_dir=None):
        if out_dir is None:
            out_dir = str(uuid.uuid1())
        for cam in bpy.context.view_layer.objects:
            if cam.type == 'CAMERA':
                bpy.context.scene.camera = cam
                if bpy.context.scene.node_tree is not None:
                    composer_nodes = bpy.context.scene.node_tree.nodes
                    if 'blenderset.Background' in composer_nodes:
                        composer_nodes['blenderset.Background'].image = cam.data.background_images[0].image
                if 'blenderset.resolution_x' in cam:
                    bpy.context.scene.render.resolution_x = cam['blenderset.resolution_x']
                    bpy.context.scene.render.resolution_y = cam['blenderset.resolution_y']

                self.render(asset_generator, out_dir + '/' + cam.name)

    def render(self, asset_generator, out_dir=None):
        self.setup()
        asset_generator.setup_render()
        if out_dir is None:
            out_dir = str(uuid.uuid1())
        out = self.output_root / out_dir
        out.mkdir(parents=True, exist_ok=True)

        roi = asset_generator.get_all_proprty_values("blenderset.walkable_roi")
        scene_info = dict(
            roi = [[list(p) for p in poly] for poly in roi],
            background_collected_from_game = asset_generator.get_all_proprty_values('blenderset.collected_from'),
        )
        with open(out / "scene_info.json", "w") as fd:
            json.dump(scene_info, fd)

        layers_path = out / "layers.exr"
        self.context.scene.render.filepath = str(layers_path)

        self.context.view_layer.update()
        bpy.ops.render.render(write_still=True)

        if self.output_format == 'JPEG':
            ext = 'jpg'
        else:
            ext = self.output_format.lower()

        if self.output_format == 'PNG':
            bpy.context.scene.render.image_settings.color_mode = 'RGBA'

        self.context.scene.render.image_settings.file_format = self.output_format
        self.context.scene.render.image_settings.color_depth = "8"
        rgb_fn = str(out / ("rgb." + ext))
        bpy.data.images["Render Result"].save_render(rgb_fn)

        camera_matrix, lens = get_current_camera()
        np.save(out / "camera_matrix.npy", camera_matrix)
        lens.save_json(out / "lens.json")

        if self.save_blend:
            bpy.ops.file.make_paths_absolute()
            bpy.ops.wm.save_as_mainfile(filepath=str(out / "scene.blend"))

        exr = ExrFile(layers_path)
        objects, segmentations = exr.get_objects()
        add_object_keypoints(objects, camera_matrix, lens)
        assert len(segmentations) == 1
        with gzip.GzipFile(out / "segmentations.npy.gz", "w") as fd:
            np.save(fd, segmentations[0])
        with (out / "objects.json").open("w") as fd:
            json.dump(objects, fd)
        head_mask = exr.get_head_mask()
        if head_mask is not None:
            imwrite(255 * head_mask.astype(np.uint8), str(out / "head_mask.png"))

        depth = exr.get_depth_image()
        depth[imread(rgb_fn)[:,:,3] == 0] = -1
        with gzip.GzipFile(out / "depth.npy.gz", "w") as fd:
            np.save(fd, depth)

        if not self.save_exr:
            layers_path.unlink()

        return out


class PreviewRenderer(Renderer):
    samples = 1
    use_denoising = False


class PreviewCPURenderer(PreviewRenderer):
    device = "CPU"
