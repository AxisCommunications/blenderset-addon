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
import bpy
from blenderset.render import PreviewRenderer, Renderer
from blenderset.assets import ComposedAssetGenerator
from blenderset.background import GeneratePremadeBackground
from blenderset.light import GenerateHdrDoomLight
from blenderset.bedlam import GenerateBedlam, GenerateBedlamClothes, ExtendedRectanglePositioner, NoClothes, GenerateSoccerClothes

np.set_printoptions(threshold=np.inf)

class Scene(ComposedAssetGenerator):
    def setup(self):
        clothes = [GenerateSoccerClothes(self.context), GenerateBedlamClothes(self.context)]
        # clothes = [GenerateSoccerClothes(self.context)]
        # clothes = [GenerateBedlamClothes(self.context)]
        # clothes = [NoClothes(self.context)]
        return [
            GeneratePremadeBackground(
                self.context,
                (self.root / 'multicams').glob('*.blend'),
            ),
            GenerateHdrDoomLight(self.context),

        ] + [
            GenerateBedlam(self.context, c, nbr_of_bedlams=15, positioner=ExtendedRectanglePositioner(), fps=5, nbr_of_frames=15)
            for c in clothes
        ]


def main():
    root = Path("renders/multicam")

    # renderer = PreviewRenderer(bpy.context, root, save_blend=True, save_exr=True, output_format='PNG')
    renderer = Renderer(bpy.context, root, output_format='PNG')

    gpu = os.environ.get('CUDA_VISIBLE_DEVICES', '') + os.environ.get('HIP_VISIBLE_DEVICES', '')
    render_lock = FileLock(f"/tmp/blenderset_render_{gpu}.lock")
    run_start = datetime.datetime.now()
    run_name = os.environ.get(
        "BLENDERSET_RUN_NAME", run_start.strftime("%Y%m%d_%H%M%S") + "_" + gethostname()
    )
    if 'SLURM_JOBID' in os.environ:
        run_name += '_' + os.environ['SLURM_JOBID']
    run_name += "_" + str(os.getpid())
    random.seed(run_name)
    np.random.seed(random.randrange(0, 2 ** 32))

    gen = Scene(bpy.context)
    for scene_num in range(1000):
        bpy.ops.wm.open_mainfile(filepath="blank.blend")
        gen.create()
        with render_lock:
            renderer.render_all_frames(gen, f"{run_name}_{scene_num}")


if __name__ == "__main__":
    configure_logging()
    main()
