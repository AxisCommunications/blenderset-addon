import inspect
from pathlib import Path
from random import choice

import bpy

from blenderset.assets import AssetGenerator
from blenderset.utils.hdr import load_HDR


class LightCreate(bpy.types.Operator):
    bl_idname = "blenderset.light_create"
    bl_label = "Create Light Plane"
    bl_options = {"REGISTER", "UNDO"}

    generator_name: bpy.props.StringProperty(
        name="Generator Name", default="GenerateLightPlane"
    )

    def execute(self, context):
        gen = globals()[self.generator_name](context)
        gen.create()
        return {"FINISHED"}


class LightPanel(bpy.types.Panel):
    bl_idname = "blenderset.light_panel"
    bl_label = "Light"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Synthetic"
    # bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        for cls in globals().values():
            if inspect.isclass(cls) and issubclass(cls, AssetGenerator):
                if cls.__module__ == "blenderset.light":
                    op = self.layout.operator(
                        "blenderset.light_create", text=cls.__name__
                    )
                    op.generator_name = cls.__name__


class GenerateLightPlane(AssetGenerator):
    def create(self):
        light_data = bpy.data.lights.new(name="LightPlaneData", type="AREA")
        light_data.energy = 100_000
        light_object = bpy.data.objects.new(name="LightPlane", object_data=light_data)
        collection = self.context.view_layer.active_layer_collection.collection
        collection.objects.link(light_object)
        light_object.location = (0, 0, 4)
        light_object.scale = (1000, 1000, 1)

    def update(self):
        pass


class GenerateHdrDoomLight(AssetGenerator):
    def create(self):
        hdrs = list((self.root / "skys").glob("*.hdr"))
        load_HDR(str(choice(hdrs)), "DoomLight")

    def update(self):
        pass
