import json
import logging
import random
from collections import defaultdict
from pathlib import Path

import bpy
import numpy as np

from blenderset.assets import AssetGenerationFailed, AssetGenerator
from shapely.geometry import MultiPolygon, Polygon, Point

from blenderset.utils.tags import filter_by_tags
from blenderset.utils import mesh

logger = logging.getLogger(__name__)


class CharacterCreate(bpy.types.Operator):
    bl_idname = "blenderset.charcater_create"
    bl_label = "Create Characters"
    bl_options = {"REGISTER", "UNDO"}

    nbr_of_characters: bpy.props.IntProperty(name="Number of Characters", default=1)

    def execute(self, context):
        GenerateCharacter(context, self.nbr_of_characters).create()
        return {"FINISHED"}


class CharacterUpdate(bpy.types.Operator):
    bl_idname = "blenderset.charcater_update"
    bl_label = "Update Characters"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        GenerateCharacter(context).update_all()
        return {"FINISHED"}


class CharacterPanel(bpy.types.Panel):
    bl_idname = "blenderset.character_panel"
    bl_label = "Character"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Synthetic"
    # bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        op = self.layout.operator("blenderset.charcater_create", text="Create")
        op.nbr_of_characters = 2
        op = self.layout.operator("blenderset.charcater_update", text="Update")


