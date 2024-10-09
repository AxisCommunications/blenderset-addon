from random import choice, shuffle
import numpy as np
from tempfile import NamedTemporaryFile

from pathlib import Path
from blenderset.utils import mesh
import bpy
from blenderset.utils.tags import filter_by_tags
from blenderset.assets import AssetGenerationFailed, AssetGenerator
from .utils.debug import show_points, show_poly
import json
from time import time
from shapely.geometry import MultiPolygon, Polygon, Point
from blenderset.assets import ComposedAssetGenerator
from blenderset.background import GeneratePremadeBackground
from blenderset.light import GenerateHdrDoomLight


class BedlamCreate(bpy.types.Operator):
    bl_idname = "blenderset.bedlam_create"
    bl_label = "Create Bedlams"
    bl_options = {"REGISTER", "UNDO"}

    nbr_of_bedlams: bpy.props.IntProperty(name="Number of Bedlams", default=1)

    def execute(self, context):
        GenerateBedlam(context, nbr_of_bedlams=self.nbr_of_bedlams).create()
        return {"FINISHED"}

class BedlamCreateSoccer(bpy.types.Operator):
    bl_idname = "blenderset.bedlam_create_soccer"
    bl_label = "Create Bedlams"
    bl_options = {"REGISTER", "UNDO"}

    nbr_of_bedlams: bpy.props.IntProperty(name="Number of Bedlams", default=1)

    def execute(self, context):
        GenerateBedlam(context, GenerateSoccerClothes(context), nbr_of_bedlams=self.nbr_of_bedlams).create()
        return {"FINISHED"}

class BedlamUpdate(bpy.types.Operator):
    bl_idname = "blenderset.bedlam_update"
    bl_label = "Update Bedlam"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        GenerateBedlam(context).update_all()
        return {"FINISHED"}


class BedlamPanel(bpy.types.Panel):
    bl_idname = "blenderset.bedlam_panel"
    bl_label = "Bedlams"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Synthetic"

    def draw(self, context):
        op = self.layout.operator("blenderset.bedlam_create", text="Create")
        op.nbr_of_bedlams = 1
        op = self.layout.operator("blenderset.bedlam_create_soccer", text="Create Soccer Player")
        op = self.layout.operator("blenderset.bedlam_update", text="Update")
        op = self.layout.operator("blenderset.bedlam_create_soccer_scene", text="Soccer Scene")


class ClothAssetGenerator(AssetGenerator):
    def create(self, obj, animation_fn, animation_offset, step_size, height_offset):
        raise NotImplementedError

    def filter_animations(self, animations):
        raise NotImplementedError


class GenerateBedlamClothes(ClothAssetGenerator):
    def create(self, obj, animation_fn, animation_offset, step_size, height_offset):
        """
            Picks some random cloths from the BEDLAM animation `animation_fn`
            and dresses the the charecter object `obj`in those.
        """
        assert step_size == 1
        cloth = self.anim_to_cloth(animation_fn)
        texture = choice(list((cloth.parent.parent.parent / "clothing_textures").glob('*')))
        diffuse = texture / (texture.name + '_diffuse_1001.png')
        normal = texture / (texture.name + '_normal_1001.png')
        bpy.ops.wm.alembic_import(filepath=str(cloth), relative_path=False, as_background_job=False)
        cloth_obj = self.context.object
        mat = create_textured_material(diffuse, normal)
        cloth_obj.data.materials.append(mat)
        cloth_obj.modifiers[0].cache_file.frame_offset = -100 - animation_offset
        cloth_obj.parent = obj
        cloth_obj.location[2] = height_offset
        cloth_obj['blenderset.animation'] = str(cloth)
        bpy.context.scene.frame_start = 0
        obj['blenderset.player_type'] = 'Bystander'


    def anim_to_cloth(self, fn):
        "Converts a BEDLAM animation filename to the corresponding cloth filename."
        root = self.root / "bedlam"
        name = fn.parent.name
        return root / "clothing" / fn.parent.parent.parent.name / "clothing_simulations" / name / (name + '.abc')

    def filter_animations(self, animations):
        "Filter out the animations for which BEDLAM cloths exists in the asset catalog."
        return [fn for fn in animations if self.anim_to_cloth(fn).exists()]


