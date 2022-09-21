import random

from pathlib import Path
from blenderset.utils import mesh
import bpy
from blenderset.assets import AssetGenerationFailed, AssetGenerator
from blenderset.utils.tags import filter_by_tags


class VehicleCreate(bpy.types.Operator):
    bl_idname = "blenderset.vehicle_create"
    bl_label = "Create Vehicles"
    bl_options = {"REGISTER", "UNDO"}

    nbr_of_vehicles: bpy.props.IntProperty(name="Number of Vehicles", default=1)

    def execute(self, context):
        GenerateVehicleAlongPath(context, self.nbr_of_vehicles).create()
        return {"FINISHED"}


class VehicleUpdate(bpy.types.Operator):
    bl_idname = "blenderset.vehicle_update"
    bl_label = "Update Vehicle"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        GenerateVehicleAlongPath(context).update_all()
        return {"FINISHED"}


class VehiclePanel(bpy.types.Panel):
    bl_idname = "AxisVehicles"
    bl_label = "Vehicles"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Synthetic"

    # bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        op = self.layout.operator("blenderset.vehicle_create", text="Create")
        op.nbr_of_vehicles = 2
        op = self.layout.operator("blenderset.vehicle_update", text="Update")


class GenerateVehicleAlongPath(AssetGenerator):
    def __init__(
        self,
        context,
        nbr_of_vehicles=1,
        paths=None,
        tags=None,
        lowpoly=False,
        delta_x_offsets=(0,),
        delta_x_offset_range=(0, 0),
        mirror=False,
        offset_range=(0, 1),
    ):
        super().__init__(context)
        self.nbr_of_vehicles = nbr_of_vehicles
        self.root = self.root / "Tranportation_data"
        model_data = {}
        for fn in self.root.glob("vehicles/*/*/*.blend"):
            if ("lowpoly" in fn.name) != lowpoly:
                continue
            model_data[fn] = {
                "blend": fn,
                "tags": [
                    "model:" + fn.parent.name,
                    "type:" + fn.parent.parent.name,
                ],
            }
        self.model_data = filter_by_tags(model_data, tags)
        self.colors = list(self.root.glob("materials/*/*/*.blend"))
        self.path_names = paths
        self.delta_x_offsets = delta_x_offsets
        self.delta_x_offset_range = delta_x_offset_range
        self.mirror = mirror
        self.offset_range = offset_range

    def create(self):
        for _ in range(self.nbr_of_vehicles):
            vehicle = random.choice(list(self.model_data.values()))
            with bpy.data.libraries.load(str(vehicle["blend"]), link=False) as (
                data_src,
                data_dst,
            ):
                data_dst.collections = data_src.collections
            collection = data_dst.collections[0]
            self.context.scene.collection.children.link(collection)
            obj = collection.objects[0]
            while obj.parent is not None:
                obj = obj.parent

            constraint = obj.pose.bones["Root"].constraints.new("FOLLOW_PATH")
            constraint.use_fixed_location = True
            constraint.use_curve_follow = True

            self.claim_object(obj)
            obj["blenderset.object_class"] = "vehicle"
            self.update_object(obj)

    def update_object(self, obj):
        color = random.choice(self.colors)
        with bpy.data.libraries.load(str(color), link=False) as (data_src, data_dst):
            data_dst.materials = data_src.materials
        material = data_dst.materials[0]
        for o in obj.children_recursive:
            if obj.active_material is None:
                continue
            name = obj.active_material.name.lower()
            if "car" in name and "paint" in name:
                o.active_material = material

        if self.path_names is None:
            paths = self.get_all_objects_of_class("vehicle_path")
        else:
            paths = [bpy.data.objects[n] for n in self.path_names]
        assert len(paths) > 0

        object_meshes, other_meshes = self.get_object_meshes(obj)

        for _ in range(1000):
            obj.pose.bones["Root"].constraints["Follow Path"].target = random.choice(
                paths
            )
            obj.pose.bones["Root"].constraints[
                "Follow Path"
            ].offset_factor = random.uniform(*self.offset_range)
            obj.delta_location[0] = random.choice(
                self.delta_x_offsets
            ) + random.uniform(*self.delta_x_offset_range)

            if not self.mirror or random.uniform(0, 1) < 0.5:
                obj.pose.bones["Root"].constraints[
                    "Follow Path"
                ].forward_axis = "FORWARD_Y"
            else:
                obj.pose.bones["Root"].constraints[
                    "Follow Path"
                ].forward_axis = "TRACK_NEGATIVE_Y"

            for o in object_meshes:
                if o.name in self.bvh_tree_cache:
                    del self.bvh_tree_cache[o.name]
            if not mesh.intersects(object_meshes, other_meshes, self.bvh_tree_cache):
                break
        else:
            raise AssetGenerationFailed(
                f"Could not find non-overlapping position for vehicle '{obj.name}'"
            )