class GenerateCharacter(AssetGenerator):
    def __init__(
        self, context, nbr_of_characters=1, tags=None, pose_tags=None, roi=None
    ):
        super().__init__(context)
        self.animation_root = self.root / "Character_Creator_v3.41/Animations/Blender/"
        self.root = self.root / "Character_Creator_v3.41/BlenderCharacters256/"
        self.nbr_of_characters = nbr_of_characters
        self.override_roi = roi

        models = list(self.root.glob("*/*.[fF]bx"))
        fn = self.metadata_dir / "character_metadata.json"
        character_data = json.load(fn.open())
        blocked = set(character_data['_blocked'])
        model_data = {}
        for fn in models:
            name = fn.parent.name
            if name in blocked:
                continue
            try:
                entry = character_data[name]
            except KeyError:
                logger.warning("No metadata for %s, skipping", name)
                continue
            entry["fbx"] = fn
            entry["tags"] = []
            for t in [
                "gender",
                "age_group",
                "skin_color",
                "hair_color",
                "body_type",
                "wearing_hard_hat",
                "big_hair",
                "origin",
                "partition",
            ]:
                if t not in entry:
                    continue
                values = entry[t]
                if not isinstance(values, list):
                    values = [values]
                for val in values:
                    entry["tags"].append(t + ":" + val)
            model_data[fn] = entry
        self.model_data = filter_by_tags(model_data, tags)

        animation_data = json.load(open(self.metadata_dir / "animations_metadata.json"))
        self.animation_data = filter_by_tags(animation_data, pose_tags)
        self.animation_names = defaultdict(list)
        self.animation_lengths = defaultdict(list)
        for key, entry in self.animation_data.items():
            self.animation_names[entry["avatar"]].append(key)
            self.animation_lengths[entry["avatar"]].append(entry["length"])

        addons = bpy.context.preferences.addons
        for name in addons.keys():
            if name.startswith("cc_blender_tools-"):
                addons[name].preferences.render_target = "CYCLES"

    def create(self, override_character=None):
        for _ in range(self.nbr_of_characters):
            if override_character is None:
                character = random.choice(list(self.model_data.values()))
            else:
                character = override_character
            fn = character["fbx"]
            print("Importing", fn)
            bpy.ops.cc3.importer(filepath=str(fn), param="IMPORT_QUALITY")
            obj = self.context.object
            while obj.parent is not None:
                obj = obj.parent
            self.claim_object(obj)
            obj.animation_data_clear()
            obj["blenderset.object_class"] = "human"

            avatar = character["avatar_base"]
            anim = random.choices(
                self.animation_names[avatar], weights=self.animation_lengths[avatar]
            )[0]
            obj["blenderset.animation"] = self.ensure_animation_linked(anim)
            self.create_head_mask_output(obj)

            self.update_object(obj)

    def setup_render(self):
        bpy.ops.cc3.scene(param="CYCLES_SETUP")

    def ensure_animation_linked(self, key):
        animation = self.animation_data[key]
        name = animation["name"]
        if name not in bpy.data.actions:
            with bpy.data.libraries.load(
                str(self.animation_root / animation["file"]), link=True
            ) as (src, dst):
                dst.actions = [name]
            name = dst.actions[0].name
        return name

    def update_object(self, obj):
        obj.rotation_euler = [0, 0, np.random.uniform(0, 2 * np.pi)]

        action = bpy.data.actions[obj["blenderset.animation"]]
        obj.pose.apply_pose_from_action(
            action, evaluation_time=np.random.uniform(*action.frame_range)
        )
        obj.pose.bones["CC_Base_Hip"].location = [0, 0, 0]

        object_meshes, other_meshes = self.get_object_meshes(obj)

        for _ in range(1000):
            x, y = self.random_position(self.get_roi())
            obj.location = [x, y, 0]
            # if self.minimal_distance_to_other(obj) > 0.7:
            if not mesh.intersects(object_meshes, other_meshes):
                break
        else:
            raise AssetGenerationFailed(
                f"Could not find non-overlapping position for character '{obj.name}'"
            )

    def minimal_distance_to_other(self, obj):
        mind = float("inf")
        for other in bpy.data.objects:
            if other is obj:
                continue
            if "blenderset.creator_class" in other:
                if other["blenderset.creator_class"] == self.__class__.__name__:
                    d = other.location - obj.location
                    mind = min(mind, d.magnitude)
        return mind

    def get_roi(self):
        if self.override_roi is not None:
            return self.override_roi
        walkable_polys = self.get_all_proprty_values("blenderset.visible_walkable_roi")
        return MultiPolygon([Polygon(p) for p in walkable_polys])

    def random_position(self, roi):
        if roi.bounds:
            min_x, min_y, max_x, max_y = roi.bounds
            while True:
                random_point = Point(
                    [np.random.uniform(min_x, max_x), np.random.uniform(min_y, max_y)]
                )
                if random_point.within(roi):
                    return random_point.x, random_point.y
        else:
            min_x, min_y, max_x, max_y = -1, -1, 1, 1
            random_point = Point(
                [np.random.uniform(min_x, max_x), np.random.uniform(min_y, max_y)]
            )
            return random_point.x, random_point.y

    def create_head_mask_output(self, obj):
        for o in obj.children:
            if "CC_Base_Head" not in o.vertex_groups:
                continue
            grp = o.vertex_groups["CC_Base_Head"].index
            color = o.data.vertex_colors.new(name="HeadMask")
            head_mask = np.array(
                [grp in [g.group for g in v.groups] for v in o.data.vertices]
            )
            for l in o.data.loops:
                color.data[l.index].color = (0, 0, 0, int(head_mask[l.vertex_index]))
                # loop_vertex_index = np.empty(len(o.data.loops), int)
                # o.data.loops.foreach_get('vertex_index', loop_vertex_index)
                # loop_head_mask = head_mask[loop_vertex_index].astype(int)
                # color_values = np.zeros((len(color.data), 4))
                # color_values[loop_head_mask, 3] = 1
                # color.data.foreach_set('color', color_values.flatten())

            for slot in o.material_slots:
                material = bpy.data.materials[slot.name]
                assert material.use_nodes
                tree = material.node_tree
                input = tree.nodes.new(type="ShaderNodeVertexColor")
                input.layer_name = color.name
                input.location = (0, 0)
                output = tree.nodes.new(type="ShaderNodeOutputAOV")
                output.name = "HeadMask"
                output.location = (300, 0)
                tree.links.new(input.outputs["Alpha"], output.inputs["Value"])

        for aov in bpy.context.scene.view_layers["View Layer"].aovs:
            if aov.name == "HeadMask":
                break
        else:
            bpy.ops.scene.view_layer_add_aov()
            bpy.context.scene.view_layers["View Layer"].aovs[-1].name = "HeadMask"
            bpy.context.scene.view_layers["View Layer"].aovs[-1].type = "VALUE"


class GenerateGalleryCharacter(GenerateCharacter):
    def update_object(self, obj):
        obj.location = [-0.6, 0, 0]
        action = bpy.data.actions[obj["blenderset.animation"]]
        obj.pose.apply_pose_from_action(
            action, evaluation_time=np.random.uniform(*action.frame_range)
        )
        obj.pose.bones["CC_Base_Hip"].location = [0, 0, 0]