class GenerateBedlam(AssetGenerator):
    """
        Creates `nbr_of_bedlams` BEDLAM characters animated for `nbr_of_frames`
        frames. The clothing can be customize by setting `cloth_generator` to
        a suitible ClothAssetGenerator. The positions can be customized by
        setting `positioner`to a suitable Positioner.
    """
    override_roi = None

    def __init__(
        self,
        context,
        cloth_generator=None,
        nbr_of_bedlams=1,
        nbr_of_frames=5,
        positioner=None
    ):
        super().__init__(context)
        self.nbr_of_bedlams = nbr_of_bedlams
        self.nbr_of_frames = nbr_of_frames
        root = self.root / "bedlam"
        max_side = 512
        skins_root = root / f"bedlam_body_textures_meshcapade_{max_side}/smpl/MC_texture_skintones/"
        self.skins = dict(
            male = list((skins_root / "male").rglob('*.png')),
            female = list((skins_root / "female").rglob('*.png')),
        )
        self.eye = root / f"bedlam_body_textures_meshcapade_{max_side}/eye/SMPLX_eye.png"
        self.animations = list((root / "gendered_ground_truth").rglob('*/motion_seq.npz'))
        if cloth_generator is None:
            cloth_generator = GenerateBedlamClothes(context)
        self.cloth_generator = cloth_generator
        self.animations = self.cloth_generator.filter_animations(self.animations)
        if positioner is not None:
            self.random_position = positioner.random_position


    def create(self):
        context = self.context
        context.scene.render.fps = 30
        for _ in range(self.nbr_of_bedlams):
            fn = choice(self.animations)
            anim = np.load(fn)
            data = {k: anim[k] for k in anim.keys()}
            n = len(data['poses'])
            nbr_of_frames = min(self.nbr_of_frames, n)
            mocap_framerate = int(data["mocap_frame_rate"]) if "mocap_frame_rate" in data else int(data["mocap_framerate"])
            target_framerate = context.scene.render.fps
            step_size = int(mocap_framerate / target_framerate)
            nbr_of_frames *= step_size

            f = choice(range(len(data['poses']) - nbr_of_frames + 1))
            for k in ['poses', 'global_ori', 'trans']:
                data[k] = data[k][f:f+nbr_of_frames]
            with NamedTemporaryFile(suffix='.npz') as tmp:
                np.savez(tmp.name, **data)
                bpy.ops.object.smplx_add_animation(filepath=tmp.name, anim_format='SMPL-X', target_framerate=target_framerate, keyframe_corrective_pose_weights=True)

            obj = context.object
            gender, offset = ('female', 1.25) if 'female' in context.object.name else ('male', 1.357)
            context.scene.frame_start = 1
            context.scene.frame_end = nbr_of_frames
            offset = adjust_height(context, obj, offset)
            skin = choice(self.skins[gender])
            obj.data.materials.clear()
            obj.data.materials.append(create_textured_material(skin, diffuse2=str(self.eye)))
            reset_pose_and_shape(obj)
            obj.parent["blenderset.object_class"] = "human"
            obj.parent["blenderset.animation"] = str(fn)
            obj.parent["blenderset.animation_start_frame"] = f
            obj.parent["blenderset.gender"] = gender
            obj.parent["blenderset.skin"] = str(skin)

            self.claim_object(obj.parent)
            bpy.context.scene.frame_set(nbr_of_frames // 2 + 1)
            self.update_object(obj.parent)
            self.cloth_generator.create(obj.parent, fn, f, step_size, offset)

            context.scene.frame_start = 0
            context.scene.frame_end = nbr_of_frames
            bpy.context.scene.frame_set(nbr_of_frames // 2 + 1)


    def update_object(self, obj):
        obj.rotation_euler = [0, 0, np.random.uniform(0, 2 * np.pi)]
        object_meshes, other_meshes = self.get_object_meshes(obj)
        walkable_polys = self.get_all_proprty_values("blenderset.walkable_roi")
        roi = MultiPolygon([Polygon(p) for p in walkable_polys])

        for _ in range(1000):
            x, y = self.random_position(roi)
            obj.location = [x, y, 0]
            if not mesh.intersects(object_meshes, other_meshes):
                break
        else:
            raise AssetGenerationFailed(
                f"Could not find non-overlapping position for character '{obj.name}'"
            )

def reset_pose_and_shape(armature):
    """
        Reset the pose and shape keys of an object to it's rest pose/shape and
        insert a keyframe at frame=0 that can be used for binding cloths to
        the object.
    """
    if armature.type != 'ARMATURE':
        armature = armature.parent
    assert armature.type == 'ARMATURE'
    for bone in armature.pose.bones:
        bone.rotation_quaternion = [1,0,0,0]
        bone.location = [0,0,0]
        bone.keyframe_insert(data_path="location", frame=0)
        bone.keyframe_insert(data_path="rotation_quaternion", frame=0)

    for shape_key in bpy.data.shape_keys:
        for key in shape_key.key_blocks:
            key.keyframe_insert(data_path="value", frame=1)
            key.value = 0
            key.keyframe_insert(data_path="value", frame=0)

    bpy.context.scene.frame_set(0)


def create_textured_material(diffuse, normal=None, diffuse2=None):
    """
        Create a new material with the specified `diffuse` and `normal`
        textures. The `diffuse2` texture with be alpha belnded ontop of
        `diffuse`.
    """
    mat = bpy.data.materials.new(name="MaterialName")
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    nodes.clear()
    diffuseteximg = nodes.new(type="ShaderNodeTexImage")
    diffuseteximg.image = bpy.data.images.load(str(diffuse))
    diffuseteximg.location = (300, 0)
    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (900, 0)
    diffuse = nodes.new(type="ShaderNodeBsdfPrincipled")
    diffuse.location = (600, 0)
    diffuse.inputs["Roughness"].default_value = 0.6
    if "Specular IOR Level" in diffuse.inputs:
        diffuse.inputs["Specular IOR Level"].default_value = 0.5
    else:
        diffuse.inputs["Specular"].default_value = 0.5
    if diffuse2 is not None:
        diffuseteximg2 = nodes.new(type="ShaderNodeTexImage")
        diffuseteximg2.image = bpy.data.images.load(str(diffuse2))
        diffuseteximg2.location = (300, 300)
        mix = nodes.new(type="ShaderNodeMix")
        mix.data_type = 'RGBA'
        mix.location = (600, 300)
        links.new(diffuseteximg2.outputs["Alpha"], mix.inputs[0])
        links.new(diffuseteximg.outputs["Color"], mix.inputs[6])
        links.new(diffuseteximg2.outputs["Color"], mix.inputs[7])
        links.new(mix.outputs[2], diffuse.inputs["Base Color"])
    else:
        links.new(diffuseteximg.outputs["Color"], diffuse.inputs["Base Color"])
    links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])

    if normal is not None:
        normal_img = nodes.new(type="ShaderNodeTexImage")
        normal_img.image = bpy.data.images.load(str(normal))
        normal_img.image.colorspace_settings.name = 'Non-Color'
        normal_img.location = (0, -300)
        normal_map = nodes.new(type="ShaderNodeNormalMap")
        normal_map.location = (300, -300)
        links.new(normal_img.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], diffuse.inputs["Normal"])

    return mat

