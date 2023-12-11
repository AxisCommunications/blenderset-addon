import json
from pathlib import Path
from shapely.geometry import MultiPolygon, Polygon, Point
import numpy as np

import bpy


class AssetGenerator:
    def __init__(self, context):
        self.context = context
        self.created_objects = []
        self.bvh_tree_cache = {}

        config_file = Path.home() / '.config' / 'blenderset' / 'config.json'
        if config_file.exists():
            self.config = json.load(config_file.open())
        else:
            self.config = {}
        if 'assets_dir' in self.config:
            self.root = Path(self.config.get('assets_dir'))
        else:
            self.root = Path.cwd() / '..' / 'blenderset-assets'
        if 'metadata_dir' in self.config:
            self.metadata_dir = Path(self.config.get('metadata_dir'))
        else:
            self.metadata_dir = Path.cwd() / '..' / 'blenderset-metadata'
        if not self.root.exists():
            raise IOError('Cant find assets in ' + str(self.root))
        if not self.metadata_dir.exists():
            raise IOError('Cant find metadata in ' + str(self.metadata_dir))

    def setup_render(self):
        pass

    def create(self):
        raise NotImplementedError

    def update_object(self, obj):
        raise NotImplementedError

    def update(self):
        for obj in self.created_objects:
            self.update_object(obj)

    def update_all(self):
        for obj in bpy.data.objects:
            if "blenderset.creator_class" in obj:
                if obj["blenderset.creator_class"] == self.__class__.__name__:
                    self.update_object(obj)

    def claim_object(self, obj):
        obj["blenderset.creator_class"] = self.__class__.__name__
        self.created_objects.append(obj)

    def get_object_meshes(self, obj):
        object_meshes = set(o for o in obj.children_recursive if o.type == "MESH")
        other_meshes = [
            o
            for o in self.context.scene.objects
            if o not in object_meshes
            and o.type == "MESH"
            and o.get("blenderset.object_class") != "ground_plane"
        ]
        return object_meshes, other_meshes

    def get_all_proprty_values(self, name, cast=None):
        assert not name.endswith(".")
        values = []
        for obj in bpy.data.objects:
            for n in obj.keys():
                if n == name or n.startswith(name + "."):
                    v = obj[n]
                    if cast is not None:
                        v = cast(v)
                    values.append(v)
        return values

    def get_all_objects_of_class(self, class_name):
        objs = []
        for obj in bpy.data.objects:
            if obj.get("blenderset.object_class") == class_name:
                objs.append(obj)
        return objs

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



class ComposedAssetGenerator(AssetGenerator):
    def __init__(self, context):
        super().__init__(context)
        self.generators = self.setup()

    def setup_render(self):
        for gen in self.generators:
            gen.setup_render()

    def create(self):
        for gen in self.generators:
            gen.create()

    def update(self):
        for gen in self.generators:
            gen.update()

    def update_all(self):
        for gen in self.generators:
            gen.update_all()

    def setup(self):
        raise NotImplementedError


class AssetGenerationFailed(Exception):
    pass
