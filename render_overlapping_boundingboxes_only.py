from __future__ import annotations

import dataclasses
import datetime
import itertools
import json
import os
import pathlib
import shutil
from pathlib import Path
from typing import Generic, TypeVar

import math
import more_itertools

import bpy
from blenderset.render import PreviewRenderer, Renderer
from blenderset.scenarios import Nyhamnen, DelfinenSynthBack, DelfinenRealBack

num_scene = 100
num_permutation = 100

run_start = datetime.datetime.now()
run_name = run_start.strftime("%Y%m%d_%H%M%S")
NumberT = TypeVar("NumberT", float, int)


@dataclasses.dataclass(frozen=True)
class Point2D(Generic[NumberT]):
    """An exact location in two dimensional space"""

    x: NumberT
    y: NumberT

    def __add__(self, other):
        if self.__class__ is not other.__class__:
            raise TypeError

        return self.__class__(x=self.x + other.x, y=self.x + other.x)

    def is_close(self, other: Point2D, **kwargs) -> bool:
        """Return true iff two points are approximately equal"""
        return math.isclose(self.x, other.x, **kwargs) and math.isclose(
            self.y, other.y, **kwargs
        )


@dataclasses.dataclass(frozen=True)
class Rectangle(Generic[NumberT]):
    """An equiangular quadrilateral

    Uses a y-axis that points downwards.
    """

    position: Point2D[NumberT]
    size: Point2D[NumberT]

    @classmethod
    def from_ltrb(cls, left: NumberT, top: NumberT, right: NumberT, bottom: NumberT):
        """Return a Rectangle from left, top, right, bottom coordinates"""
        return cls(
            position=Point2D(x=left, y=top),
            size=Point2D(x=right - left, y=bottom - top),
        )

    @property
    def left(self):
        """Return lowest x-coordinate contained in rectangle"""
        return self.position.x

    @property
    def top(self):
        """Return lowest y-coordinate contained in rectangle"""
        return self.position.y

    @property
    def right(self):
        """Return highest x-coordinate contained in rectangle"""
        return self.position.x + self.size.x

    @property
    def bottom(self):
        """Return highest y-coordinate contained in rectangle"""
        return self.position.y + self.size.y

    @property
    def start(self):
        """Return top left corner of rectangle"""
        return self.position

    @property
    def end(self):
        """Return bottom right corner of rectangle"""
        return self.position + self.size

    @property
    def area(self) -> NumberT:
        """Return area of rectangle"""
        return self.size.x * self.size.y

    def intersection(self, other: Rectangle):
        """Return the largest rectangle contained by two rectangles"""
        # Comparison between relative and absolute roi is not meaningful
        if self.__class__ is not other.__class__:
            raise TypeError

        top = max(self.top, other.top)
        right = min(self.right, other.right)
        left = max(self.left, other.left)
        bottom = min(self.bottom, other.bottom)
        if left < right and top < bottom:
            return type(self).from_ltrb(left, top, right, bottom)
        return None

    def is_close(self, other: Rectangle, **kwargs) -> bool:
        """Return True iff two rectangles are approximately equal"""
        method_1 = self.position.is_close(
            other.position, **kwargs
        ) and self.size.is_close(other.size, **kwargs)
        method_2 = (
            math.isclose(self.left, other.left, **kwargs)
            and math.isclose(self.top, other.top, **kwargs)
            and math.isclose(self.right, other.right, **kwargs)
            and math.isclose(self.bottom, other.bottom, **kwargs)
        )
        # I think these will sometimes be different but I defer the decision of which
        # method is more correct until we encounter an example.
        assert method_1 == method_2
        return method_1


def should_render_final(preview_path: pathlib.Path):
    objects = json.load(open(preview_path / "objects.json"))
    boxes = [
        obj["bounding_box_tight"]
        for obj in objects.values()
        if obj["class"] in {"car", "human"}
    ]
    rectangles = [Rectangle.from_ltrb(u0, v0, u1, v1) for u0, u1, v0, v1 in boxes]
    return any(l.intersection(r) for l, r in more_itertools.pairwise(rectangles))


def main(name: str):
    clss = {
        "DelfinenSynthBack": DelfinenSynthBack,
        "DelfinenRealBack": DelfinenRealBack,
        "Nyhamnen": Nyhamnen,
    }
    roots = {
        "DelfinenSynthBack": Path("renders/delfinen_realback"),
        "DelfinenRealBack": Path("renders/delfinen_realback"),
        "Nyhamnen": Path("renders/nyhamnen"),
    }

    root = roots[name]
    cls = clss[name]

    preview_renderer = PreviewRenderer(bpy.context, root)
    final_renderer = Renderer(bpy.context, root)
    preview_only = os.environ.get("BLENDERSET_PREVIEW", "0") == "1"

    for scene_num in range(num_scene):
        bpy.ops.wm.open_mainfile(filepath="blank.blend")
        num_character = (scene_num + 10) % 30
        gen = cls(bpy.context, num_character)
        gen.create()
        perm_num = 0
        attempt_nums = itertools.count()
        while perm_num < num_permutation:
            attempt_num = next(attempt_nums)
            stem = f"{run_name}_{scene_num:03}_{perm_num:03}_{attempt_num:04}"
            name = f"{stem}"
            path = preview_renderer.render(name)
            if should_render_final(path):
                perm_num += 1
                if preview_only:
                    path.rename(path.with_suffix(".preview"))
                else:
                    final_renderer.render(path.with_suffix(".final").name)

            if not preview_only and path.exists():
                shutil.rmtree(path)

            gen.update()


if __name__ == "__main__":
    main(
        # name="DelfinenRealBack"
        name="Nyhamnen"
    )