def adjust_height(context, obj, offset):
    "Move the reference point of a SMPL object to make it stand on the ground."
    armature = obj.parent
    armature.location.z += offset

    # Apply location offsets to armature and skinned mesh
    context.view_layer.objects.active = armature
    armature.select_set(True)
    obj.select_set(True)
    bpy.ops.object.transform_apply(location = True, rotation=False, scale=False) # apply to selected objects
    armature.select_set(False)

    # Fix root bone location
    bpy.ops.object.mode_set(mode='EDIT')
    bone = armature.data.edit_bones["root"]
    bone.head = (0.0, 0.0, 0.0)
    bone.tail = (0.0, 0.0, 0.1)
    bpy.ops.object.mode_set(mode='OBJECT')
    context.view_layer.objects.active = obj

    bpy.ops.object.smplx_snap_ground_plane('EXEC_DEFAULT')
    height_offset = armature.location[2]
    armature.location[2] = 0

    for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
        context.scene.frame_set(frame)
        bone = armature.pose.bones['pelvis']
        bone.location[1] += height_offset
        bone.keyframe_insert('location', frame=frame)
    return offset + height_offset


class GenerateSoccerClothes(ClothAssetGenerator):
    """
        Generate soccer uniform cloths for BEDLAM characters.
    """
    def __init__(self, context):
        super().__init__(context)
        self.root = self.root / 'SportCloth'
        self.template_texture_names = {
            'Tshirt': 'BK Häcken_Tshirt_LS_Player_Away',
            'Tshirt_Referee': 'BK Häcken_Tshirt_LS_Player_Away',
            'Tshirt_Long Sleeve': 'BK Häcken_Tshirt_LS_Player_Away',
            'Vest': 'BK Häcken_Tshirt_LS_Player_Away',
            'Pants': 'BK Häcken_Pants_Player_Away',
            'Shorts_Long': 'BK Häcken_Shorts Long_Player Away',
            'Shorts_Short': 'BK Häcken_Shorts Short_Player Away',
            'Socks_Long': 'BK Häcken_Socks Long_Player Away',
            'Socks_Short': 'BK Häcken_Socks Short_Player Away',
        }
        self.alternatives = [
            ['Pants', 'Shorts_Long', 'Shorts_Short'],
            ['Shoe'],
            ['Socks_Short', 'Socks_Long'],
            ['Tshirt', 'Tshirt_Long Sleeve', 'Vest'],
        ]
        self.names = [n.strip() for n in open(self.root / "names.txt").readlines()]
        self.uniforms = json.load(open(self.root / 'JSONS' / 'team_uniforms.json'))

    def create(self, obj, animation_fn, animation_offset, step_size, height_offset):
        clothes_names = [choice(alt) for alt in self.alternatives]
        uniform = choice(list(choice(list(choice(list(self.uniforms.values())).values())).values()))
        self.apply_clothes(obj, clothes_names, uniform, np.random.randint(1, 99), choice(self.names))

    def filter_animations(self, animations):
        return animations

    def apply_clothes(self, obj, clothes_names, uniform, number, name, number_color=(0,0,0,1), name_color=(0,0,0,1)):
        bpy.context.scene.frame_set(0)
        if obj.type == 'ARMATURE':
            armature = obj
            obj = obj.children[0]
        else:
            armature = obj.parent

        textures = {}
        for p in clothes_names:
            if p is None:
                continue
            fn = uniform.get(p + '_001')
            if fn is None:
                continue
            fn = self.root / 'baked_textures' / Path(fn).relative_to("/home/hakan/3d/clothes/SportCloth/JSONS")
            fn = fn.parent / (p + '_001_' + fn.name.replace('.json', '.png'))
            textures[self.template_texture_names[p]] = str(fn)

        if 'female' in obj.name:
            fn = self.root / 'Cloth_Assets' / 'Assets_Female.blend'
        else:
            fn = self.root / 'Cloth_Assets' / 'Assets_Male.blend'
        with bpy.data.libraries.load(str(fn)) as (data_from, data_to):
            data_to.objects = [n + '_001' for n in clothes_names if n is not None]

        img_nbr, img_name = self.make_number_and_name(number, name)
        textures['Numb_39'] = img_nbr
        textures['Player Name'] = img_name
        obj['blenderset.jersey_number'] = number
        obj['blenderset.player_name'] = name

        for clothes in data_to.objects:
            bpy.context.scene.collection.objects.link(clothes)
            clothes.parent = armature
            for mod in clothes.modifiers:
                if mod.type == 'SURFACE_DEFORM':
                    mod.target = obj
                    bpy.ops.object.select_all(action='DESELECT')
                    clothes.select_set(True)
                    bpy.context.view_layer.objects.active = clothes
                    bpy.ops.object.surfacedeform_bind(modifier=mod.name)
                elif mod.type == 'ARMATURE':
                    mod.object = armature

            for slot in clothes.material_slots:
                for node in slot.material.node_tree.nodes:
                    if node.type=='TEX_IMAGE' and node.image:
                        img = textures.get(node.image.name.split('.png')[0])
                        if img is not None:
                            if isinstance(img, str):
                                fn = self.root / img
                                img = bpy.data.images.load(str(fn))
                            node.image = img
                    elif node.type=='GROUP':
                        node.inputs['Name Color'].default_value = name_color
                        node.inputs['Number Color'].default_value = number_color

    def make_number_and_name(self, nbr, name):
        if nbr is None:
            nbr = ''
        if name is None:
            name = ''
        if not 'Number Gen' in bpy.data.scenes:
            fn = self.root / 'Templates' / 'Number and Names Generator_001.blend'
            with bpy.data.libraries.load(str(fn)) as (data_from, data_to):
                data_to.scenes = data_from.scenes

        ofn = self.root / 'cache' / 'number' / f'{nbr}.png'
        ofn.parent.mkdir(parents=True, exist_ok=True)
        if not ofn.exists():
            scene = bpy.data.scenes['Number Gen']
            text = [o for o in scene.objects if o.type == 'FONT'][0]
            text.data.body = str(nbr)
            text.data.size = 0.8
            scene.render.filepath = str(ofn)
            scene.render.engine = "CYCLES"
            scene.cycles.samples = 1
            bpy.ops.render.render(scene='Number Gen', write_still=True)
        img_num = bpy.data.images.load(str(ofn))

        ofn = self.root / 'cache' / 'name' / f'{name}.png'
        ofn.parent.mkdir(parents=True, exist_ok=True)
        if not ofn.exists():
            scene = bpy.data.scenes['Text Gen']
            text = [o for o in scene.objects if o.type == 'FONT'][0]
            text.data.body = name
            text.data.size = 8 / (len(name) + 1e-2)
            scene.render.filepath = str(ofn)
            scene.render.engine = "CYCLES"
            scene.cycles.samples = 1
            bpy.ops.render.render(scene='Text Gen', write_still=True)
        img_name = bpy.data.images.load(str(ofn))

        return img_num, img_name


