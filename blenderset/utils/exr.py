import json
import struct
from collections import defaultdict

import Imath
import OpenEXR
import cv2
import bpy
import numpy as np


class ExrFile:
    def __init__(self, filename):
        self.exr = OpenEXR.InputFile(str(filename))
        self.header = self.exr.header()
        dw = self.header["dataWindow"]
        self.shape = (dw.max.y - dw.min.y + 1, dw.max.x - dw.min.x + 1)

    def get_objects(self):
        cryptomatte = defaultdict(dict)
        for k in self.header.keys():
            if k.startswith("cryptomatte/"):
                _, name, key = k.split("/")
                cryptomatte[name][key] = self.header[k]
        head_mask = self.get_head_mask()

        objects = {}
        all_segmentations = []
        for _, crypto in cryptomatte.items():
            root_name = crypto["name"].decode("utf")
            p = root_name + "00.r"
            assert self.header["channels"][p] == Imath.Channel(
                Imath.PixelType(Imath.PixelType.FLOAT), 1, 1
            )
            segmentation = np.frombuffer(self.exr.channel(p), np.uint32).reshape(
                self.shape
            )
            all_segmentations.append(segmentation)

            if len(crypto["manifest"]) > 1:
                data = crypto["manifest"].replace(
                    b'27" screen', b"27 screen"
                )  # Hacky bug workaround
                for name, hexid in json.loads(data).items():
                    obj = {}
                    obj["segmentation_id"] = sid = int(hexid, 16)
                    mask = segmentation == sid
                    vv, uu = np.nonzero(mask)
                    if name not in bpy.data.objects:
                        continue
                    cls = bpy.data.objects[name].get("blenderset.object_class")
                    if len(vv) == 0 or cls is None:
                        continue
                    obj["class"] = cls
                    obj["bounding_box_tight"] = tuple(
                        map(int, (uu.min(), uu.max(), vv.min(), vv.max()))
                    )
                    obj["name"] = name
                    objects[root_name + "/" + name] = obj
                    # Adding the head bounding box using the masks:
                    if cls == "human":
                        combined_mask = np.multiply(mask, head_mask)
                        img = 255 * combined_mask.astype(np.uint8)
                        kernel = np.ones((5, 5), np.uint8)  # 2,2
                        erosion = cv2.erode(img, kernel, iterations=1)
                        dilation = cv2.dilate(erosion, kernel, iterations=1)
                        head_bbox_indexes = np.argwhere(dilation > 0)
                        if head_bbox_indexes.any():
                            head_bbox_min = np.min(head_bbox_indexes, axis=0)
                            head_bbox_max = np.max(head_bbox_indexes, axis=0)
                            obj["bounding_box_head"] = tuple(
                                [
                                    int(head_bbox_min[1]),
                                    int(head_bbox_max[1]),
                                    int(head_bbox_min[0]),
                                    int(head_bbox_max[0]),
                                ]
                            )

        return objects, all_segmentations

    def get_depth_image(self, name="View Layer.Depth.Z"):
        assert self.header["channels"][name] == Imath.Channel(
            Imath.PixelType(Imath.PixelType.FLOAT), 1, 1
        )
        return np.frombuffer(self.exr.channel(name), np.float32).reshape(self.shape).astype(np.float32)

    def get_rgb_image(self, name="View Layer.Combined"):
        img = np.zeros(self.shape + (3,), np.float32)
        for i, ch in enumerate("RGB"):
            p = name + "." + ch
            assert self.header["channels"][p] == Imath.Channel(
                Imath.PixelType(Imath.PixelType.FLOAT), 1, 1
            )
            img[:, :, i] = (
                np.frombuffer(self.exr.channel(p), np.float32)
                .reshape(self.shape)
                .astype(np.float32)
            )
        return img

    def get_head_mask(self):
        p = "View Layer.HeadMask.X"
        if p not in self.header["channels"]:
            return None
        assert self.header["channels"][p] == Imath.Channel(
            Imath.PixelType(Imath.PixelType.FLOAT), 1, 1
        )
        mask = np.frombuffer(self.exr.channel(p), np.float32).reshape(self.shape) > 0
        return mask


def linear_to_srgb(x):
    out = np.empty_like(x)
    msk = x < 0.0031308
    out[msk] = x[msk] * 12.92
    out[~msk] = x[~msk] ** (1 / 2.4) * 1.055 - 0.055
    out = np.round(255 * out)
    out[out < 0] = 0
    out[out > 255] = 255
    print(out.min(), out.max())
    return out.astype(np.uint8)
