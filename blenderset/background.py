import json
from math import dist
from pathlib import Path
from random import choice, uniform
from mathutils import Vector
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid

import shapely
import bpy
import numpy as np
import os
import random as rnd
import math

from .assets import AssetGenerator, ComposedAssetGenerator
from .utils import lens as lenses
from .utils.debug import show_points, show_poly
from .utils.lens import rotmat, rotmat_xyz
from .utils.tags import get_all_tags, filter_by_tags
from .camera import GenerateCameraFromBackground


class Background(bpy.types.Operator):
    """Create random background with camera"""

    bl_idname = "blenderset.background"
    bl_label = "Create Background"
    bl_options = {"REGISTER", "UNDO"}

    background_name: bpy.props.StringProperty(
        name="Background Name", default="background_1.jpg"
    )
    alternative_image: bpy.props.StringProperty(name="Alternative Image", default="")

    def execute(self, context):
        gen = GenerateBackgroundAndCamera(
            context,
            background_name=self.background_name,
            alternative_image=self.alternative_image,
        )
        gen.create()
        return {"FINISHED"}


class SyntheticBackground(bpy.types.Operator):
    """Create random background"""

    bl_idname = "blenderset.synthetic_background"
    bl_label = "Create Background"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        gen = GenerateSyntheticBackground(context)
        gen.create()
        return {"FINISHED"}


class SelectionToRoi(bpy.types.Operator):
    """Create random background"""

    bl_idname = "blenderset.selection_to_roi"
    bl_label = "Set ROI to selection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        set_roi_to_bound_box(context.selected_objects)
        return {"FINISHED"}


def set_roi_to_bound_box(objects):
    xx, yy = [], []
    for obj in objects:
        for pkt in obj.bound_box:
            pkt = obj.matrix_world @ Vector(pkt)
            xx.append(pkt[0])
            yy.append(pkt[1])
    x1, x2 = min(xx), max(xx)
    y1, y2 = min(yy), max(yy)
    roi = [(x1, y1), (x1, y2), (x2, y2), (x2, y1)]
    for key in obj.keys():
        if key.startswith("blenderset.walkable_roi"):
            del obj[key]
    obj["blenderset.walkable_roi.0"] = roi


class BackgroundPanel(bpy.types.Panel):
    bl_idname = "blenderset.background_panel"
    bl_label = "Background"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Synthetic"
    # bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        op = self.layout.operator(
            "blenderset.background", text="Create Office Corridor"
        )
        op.background_name = "office_corridor.jpg"

        op = self.layout.operator("blenderset.background", text="Create Nyhamnen")
        op.background_name = "31879_0.jpg"

        op = self.layout.operator(
            "blenderset.synthetic_background", text="Create Random Synthetic"
        )

        op = self.layout.operator("blenderset.background", text="Create Random")
        op.background_name = "{RANDOM}"

        op = self.layout.operator("blenderset.selection_to_roi")