class GenerateSoccerClothesTeam(GenerateSoccerClothes):
    """
        Generate soccer uniform cloths for BEDLAM characters for an entire team
        of players. Which team is selected randomly once by calling the
        `select_uniform()` method. Then the same uniform is applied to all
        players.
    """
    def __init__(self, context, kind='Home', player_type='Player'):
        super().__init__(context)
        self.kind = kind
        self.player_type = player_type
        del self.uniforms['Referee']

    def select_uniform(self):
        self.clothes_names = [choice(alt) for alt in self.alternatives]
        self.uniform = choice(list(self.uniforms.values()))[self.kind][self.player_type]

    def create(self, obj, animation_fn, animation_offset, step_size, height_offset):
        self.apply_clothes(obj, self.clothes_names, self.uniform, np.random.randint(1, 99), choice(self.names))
        obj['blenderset.team_type'] = self.kind
        obj['blenderset.player_type'] = self.player_type

class GenerateSoccerClothesReferee(GenerateSoccerClothes):
    """
       Generate soccer referee cloths for BEDLAM characters.
    """
    def __init__(self, context):
        super().__init__(context)
        self.uniforms = self.uniforms['Referee']
        self.alternatives[0] = ['Shorts_Long']
        self.alternatives[3] = ['Tshirt_Referee']

    def select_uniform(self):
        self.clothes_names = [choice(alt) for alt in self.alternatives]
        self.uniform = choice(list(self.uniforms.values()))['Referee']

    def create(self, obj, animation_fn, animation_offset, step_size, height_offset):
        self.apply_clothes(obj, self.clothes_names, self.uniform, None, None)
        obj['blenderset.player_type'] = 'Referee'

