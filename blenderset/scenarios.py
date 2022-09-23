from random import choice
from blenderset.camera import (
    GenerateCameraFromBackground,
    GenerateAxisM3057Camera,
)
import inspect
import sys
import importlib.util

import bpy
from shapely.geometry import Point, box, Polygon

from blenderset.assets import ComposedAssetGenerator, AssetGenerator
from blenderset.background import (
    GenerateBackground,
    GenerateBackgroundAndCamera,
    GenerateSyntheticBackground,
    GeneratePremadeBackground,
)
from blenderset.character import GenerateCharacter
from blenderset.light import GenerateHdrDoomLight
from blenderset.vehicle import GenerateVehicleAlongPath
from blenderset.camera import GenerateProjectiveCamera


class Scenario(bpy.types.Operator):
    """Create random background"""

    bl_idname = "blenderset.create_scenario"
    bl_label = "Create Scenario"
    bl_options = {"REGISTER", "UNDO"}

    scenario_name: bpy.props.StringProperty(name="Scenario Name", default="Nyhamnen")

    def execute(self, context):
        gen = globals()[self.scenario_name](context)
        gen.create()
        return {"FINISHED"}


class ScenarioPanel(bpy.types.Panel):
    bl_idname = "AxisOmnisetScenarioPanel"
    bl_label = "Scenarios"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Synthetic"
    # bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        for cls in globals().values():
            if inspect.isclass(cls) and issubclass(cls, ComposedAssetGenerator):
                if cls.__module__ == "blenderset.scenarios":
                    op = self.layout.operator(
                        "blenderset.create_scenario", text=cls.__name__
                    )
                    op.scenario_name = cls.__name__


class Nyhamnen(ComposedAssetGenerator):
    def __init__(self, context, characters=2, test_set=False):
        self.characters = characters
        self.part_tag = "partition:Test1"
        if not test_set:
            self.part_tag = "~" + self.part_tag
        super().__init__(context)

    def setup(self):
        # GenerateCharacter(self.context, self.characters, tags="~age_group:toddler", pose_tags="Standing"),
        return [
            GenerateBackgroundAndCamera(self.context, tags=["Nyhamnen", self.part_tag]),
            GenerateHdrDoomLight(self.context),
            GenerateCharacter(
                self.context,
                self.characters,
                tags=["~age_group:toddler", self.part_tag],
                pose_tags="Standing",
            ),
        ]


class NyhamnenSynthBack(Nyhamnen):
    def setup(self):
        bg = GenerateBackground(self.context, tags="Nyhamnen")
        bg.create_lens(choice(list(bg.background_data.keys())))
        return [
            GenerateCameraFromBackground(self.context, bg),
            GenerateHdrDoomLight(self.context),
            GenerateSyntheticBackground(self.context),
            GenerateCharacter(
                self.context,
                self.characters,
                tags="~age_group:toddler",
                pose_tags="Standing",
                roi=Polygon([(-30, 60), (30, 60), (7, 9), (-7, 9)]),
            ),
        ]

class OfficeRealBack(ComposedAssetGenerator):
    def __init__(self, context, characters=5):
        self.characters = characters
        super().__init__(context)

    def setup(self):
        return [
            GenerateBackground(self.context, tags="Office"),
            GenerateProjectiveCamera(self.context),
            GenerateHdrDoomLight(self.context),
            GenerateCharacter(
                self.context,
                self.characters,
                tags=["~age_group:toddler", "wearing_hard_hat:no"],
                pose_tags="Standing",
            ),
        ]


class FisheyeOffice(ComposedAssetGenerator):
    def __init__(self, context, characters=5):
        self.characters = characters
        super().__init__(context)

    def setup(self):
        # GenerateCharacter(self.context, self.characters, tags="~age_group:toddler", pose_tags="Standing"),
        return [
            GenerateBackgroundAndCamera(self.context, tags=["Office", "M3057"]),
            GenerateHdrDoomLight(self.context),
            GenerateCharacter(
                self.context,
                self.characters,
                tags=["~age_group:toddler"],
                pose_tags="Standing",
            ),
        ]


class FisheyeSynthBack(ComposedAssetGenerator):
    def __init__(self, context, characters=5):
        self.characters = characters
        super().__init__(context)

    def setup(self):
        return [
            GenerateAxisM3057Camera(self.context),
            GenerateHdrDoomLight(self.context),
            GenerateSyntheticBackground(self.context),
            GenerateCharacter(
                self.context,
                self.characters,
                tags="~age_group:toddler",
                pose_tags="Standing",
                roi=Point(0, 0).buffer(6),
            ),
        ]


class RealHighway(ComposedAssetGenerator):
    def __init__(self, context, vehicles=3):
        self.vehicles = vehicles
        super().__init__(context)

    def setup(self):
        return [
            GeneratePremadeBackground(
                self.context,
                "real_highway_background.blend",
            ),
            GenerateVehicleAlongPath(
                self.context,
                self.vehicles,
                tags=[
                    "~type:Boat",
                    "~type:Bicycle",
                    "~type:Plane",
                    "~type:Motorbike",
                    "~type:Tractor",
                    "~type:Formula1",
                    "~model:Train_ETR",
                    "~model:Pesa_2010_n2",
                    "~model:Buggy",
                    "~model:Kenworth W990",
                ],
                delta_x_offsets=(3, 6),
                delta_x_offset_range=(-0.3, 0.3),
                mirror=True,
                offset_range=(0.022, 0.75),
                # offset_range=(0.022, 0.3),
                lowpoly=True,
            ),
        ]


def _append_metadata_scenarios(module):
    source = AssetGenerator(None).metadata_dir / "scenarios.py"
    if source.exists():
        spec = importlib.util.spec_from_file_location("blenderset.scenarios", source)
        scenarios = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scenarios)
        for name in dir(scenarios):
            cls = getattr(scenarios, name)
            if inspect.isclass(cls) and issubclass(cls, ComposedAssetGenerator):
                setattr(module, name, cls)

_append_metadata_scenarios(sys.modules[__name__])