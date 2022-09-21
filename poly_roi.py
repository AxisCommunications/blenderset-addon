import json
import os
from itertools import repeat
from tempfile import TemporaryDirectory

import click
import cv2
import pyglet
from vi3o import Video
from vi3o.debugview import DebugViewer
from vi3o.image import imread, imwrite, imscale
import numpy as np
from pyglet.window import key as keysym
from vi3o.netcam import AxisCam


def print_roi_query(rois):
    strs = []
    for i, roi in enumerate(rois):
        strs.append(
            "roi%d=%dx%d:%s"
            % (i + 1, roi["image_width"], roi["image_height"], ",".join(str(v) for v in sum(roi["poly"], [])))
        )
    print("&".join(strs))


def draw_poly(drw, poly, color, nbr, name=None):
    cv2.polylines(drw, np.array([poly], np.int32), True, color, 3)
    label = str(nbr)
    if name:
        label += ": " + name
    cv2.putText(drw, label, tuple(map(int, np.mean(poly, 0))), cv2.FONT_HERSHEY_SIMPLEX, 2, color, 4, cv2.LINE_AA)


def mask_poly(msk, poly, nbr):
    if len(poly) > 2:
        cv2.fillPoly(msk, np.array([poly], np.int32), nbr)


def save_roi(roi_file, other_roi, this_roi):
    if len(this_roi["poly"]) > 2:
        all_roi = other_roi + [this_roi]
    else:
        all_roi = other_roi
    if roi_file is not None:
        with open(roi_file, "w") as fd:
            json.dump(all_roi, fd, indent=4, sort_keys=True)
        print_roi_query(all_roi)