class Positioner:
    "Helper to position objects acording to different distributions."
    def random_position(self, roi, max_dist=2):
        raise NotImplementedError

class ExtendedRectanglePositioner(Positioner):
    "Position objects uniformly witin or atmost `max_dist` units away from the rectange `roi`."
    def random_position(self, roi, max_dist=2):
        min_x, min_y, max_x, max_y = roi.bounds
        x = np.random.uniform(min_x - max_dist, max_x + max_dist)
        y = np.random.uniform(min_y - max_dist, max_y + max_dist)
        return x, y

class RightOutsidePositioner(Positioner):
    "Position objects uniformly 0 - `max_dist` units away from the rectange `roi`."
    def random_position(self, roi, max_dist=2):
        min_x, min_y, max_x, max_y = roi.bounds
        offset = np.random.uniform(0, max_dist)
        if choice(['x', 'x', 'y']) == 'x':
            x = choice([min_x - offset, max_x + offset])
            y = np.random.uniform(min_y, max_y)
        else:
            x = np.random.uniform(min_x, max_x)
            y = choice([min_y - offset, max_y + offset])
        return x, y

class CloseToCommonPositioner(Positioner):
    "Position objects gaussian distributed with standard deviation `std` around a common position but still within `roi`."
    def __init__(self, std) -> None:
        self.std = std
        self.reset_common_position()

    def reset_common_position(self):
        self.common_pos = None

    def choose_common_position(self, roi):
        min_x, min_y, max_x, max_y = roi.bounds
        return np.random.uniform(min_x, max_x), np.random.uniform(min_y, max_y)

    def random_position(self, roi):
        if self.common_pos is None:
            self.common_pos = self.choose_common_position(roi)
        x, y = self.common_pos
        while True:
            random_point = Point([x + np.random.normal(0, self.std), y + np.random.normal(0, self.std)])
            if random_point.within(roi):
                return random_point.x, random_point.y

