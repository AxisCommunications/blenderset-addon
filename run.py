import numpy as np
from blenderset.utils.log import configure_logging

import datetime
import os
import random
from pathlib import Path
from random import randint
from socket import gethostname

import bpy

from blenderset.render import PreviewRenderer, Renderer
from blenderset.scenarios import (
    Nyhamnen,
    RealHighway,
    ProjectiveSyntheticPedestrians,
)
from blenderset.bedlam import SoccerScene


def main():
    root = Path('renders/nyhamnen')
    # root = Path("renders/real_highway")
    # root = Path("renders/ProjectiveSyntheticPedestrians")
    root = Path("renders/SoccerScene")

    renderer = PreviewRenderer(bpy.context, root, save_blend=True)
    # renderer = Renderer(bpy.context, root)

    run_start = datetime.datetime.now()
    run_name = os.environ.get(
        "BLENDERSET_RUN_NAME", run_start.strftime("%Y%m%d_%H%M%S") + "_" + gethostname()
    )
    random.seed(run_name)
    np.random.seed(random.randrange(0, 2 ** 32))

    for scene_num in range(1000):
        bpy.ops.wm.open_mainfile(filepath="blank.blend")
        # gen = Nyhamnen(bpy.context, 3) #randint(20, 200), test_set=True)
        # gen = RealHighway(bpy.context, randint(20, 30))
        # gen = ProjectiveSyntheticPedestrians(bpy.context)
        gen = SoccerScene(bpy.context)
        gen.create()
        for perm_num in range(10):
            renderer.render_all_cameras(gen, f"{run_name}_{scene_num:03}_{perm_num:03}")
            return
            gen.update()


if __name__ == "__main__":
    configure_logging()
    main()
    # os.system('xzgv `ls -trh renders/SoccerScene/*/rgb.png | tail -1`')
    os.system('./build/blender/blender `ls -trh renders/SoccerScene/*/scene.blend | tail -1`')