@click.command(help="Specify region of interest as polygons")
@click.option("-f", "--file", "file_path", type=click.File("rb"))
@click.option("--uri", default=None)
@click.option("-u", "--user", default="root")
@click.option("-p", "--password", default="pass")
@click.option("--roi-file", default=None)
@click.option("--crowdcam", default=None)
@click.option("--top", is_flag=True, default=False, help="Only use top half of image")
def poly_roi(file_path, uri, user, password, roi_file, crowdcam, top):
    if crowdcam:
        uri = crowdcam
    if not (file_path or uri):
        raise ValueError("Must specify either --file or --uri or --crowdcam")

    if uri:
        video = AxisCam(uri, no_proxy=True, username=user, password=password)
    else:
        try:
            video = repeat(imread(file_path))
        except OSError:
            video = Video(file_path.name)

    with TemporaryDirectory() as tmpdir:

        if crowdcam:
            os.system("ssh root@%s mkdir /etc/crowdd" % crowdcam)
            os.system("scp root@%s:/etc/crowdd/* %s" % (crowdcam, tmpdir))
            roi_file = os.path.join(tmpdir, "rois.json")

        poly = []
        other_roi = []
        if roi_file is not None:
            if os.path.exists(roi_file):
                other_roi = json.load(open(roi_file))
                print_roi_query(other_roi)

        class Viewer(DebugViewer):
            save_frame = True
            done = False
            selecting = ""
            selected = None

            def on_mouse_motion(self, x, y, dx=None, dy=None):
                x = int((x - self.offset[0] - self.scroll[0]) / self.scale)
                y = self.image.height - int((y - self.offset[1] - self.scroll[1]) / self.scale) - 1
                DebugViewer.mouse_x = min(max(x, 0), width - 1)
                DebugViewer.mouse_y = min(max(y, 0), height - 1)

            def on_mouse_release(self, x, y, button, modifiers):
                if self.clicking:
                    if button == pyglet.window.mouse.LEFT:
                        poly.append([self.mouse_x, self.mouse_y])
                    elif button == pyglet.window.mouse.RIGHT:
                        poly.pop()
                        self.save_frame = True
                    this_roi = {"poly": poly, "image_width": width, "image_height": height}
                    save_roi(roi_file, other_roi, this_roi)

            def on_key_press(self, key, modifiers):
                if key == keysym.BACKSPACE:
                    poly.pop()
                elif key == keysym.ESCAPE:
                    if self.selected is not None or self.selecting:
                        self.selected = None
                        self.selecting = ""
                    else:
                        self.done = True
                elif key in (keysym.PLUS, keysym.NUM_ADD):
                    print(key)
                    if len(poly) > 2:
                        other_roi.append({"poly": poly.copy(), "image_width": width, "image_height": height})
                        poly[:] = []
                elif key == keysym.DELETE and self.selected is not None:
                    del other_roi[self.selected]
                    this_roi = {"poly": poly, "image_width": width, "image_height": height}
                    save_roi(roi_file, other_roi, this_roi)
                    self.selected = None
                    self.selecting = ""
                elif self.selected is None:
                    DebugViewer.on_key_press(self, key, modifiers)

            def on_text(self, char):
                if self.selected is None and char in "0123456789":
                    if self.selected is None:
                        self.selecting += char
                elif char in "\r\n":
                    if self.selecting and self.selected is None:
                        i = int(viewer.selecting)
                        if i < len(other_roi):
                            self.selected = i
                            other_roi[self.selected]["name"] = ""
                        else:
                            self.selected = None
                            self.selecting = ""
                    elif self.selected is not None:
                        self.selected = None
                        self.selecting = ""
                        this_roi = {"poly": poly, "image_width": width, "image_height": height}
                        save_roi(roi_file, other_roi, this_roi)

                elif self.selected is not None:
                    other_roi[self.selected]["name"] += char

        viewer = Viewer()
        while True:
            for img in video:
                img = imscale(img, 0.5)
                if top:
                    h, w = img.shape[:2]
                    img = img[: h // 2]
                if len(img.shape) == 2:
                    img = img[:, :, None]
                    img = np.concatenate([img, img, img], 2)
                height, width, _ = img.shape
                for roi in other_roi:
                    if roi["image_width"] != width or roi["image_height"] != height:
                        wsc = width / roi["image_width"]
                        hsc = height / roi["image_height"]
                        assert wsc == hsc
                        roi["poly"] = [[wsc * x, wsc * y] for x, y in roi["poly"]]
                        roi["image_width"] = width
                        roi["image_height"] = height
                drw = img.copy()
                draw_poly(drw, poly + [(viewer.mouse_x, viewer.mouse_y)], [255, 0, 0], len(other_roi))
                for i, other in enumerate(other_roi):
                    draw_poly(drw, other["poly"], [0, 0, 255], i, other.get("name", ""))

                if viewer.selected is not None:
                    draw_poly(
                        drw,
                        other_roi[viewer.selected]["poly"],
                        [0, 255, 0],
                        viewer.selected,
                        other_roi[viewer.selected].get("name", ""),
                    )
                cv2.putText(drw, viewer.selecting, (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 4, cv2.LINE_AA)

                msk = np.zeros(img.shape[:2], np.uint8)
                mask_poly(msk, poly + [(viewer.mouse_x, viewer.mouse_y)], len(other_roi))
                for i, other in enumerate(other_roi):
                    mask_poly(msk, other["poly"], i + 1)

                if viewer.done:
                    if roi_file:
                        imwrite(drw, roi_file.replace(".json", "") + "_roi.jpg")
                        imwrite(msk, roi_file.replace(".json", "") + "_mask.png")
                        os.system(
                            "pngtopnm %s | ppmtopgm > %s"
                            % (roi_file.replace(".json", "") + "_mask.png", roi_file.replace(".json", "") + "_mask.pgm")
                        )
                        if crowdcam:
                            os.system(
                                "scp %s/rois_mask.pgm %s/rois.json %s/rois_roi.jpg root@%s:/etc/crowdd/"
                                % (tmpdir, tmpdir, tmpdir, crowdcam)
                            )
                    return

                viewer.view(drw)
                # viewer.view(msk, scale=True)


if __name__ == "__main__":
    poly_roi()
