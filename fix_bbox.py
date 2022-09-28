#!/usr/bin/env python3
import json
import logging
import pathlib
from typing import Union

import fire
import numpy as np
from skimage import measure, morphology
from blenderset.utils.log import configure_logging

logger = logging.getLogger(__name__)


def fix_many(*roots: Union[str, pathlib.Path]):
    """Add tighter bounding box to object files in specified renders"""
    for root in roots:
        logger.info("Fixing %s", root)
        fix_one(root)


def fix_one(root: Union[str, pathlib.Path]):
    root = pathlib.Path(root)
    segment_img = np.load(root / "segmentations.npy")
    segment2label = {v: i for i, v in enumerate(np.unique(segment_img))}

    label_img = np.zeros_like(segment_img)
    for v, i in segment2label.items():
        mask_img = morphology.binary_opening(segment_img == v, np.ones((5,) * 2))
        label_img[mask_img] = i

    props = measure.regionprops(label_img)

    objects_path = root / "objects.json"
    objects = json.loads(objects_path.read_text())

    for obj in objects.values():
        bbox = props[segment2label[obj["segmentation_id"]] - 1].bbox
        obj["bounding_box_tighter"] = bbox[1], bbox[3], bbox[0], bbox[2]
    objects_path.write_text(dumps(objects))


if __name__ == "__main__":
    configure_logging()
    fire.Fire(fix_many)
