import numpy as np
from blenderset.utils.log import configure_logging
import sys

import datetime
import os
import random
from pathlib import Path
from random import randint
from socket import gethostname
from time import time
from filelock import FileLock

np.set_printoptions(threshold=np.inf)

import bpy

from blenderset.render import PreviewRenderer, Renderer
from blenderset.scenarios import (
    Nyhamnen,
    RealHighway,
    ProjectiveSyntheticPedestrians,
)
from blenderset.bedlam import SoccerScene, SoccerSceneInPlay


def main():
    # root = Path('renders/nyhamnen')
    # root = Path("renders/real_highway")
    # root = Path("renders/ProjectiveSyntheticPedestrians")
    # root = Path("renders/SoccerScene")
    root = Path("renders/SoccerCrowd")

    # renderer = PreviewRenderer(bpy.context, root, save_blend=True, save_exr=True)
    renderer = Renderer(bpy.context, root)

    render_lock = FileLock("/tmp/blenderset_render.lock")
    run_start = datetime.datetime.now()
    run_name = os.environ.get(
        "BLENDERSET_RUN_NAME", run_start.strftime("%Y%m%d_%H%M%S") + "_" + gethostname()
    )
    if 'SLURM_JOBID' in os.environ:
        run_name += '_' + os.environ['SLURM_JOBID']
    run_name += "_" + str(os.getpid())
    # run_name = "20231218_135454_hapad"
    random.seed(run_name)
    np.random.seed(random.randrange(0, 2 ** 32))

    timeing = []
    for scene_num in range(1000):
        t0 = time()
        bpy.ops.wm.open_mainfile(filepath="blank.blend")
        # gen = Nyhamnen(bpy.context, 3) #randint(20, 200), test_set=True)
        # gen = RealHighway(bpy.context, randint(20, 30))
        # gen = ProjectiveSyntheticPedestrians(bpy.context)
        gen = SoccerScene(bpy.context, int(sys.argv[-1]), int(sys.argv[-1]))
        # gen = SoccerSceneInPlay(bpy.context)
        t1 = time()
        gen.create()
        t2 = time()
        for perm_num in range(10):
            with render_lock:
                renderer.render_all_cameras(gen, f"{run_name}_{scene_num:03}_{perm_num:03}")
            t3 = time()
            gen.update()
            t4 = time()
            if perm_num == 0:
                timeing.append([t1-t0, t2-t1, t3-t2, t4-t3])
                print('Timing', timeing)



if __name__ == "__main__":
    configure_logging()
    main()
    # os.system('xzgv `ls -trh renders/SoccerScene/*/rgb.png | tail -1`')
    # os.system('./build/blender/blender `ls -trh renders/SoccerScene/*/scene.blend | tail -1`')