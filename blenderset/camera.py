from random import choice, uniform
from blenderset.assets import AssetGenerator
import bpy
import shapely
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid

from blenderset.utils.lens import (
    LensDist,
    LensDistM3057,
    create_perspective_lens,
    rotmat_xyz,
    create_lens_from_json,
)
from .utils.debug import show_points, show_poly


def get_current_camera():
    camera = bpy.context.scene.camera

    if hasattr(camera.data, "fisheye_polynomial_k0"):  # Blender 4
        data_cycles = camera.data
    else:
        data_cycles = camera.data.cycles
    class MyLens(LensDist):
        dist_poly = (
            np.array(
                [
                    data_cycles.fisheye_polynomial_k0,
                    data_cycles.fisheye_polynomial_k1,
                    data_cycles.fisheye_polynomial_k2,
                    data_cycles.fisheye_polynomial_k3,
                    data_cycles.fisheye_polynomial_k4,
                ]
            )
            * 180
            / np.pi
        )
        sensor_width = camera.data.sensor_width
        pixel_width = 1

    lens = MyLens(
        (
            bpy.context.scene.render.resolution_y,
            bpy.context.scene.render.resolution_x,
            3,
        ),
        1,
    )
    camera_matrix = np.array(camera.matrix_world.normalized().inverted())
    camera_matrix[0] *= -1
    return camera_matrix, lens


class CameraGenerator(AssetGenerator):
    def __init__(self, context, height_range=(3, 6)):
        super().__init__(context)
        self.height_range = height_range

    def get_camera_height(self):
        heights = set(self.get_all_proprty_values("blenderset.camera_height"))
        if len(heights) == 0:
            return uniform(*self.height_range)
        elif len(heights) == 1:
            return heights.pop()
        else:
            raise ValueError(
                "Multiple Backgrounds assuming different camera heights detected."
            )

    def create_camera_object(self, lens):
        camera_data = bpy.data.cameras.new(name="Camera")
        camera_object = bpy.data.objects.new("Camera", camera_data)
        collection = self.context.view_layer.active_layer_collection.collection
        collection.objects.link(camera_object)

        if hasattr(camera_object.data, "fisheye_polynomial_k0"):  # Blender 4
            data_cycles = camera_object.data
        else:
            data_cycles = camera_object.data.cycles

        camera_object.data.type = "PANO"
        data_cycles.panorama_type = 'FISHEYE_LENS_POLYNOMIAL'
        camera_object.data.sensor_fit = "HORIZONTAL"
        self.context.scene.render.engine = "CYCLES"

        camera_object.data.sensor_width = lens.sensor_width * lens.pixel_width
        data_cycles.fisheye_polynomial_k0 = np.radians(lens.dist_poly[0])
        data_cycles.fisheye_polynomial_k1 = np.radians(lens.dist_poly[1])
        data_cycles.fisheye_polynomial_k2 = np.radians(lens.dist_poly[2])
        data_cycles.fisheye_polynomial_k3 = np.radians(lens.dist_poly[3])
        data_cycles.fisheye_polynomial_k4 = np.radians(lens.dist_poly[4])
        if lens.nominal_homography is not None:
            projection = np.eye(4)
            projection[:3, :3] = lens.nominal_homography.T
            camera_object.matrix_world = projection

        camera_object.location[2] = self.get_camera_height()
        self.context.scene.render.resolution_x = lens.width
        self.context.scene.render.resolution_y = lens.height

        self.context.scene.camera = camera_object

        self.claim_object(camera_object)
        self.camera_object = camera_object
        return camera_object

    def clear_visible_walkable_roi(self, camera_object):
        for key in camera_object.keys():
            if key.startswith("blenderset.visible_walkable_roi"):
                del camera_object[key]

    def update_object(self, camera_object):
        self.clear_visible_walkable_roi(camera_object)
        for i, roi in enumerate(self.get_all_proprty_values("blenderset.walkable_roi")):
            camera_object[f"blenderset.visible_walkable_roi.{i}"] = roi


class GenerateCameraFromBackground(CameraGenerator):
    def __init__(self, context, background_generator):
        super().__init__(context)
        self.background_generator = background_generator

    def create(self):
        lens = self.background_generator.lens
        h = self.background_generator.height
        self.height_range = (h, h)
        if lens is None:
            raise ValueError("Create a background first to specify a camera lens")
        self.create_camera_object(lens)
        self.update()


class GenerateCameraFromJson(CameraGenerator):
    def __init__(self, context, shape, json_file, height_range=(3, 6)):
        super().__init__(context, height_range)
        self.lens = create_lens_from_json(shape, json_file)

    def create(self):
        self.create_camera_object(self.lens)
        self.update()

    def update_object(self, camera_object):
        height = self.get_camera_height()
        self.camera_object.location[2] = height
        super().update_object(camera_object)