class CloseToLeftGoalPositioner(CloseToCommonPositioner):
    def choose_common_position(self, roi):
        min_x, min_y, max_x, max_y = roi.bounds
        return 0, max_y

class CloseToRightGoalPositioner(CloseToCommonPositioner):
    def choose_common_position(self, roi):
        min_x, min_y, max_x, max_y = roi.bounds
        return 0, min_y

class CloseToCloseSidePositioner(CloseToCommonPositioner):
    def choose_common_position(self, roi):
        min_x, min_y, max_x, max_y = roi.bounds
        return min_x, np.random.uniform(min_y, max_y)

class CloseToFarSidePositioner(CloseToCommonPositioner):
    def choose_common_position(self, roi):
        min_x, min_y, max_x, max_y = roi.bounds
        return max_x, np.random.uniform(min_y, max_y)

class GenerateSoccerTeams(ComposedAssetGenerator):
    """
        Generates two soccer teams with golies and referees.
    """
    def __init__(self, context, nbr_of_players=10):
        self.nbr_of_players = nbr_of_players
        super().__init__(context)

    def setup(self):
        close_to_ball = CloseToCommonPositioner(10)
        close_to_left = CloseToLeftGoalPositioner(2)
        close_to_right = CloseToRightGoalPositioner(2)
        close_to_far = CloseToFarSidePositioner(1)
        close_to_close = CloseToCloseSidePositioner(1)

        goal_positioners = [close_to_left, close_to_right]
        shuffle(goal_positioners)
        self.positioners = goal_positioners + [close_to_ball, close_to_far, close_to_close]
        self.referee_clothes = GenerateSoccerClothesReferee(self.context)
        return [
            GenerateBedlam(self.context, GenerateSoccerClothesTeam(self.context, 'Home', 'Player'), nbr_of_bedlams=self.nbr_of_players, positioner=close_to_ball),
            GenerateBedlam(self.context, GenerateSoccerClothesTeam(self.context, 'Home', 'Goalkeeper'), nbr_of_bedlams=1, positioner=goal_positioners[0]),
            GenerateBedlam(self.context, GenerateSoccerClothesTeam(self.context, 'Away', 'Player'), nbr_of_bedlams=self.nbr_of_players, positioner=close_to_ball),
            GenerateBedlam(self.context, GenerateSoccerClothesTeam(self.context, 'Away', 'Goalkeeper'), nbr_of_bedlams=1, positioner=goal_positioners[1]),
            GenerateBedlam(self.context, self.referee_clothes, nbr_of_bedlams=1, positioner=close_to_far),
            GenerateBedlam(self.context, self.referee_clothes, nbr_of_bedlams=1, positioner=close_to_close),
            GenerateBedlam(self.context, self.referee_clothes, nbr_of_bedlams=1, positioner=close_to_ball),
        ]

    def create(self):
        for gen in self.generators:
            gen.cloth_generator.select_uniform()
        self.referee_clothes.select_uniform()
        super().create()

    def update(self):
        for poser in self.positioners:
            poser.reset_common_position()
        return super().update()


