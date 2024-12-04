#!/usr/bin/env python3
import collections
import functools
import json
import logging
import pathlib
from typing import Union
import gzip

import cv2
import fire
import numpy as np
from blenderset.utils.log import configure_logging
from skimage import util
from vi3o import debugview
from vi3o.image import imread, ptpscale

from blenderset.utils.lens import create_lens_from_json

logger = logging.getLogger(__name__)


class DebugViewer(debugview.DebugViewer):
    def __init__(self, paths, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paths = collections.deque(paths)
        self._view = "rgb"
        self._render()

    def _render(self):
        path = self._paths[0]
        logger.info("Showing %s for %s", self._view, path)
        if self._view == "rgb":
            self.view(_read_rgb_with_overlay(path), pause=True)
        elif self._view == "seg":
            self.view(_read_seg(path), pause=True)
        elif self._view == "hmask":
            self.view(_read_hmask(path), pause=True)
        elif self._view == "depth":
            self.view(_read_depth(path), pause=True)
        else:
            assert False

    def on_key_press(self, key, modifiers):
        if key == debugview.keysym.N:
            self._paths.rotate(-1)
        elif key == debugview.keysym.P:
            self._paths.rotate(1)
        elif key == debugview.keysym.R:
            self._view = "rgb"
        elif key == debugview.keysym.S:
            self._view = "seg"
        elif key == debugview.keysym.H:
            self._view = "hmask"
        elif key == debugview.keysym.D:
            self._view = "depth"
        else:
            super().on_key_press(key, modifiers)
        self._render()


@functools.lru_cache(maxsize=2)
def _read_seg(path: pathlib.Path):
    if (path / "segmentations.npy").exists():
        segmentations = np.load(path / "segmentations.npy")
    else:
        with gzip.GzipFile(path / "segmentations.npy.gz", "r") as fd:
            segmentations = np.load(fd)
    return util.img_as_ubyte(segmentations)

@functools.lru_cache(maxsize=2)
def _read_hmask(path: pathlib.Path):
    return imread(path / "head_mask.png")

@functools.lru_cache(maxsize=2)
def _read_depth(path: pathlib.Path):
    if (path / "depth.npy").exists():
        depth = np.load(path / "depth.npy")
    else:
        with gzip.GzipFile(path / "depth.npy.gz", "r") as fd:
            depth = np.load(fd)
    depth[depth>50] = 50
    return ptpscale(depth)


@functools.lru_cache(maxsize=2)
def _read_rgb_with_overlay(path: pathlib.Path):
    if (path / "rgb.png").exists():
        img = imread(path / "rgb.png")
    else:
        img = imread(path / "rgb.jpg")
    objects = json.load(open(path / "objects.json"))

    lens = create_lens_from_json(img.shape, path / "lens.json")
    camera_matrix = np.load(path / "camera_matrix.npy")

    for obj in objects.values():
        for key in ["bounding_box_tighter", "bounding_box_tight"]:
            if key in obj:
                bbox = obj[key]
                break
        else:
            assert False
        u0, u1, v0, v1 = bbox
        if obj["class"] == "human":
            cv2.rectangle(img, (u0, v0), (u1, v1), (255, 0, 0), 1)
            try:
                u2, u3, v2, v3 = obj["bounding_box_head"]
                cv2.rectangle(img, (u2, v2), (u3, v3), (0, 255, 255), 1)
            except KeyError:
                pass
        elif obj["class"] == "construction_hat":
            cv2.rectangle(img, (u0, v0), (u1, v1), (255, 255, 51), 1)
        elif obj["class"] == "vehicle":
            cv2.rectangle(img, (u0, v0), (u1, v1), (0, 255, 0), 1)
        else:
            cv2.rectangle(img, (u0, v0), (u1, v1), (0, 0, 255), 1)

        if "head_center_img" in obj["keypoints"]:
            u0, v0 = obj["keypoints"]["head_center_img"]
            u1, v1 = obj["keypoints"]["left_foot_img"]
            u2, v2 = obj["keypoints"]["right_foot_img"]
            u = (u0 + u1 / 2 + u2 / 2) / 2
            v = (v0 + v1 / 2 + v2 / 2) / 2
            cv2.line(img, (int(u), int(v)), (int(u0), int(v0)), (0, 255, 0), 1)
            cv2.line(img, (int(u), int(v)), (int(u1), int(v1)), (0, 255, 0), 1)
            cv2.line(img, (int(u), int(v)), (int(u2), int(v2)), (0, 255, 0), 1)

            for n in ["head_center", "left_foot", "right_foot"]:
                x, y, z = obj["keypoints"][n]
                x, y, z, _ = camera_matrix @ (x, y, z, 1)
                u, v = lens.world_to_image([x, y, z])[0]
                cv2.circle(img, (int(u), int(v)), 4, (0, 0, 255), 1)

        if 'bounding_3d' in obj:
            wpkt = np.column_stack([obj['bounding_3d'], np.ones(len(obj['bounding_3d']))]) @ camera_matrix.T
            ipkt = lens.world_to_image(wpkt[:,:3]).astype(int)
            for i, j in box_lines:
                cv2.line(img, ipkt[i], ipkt[j], (255,255,0), 1)
    return img

box_lines = [
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
]

def show_many(*paths: Union[str, pathlib.Path]):
    DebugViewer([pathlib.Path(path) for path in paths])


if __name__ == "__main__":
    configure_logging()
    fire.Fire(show_many)