class GenerateAxisM3057Camera(CameraGenerator):
    def create(self):
        shape = (2048, 2048, 3)
        lens = LensDistM3057(shape)
        self.create_camera_object(lens)
        self.update()

    def update_object(self, camera_object):
        height = self.get_camera_height()
        self.camera_object.location[2] = height
        super().update_object(camera_object)


class GenerateProjectiveCamera(CameraGenerator):
    def fisheye_lens_polynomial_from_projective(
        self, focal_length=50, sensor_width=36, sensor_height=None
    ):
        rr = self.create_grid(sensor_height, sensor_width)
        polynomial = np.polyfit(rr.flat, (-np.arctan(rr / focal_length)).flat, 4)
        return list(reversed(polynomial))

    def create(self):
        # Creating the perspective lens
        output_shape = (576, 1024)
        sensor_width = 5.328
        pixel_width = sensor_width / output_shape[1]

        persp_lens = create_perspective_lens(
            output_shape, output_shape[1], pixel_width, focal=1.8
        )

        # Distorted -> Projective
        persp_lens.dist_poly = (
            np.array(self.fisheye_lens_polynomial_from_projective(1.8, sensor_width))
            / np.pi
            * 180
        )

        camera_object = self.create_camera_object(persp_lens)

        # Rotation
        tilt_range = np.arange(35, 45, 0.2)
        pan_range = np.arange(-180, 180)
        x: int = np.radians(choice(tilt_range))  # 40 - 55 degrees
        z: int = np.radians(choice(pan_range))  # 0 - 360 degrees
        persp_lens.nominal_homography = rotmat_xyz(x, 0, z)
        projection = np.eye(4)
        projection[:3, :3] = persp_lens.nominal_homography.T
        camera_object.matrix_world = projection
        self.height = self.get_camera_height()
        camera_object.location[2] = self.height

        self.camera_roi = self.image_borders_to_world(persp_lens)
        self.update()

    def create_grid(self, sensor_height, sensor_width):
        if sensor_height is None:
            sensor_height = sensor_width / (16 / 9)  # Default aspect ration 16:9
        uu, vv = np.meshgrid(np.linspace(0, 1, 100), np.linspace(0, 1, 100))
        uu = (uu - 0.5) * sensor_width
        vv = (vv - 0.5) * sensor_height
        rr = np.sqrt(uu ** 2 + vv ** 2)
        return rr

    def image_borders_to_world(self, lens):
        w, h = (
            self.context.scene.render.resolution_x,
            self.context.scene.render.resolution_y,
        )
        u0, v0, u1, v1 = 0, 0, w, h
        roi = np.array(
            [
                [u0, v0],
                [u1, v0],
                [u1, v1],
                [u0, v1],
            ]
        )
        roi[:, 0] = w - roi[:, 0]  # Mirror
        roi_copy = roi
        roi = lens.image_to_world(roi, -self.height)
        roi[:, 2] = 0
        # Making roi that limits character placement with height TODO:nicer implementation
        roi_2 = lens.image_to_world(roi_copy, -self.height + 2)
        roi_2[:, 2] = 0
        camera_roi = Polygon(roi)
        camera_roi_height = Polygon(roi_2)
        camera_roi_res = camera_roi.intersection(camera_roi_height)
        # show_poly(camera_roi_res.exterior.coords)
        return camera_roi_res.exterior.coords

    def get_roi_from_camera(self, roi, camera_object):
        camera_roi = Polygon(roi)

        # Retrieving background roi:s
        walkable_polys = self.get_all_proprty_values("blenderset.walkable_roi")
        polygons_background = MultiPolygon([Polygon(p) for p in walkable_polys])

        # This check i probably not needed anymore since the background rois have been fixed
        if not polygons_background.is_valid:
            polygons_background = make_valid(polygons_background)

        # Intersection
        ret = polygons_background.intersection(camera_roi)

        # Setting walkable roi for the characters for each of the polygons found
        if hasattr(ret, "exterior"):
            ret = [ret]
        else:
            ret = ret.geoms

        for i, poly in enumerate(ret):
            camera_object[f"blenderset.visible_walkable_roi.{i}"] = [
                list(p) for p in poly.exterior.coords
            ]
            # show_poly(poly.exterior.coords)
        return

    def update_object(self, camera_object):
        self.clear_visible_walkable_roi(camera_object)
        self.get_roi_from_camera(self.camera_roi, camera_object)