class GenerateBackground(AssetGenerator):
    def __init__(
        self, context, tags=None, background_name=None, alternative_image=None
    ):
        super().__init__(context)
        fn = self.metadata_dir / "images_metadata.json"
        background_data = json.load(fn.open())
        self.background_data = filter_by_tags(background_data, tags)
        self.lens = None
        if background_name == "{RANDOM}":
            background_name = None
        self.background_name = background_name
        self.alternative_image = alternative_image

    def create(self):
        if self.background_name is None:
            background = choice(list(self.background_data.keys()))
        else:
            background = self.background_name
        self.create_named_background(background, self.alternative_image)

    def update(self):
        pass

    def create_lens(self, name):
        background_data = self.background_data[name]
        shape = tuple(background_data["original_img_dimension"][::-1] + [3])
        self.height = background_data["camera_height"] / 100
        if hasattr(lenses, background_data["lens"]):
            self.lens = getattr(lenses, background_data["lens"])(shape)
        elif background_data["lens"].endswith(".json"):
            json_name = self.root / "Backgrounds" / "images" / background_data["lens"]
            self.lens = lenses.create_lens_from_json(shape, json_name)
            if "translation" in self.lens.json_data:
                self.height = self.lens.json_data["translation"][2]
        else:
            raise ValueError("Bad lens: " + background_data["lens"])

    def create_named_background(self, name, alternative_image=None):
        if not alternative_image:
            image = self.root / "Backgrounds" / "images" / name
        else:
            image = self.root / "Backgrounds" / "images" / alternative_image
        self.create_lens(name)
        background_data = self.background_data[name]

        # Gird
        n = 120
        xx, yy = np.meshgrid(np.linspace(0, 1, n), np.linspace(0, 1, n))
        h, w = xx.shape
        idx = -1 * np.ones_like(xx, int)
        if "mask_radius" not in background_data:
            mask = np.ones_like(xx) == 1
        else:
            mask = (xx - 0.5) ** 2 + (yy - 0.5) ** 2 < background_data[
                "mask_radius"
            ] ** 2
        idx[mask] = range(mask.sum())

        # Mesh
        faces = [
            (idx[y, x], idx[y, x + 1], idx[y + 1, x + 1], idx[y + 1, x])
            for y in range(h - 1)
            for x in range(w - 1)
        ]
        faces = [[i for i in f if i > -1] for f in faces if sum(i > -1 for i in f) > 2]
        uv = [(x, y) for x, y in zip(xx[mask], yy[mask])]
        pkt = np.array(uv)
        pkt = 1 - pkt
        pkt[:, 0] *= self.lens.width
        pkt[:, 1] *= self.lens.height
        vertices = self.lens.image_to_world(pkt, -self.height)
        vertices[:, 2] = 0
        edges = []

        mesh = bpy.data.meshes.new("BackgroundMesh")
        mesh.from_pydata(vertices, edges, faces)
        mesh.update()

        uv_layer = mesh.uv_layers.new(name="UV")
        for l in mesh.loops:
            uv_layer.data[l.index].uv = uv[l.vertex_index]

        # Object
        obj = bpy.data.objects.new("BackgroundObject", mesh)
        material = self.create_textured_material(str(image))
        obj.data.materials.append(material)
        self.claim_object(obj)  # FIXME: Claim textures and maetrials as well
        obj["blenderset.object_class"] = "ground_plane"
        obj["blenderset.camera_height"] = self.height

        collection = self.context.view_layer.active_layer_collection.collection
        collection.objects.link(obj)

        # Roi
        shape = tuple(background_data["original_img_dimension"][::-1] + [3])
        h, w, _ = shape
        if "poly" not in background_data:
            background_data["poly"] = [[(0, 0), (0, h), (w, h), (w, 0)]]
            background_data["image_height"] = h
        for i, roi in enumerate(background_data["poly"]):
            roi = self.image_roi_to_world(roi, shape, background_data["image_height"])
            # show_poly(roi)
            obj[f"blenderset.walkable_roi.{i}"] = [list(p) for p in roi]

    def create_textured_material(self, image):
        mat = bpy.data.materials.new(name="MaterialName")
        image = Path(image)
        if image.is_dir():
            image = choice(list(image.glob("*")))
        img = bpy.data.images.load(str(image))
        mat.use_nodes = True
        tree = mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()
        output = nodes.new(type="ShaderNodeOutputMaterial")
        output.location = (900, 0)
        diffuse = nodes.new(type="ShaderNodeBsdfPrincipled")
        diffuse.location = (600, 0)
        diffuse.inputs["Roughness"].default_value = 0.75
        diffuse.inputs["Specular IOR Level"].default_value = 0.25
        coords = nodes.new(type="ShaderNodeTexCoord")
        coords.location = (0, 0)
        diffuseteximg = nodes.new(type="ShaderNodeTexImage")
        diffuseteximg.image = img
        diffuseteximg.location = (300, 0)
        links.new(coords.outputs["UV"], diffuseteximg.inputs["Vector"])
        links.new(diffuseteximg.outputs["Color"], diffuse.inputs["Base Color"])
        links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])
        return mat

    def image_roi_to_world(self, roi, shape, annotated_height):
        roi = np.asarray(roi, float)
        img_height_original = shape[0]
        roi *= img_height_original / annotated_height  # Scale
        roi[:, 0] = shape[1] - roi[:, 0]  # Mirror
        roi = self.lens.image_to_world(roi, -self.height)
        roi[:, 2] = 0
        return roi


class GenerateSyntheticBackground(AssetGenerator):
    def __init__(self, context):
        super().__init__(context)
        self.textures = list((self.root / "polyhaven").glob("*.blend"))

    def create(self):
        path = choice(self.textures)
        with bpy.data.libraries.load(str(path.absolute()), link=False) as (src, dst):
            dst.objects = ["Plane"]
        plane = dst.objects[0]
        collection = self.context.view_layer.active_layer_collection.collection
        collection.objects.link(plane)
        plane.hide_render = False
        plane.hide_viewport = False
        self.claim_object(plane)
        plane["blenderset.object_class"] = "ground_plane"
        material = bpy.data.materials[plane.material_slots[0].name]

        plane_scale = 100
        plane.scale[0] = plane_scale
        plane.scale[1] = plane_scale
        material.node_tree.nodes["Mapping"].inputs[3].default_value[0] = plane_scale
        material.node_tree.nodes["Mapping"].inputs[3].default_value[1] = plane_scale

        self.context.view_layer.update()
        set_roi_to_bound_box([plane])

    def update(self):
        pass


class GeneratePremadeBackground(AssetGenerator):
    def __init__(
        self, context, blend_file, camera_name=None, apply_background_modifiers=True
    ):
        super().__init__(context)
        self.blend_file = str(self.root / "background_models" / blend_file)
        self.camera_name = camera_name
        self.apply_background_modifiers = apply_background_modifiers

    def create(self):
        bpy.ops.wm.open_mainfile(filepath=self.blend_file)
        if self.camera_name is not None:
            bpy.data.scenes["Scene"].camera = bpy.data.objects[self.camera_name]
        if self.apply_background_modifiers:
            ctx = bpy.context.copy()
            for obj in self.get_all_objects_of_class("ground_plane"):
                ctx["object"] = obj
                for m in obj.modifiers:
                    bpy.ops.object.modifier_apply(ctx, modifier=m.name)

    def update(self):
        pass


class GenerateBackgroundAndCamera(ComposedAssetGenerator):
    def __init__(self, context, *args, **kwargs):
        self.background_generator = GenerateBackground(context, *args, **kwargs)
        super().__init__(context)

    def setup(self):
        return [
            self.background_generator,
            GenerateCameraFromBackground(self.context, self.background_generator),
        ]
