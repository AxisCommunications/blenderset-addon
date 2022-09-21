import inspect
import subprocess
import sys

bl_info = {
    "name": "Axis Synthetic Data Generation",
    "blender": (3, 0, 0),
    "category": "SyntheticData",
}


def _get_classes():
    import bpy
    from .background import (
        BackgroundPanel,
        Background,
        SelectionToRoi,
        SyntheticBackground,
    )
    from .vehicle import VehiclePanel, VehicleCreate, VehicleUpdate
    from .character import CharacterPanel, CharacterCreate, CharacterUpdate
    from .light import LightCreate, LightPanel
    from .scenarios import Scenario, ScenarioPanel

    return [
        cls
        for cls in locals().values()
        if inspect.isclass(cls)
        and issubclass(cls, (bpy.types.Panel, bpy.types.Operator))
    ]


def register():
    import bpy

    for cls in _get_classes():
        bpy.utils.register_class(cls)


def unregister():
    import bpy

    for cls in _get_classes():
        bpy.utils.unregister_class(cls)
