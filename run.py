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
    ConstructionRealBack,
    ForestRoad,
    Nyhamnen,
    DelfinenSynthBack,
    DelfinenRealBack,
    RealHighway,
)


def main():
    # root = Path('renders/nyhamnen')
    #     root = Path("renders/delfinen_realback")
    # root = Path("renders/construction_realback")
    # root = Path("renders/forest_road2")
    root = Path("renders/real_highway")

    # renderer = PreviewRenderer(bpy.context, root)
    renderer = Renderer(bpy.context, root)

    run_start = datetime.datetime.now()
    run_name = os.environ.get(
        "BLENDERSET_RUN_NAME", run_start.strftime("%Y%m%d_%H%M%S") + "_" + gethostname()
    )
    random.seed(run_name)
    np.random.seed(random.randrange(0, 2 ** 32))

    for scene_num in range(1000):
        bpy.ops.wm.open_mainfile(filepath="blank.blend")
        # gen = Nyhamnen(bpy.context, randint(20, 200), test_set=True)
        # gen = DelfinenSynthBack(bpy.context, 2)
        # gen = DelfinenRealBack(bpy.context, randint(10, 30))
        # gen = ConstructionRealBack(bpy.context, randint(3, 6))
        # gen = ForestRoad(bpy.context, randint(10, 20))
        gen = RealHighway(bpy.context, randint(20, 30))
        gen.create()
        for perm_num in range(10):
            renderer.render(gen, f"{run_name}_{scene_num:03}_{perm_num:03}")
            gen.update()


if __name__ == "__main__":
    configure_logging()
    main()