class BedlamCreateSoccerScene(bpy.types.Operator):
    bl_idname = "blenderset.bedlam_create_soccer_scene"
    bl_label = "Create SoccerScene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        SoccerScene(context).create()
        return {"FINISHED"}

class SoccerScene(ComposedAssetGenerator):
    def __init__(self, context, nbr_of_bedlams=1, nbr_of_players=1):
        self.nbr_of_bedlams = nbr_of_bedlams
        self.nbr_of_players = nbr_of_players
        super().__init__(context)

    def setup(self):
        return [
            GeneratePremadeBackground(
                self.context,
                # Path("/home/hakan/src/dev-scripts/allsvenskan/").glob("*/background_mix.blend"),
                (self.root / "soccer_backgrounds").glob('*.blend'),
            ),
            GenerateHdrDoomLight(self.context),
            GenerateBedlam(self.context, GenerateSoccerClothes(self.context), nbr_of_bedlams=self.nbr_of_players, positioner=ExtendedRectanglePositioner()),
            GenerateBedlam(self.context, GenerateBedlamClothes(self.context), nbr_of_bedlams=self.nbr_of_bedlams, positioner=ExtendedRectanglePositioner()),
        ]

class SoccerSceneInPlay(ComposedAssetGenerator):
    def __init__(self, context, nbr_of_players=10, nbr_of_bystanders=4):
        self.nbr_of_players = nbr_of_players
        self.nbr_of_bystanders = nbr_of_bystanders
        super().__init__(context)

    def setup(self):
        return [
            GeneratePremadeBackground(
                self.context,
                # Path("/home/hakan/src/dev-scripts/allsvenskan/").glob("*/background_mix.blend"),
                (self.root / "soccer_backgrounds").glob('*.blend'),
            ),
            GenerateHdrDoomLight(self.context),
            GenerateSoccerTeams(self.context, nbr_of_players=self.nbr_of_players),
            GenerateBedlam(self.context, GenerateBedlamClothes(self.context), nbr_of_bedlams=self.nbr_of_bystanders, positioner=RightOutsidePositioner()),
        ]
