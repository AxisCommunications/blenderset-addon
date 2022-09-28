from __future__ import division, print_function

import json

import numpy as np

# from matplotlib.pyplot import plot, show
# from vi3o import viewsc
# from vi3o.image import imviewsc, imview


def polyfit_noconst(x, y, deg):
    x = np.asarray(x)
    y = np.asarray(y)
    p = np.linalg.lstsq(np.array([x ** i for i in range(1, deg + 1)]).T, y, rcond=None)[
        0
    ]
    return np.hstack([p[::-1], [0]])


class LensDist(object):
    def __init__(
        self,
        shape,
        focal=None,
        homography=None,
        nominal_homography=None,
        dewarped_resolution=None,
        principal=None,
        polar_pixel_transform=None,
    ):
        self.height, self.width, *_ = shape
        self.image_scale = self.sensor_width / self.width
        self.homography = homography
        self.nominal_homography = nominal_homography
        self._ox = self._oy = self._ox_float = self._oy_float = self._mask = None
        self._ox_inv = (
            self._oy_inv
        ) = self._ox_float_inv = self._oy_float_inv = self._mask_inv = None
        self.dewarped_resolution = (
            (shape[1], shape[0]) if dewarped_resolution is None else dewarped_resolution
        )
        self.xoffset = self.yoffset = 0
        self.principal = (
            np.array([self.width / 2, self.height / 2])
            if principal is None
            else principal
        )
        px = self.principal[0]
        self.focal = (
            px / np.tan(self.d2a(px)) if focal is None else focal
        )  # Dewarped focal length
        self.polar_pixel_transform = polar_pixel_transform
        self.polar_pixel_transform_inv = None
        self.sphere_scale_norm_factor = None

    def crop(self, width, height, dx=None, dy=None):
        dx = self.width / 2 - width / 2 if dx is None else dx
        dy = self.height / 2 - height / 2 if dy is None else dy
        self.update((width, height), dx, dy)
        return self

    def dewarped_fov(self, horizontal):
        self.focal = self.dewarped_resolution[0] / 2 / np.tan(horizontal / 2)
        return self


    def polynom_warp(self, poly, poly_inv):
        if len(poly) == len(poly_inv) == 5:

            def trfm(rr, arg):
                rr = (
                    poly[0] * rr ** 4
                    + poly[1] * rr ** 3
                    + poly[2] * rr ** 2
                    + poly[3] * rr
                    + poly[4]
                )
                return rr, arg

            def trfm_inv(rr, arg):
                rr = (
                    poly_inv[0] * rr ** 4
                    + poly_inv[1] * rr ** 3
                    + poly_inv[2] * rr ** 2
                    + poly_inv[3] * rr
                    + poly_inv[4]
                )
                return rr, arg

        elif len(poly) == len(poly_inv) == 7:

            def trfm(rr, arg):
                rr = (
                    poly[0] * rr ** 6
                    + poly[1] * rr ** 5
                    + poly[2] * rr ** 4
                    + poly[3] * rr ** 3
                    + poly[4] * rr ** 2
                    + poly[5] * rr
                    + poly[6]
                )
                return rr, arg

            def trfm_inv(rr, arg):
                rr = (
                    poly_inv[0] * rr ** 6
                    + poly_inv[1] * rr ** 5
                    + poly_inv[2] * rr ** 4
                    + poly_inv[3] * rr ** 3
                    + poly_inv[4] * rr ** 2
                    + poly_inv[5] * rr
                    + poly_inv[6]
                )
                return rr, arg

        elif len(poly) == len(poly_inv) == 9:

            def trfm(rr, arg):
                rr = (
                    poly[0] * rr ** 8
                    + poly[1] * rr ** 7
                    + poly[2] * rr ** 6
                    + poly[3] * rr ** 5
                    + poly[4] * rr ** 4
                    + poly[5] * rr ** 3
                    + poly[6] * rr ** 2
                    + poly[7] * rr
                    + poly[8]
                )
                return rr, arg

            def trfm_inv(rr, arg):
                rr = (
                    poly_inv[0] * rr ** 8
                    + poly_inv[1] * rr ** 7
                    + poly_inv[2] * rr ** 6
                    + poly_inv[3] * rr ** 5
                    + poly_inv[4] * rr ** 4
                    + poly_inv[5] * rr ** 3
                    + poly_inv[6] * rr ** 2
                    + poly_inv[7] * rr
                    + poly_inv[8]
                )
                return rr, arg

        else:
            raise NotImplementedError

        self.polar_pixel_transform = trfm
        self.polar_pixel_transform_inv = trfm_inv

        self._ox = self._oy = None
        return self


    def update(
        self,
        dewarped_resolution=None,
        xoffset=None,
        yoffset=None,
        nominal_homography=None,
    ):
        if dewarped_resolution is not None:
            self.dewarped_resolution = dewarped_resolution
        if xoffset is not None:
            self.xoffset = xoffset
        if yoffset is not None:
            self.yoffset = yoffset
        if nominal_homography is not None:
            self.nominal_homography = nominal_homography
        self._ox = self._oy = self._ox_float = self._oy_float = self._mask = None
        self._ox_inv = (
            self._oy_inv
        ) = self._ox_float_inv = self._oy_float_inv = self._mask_inv = None

    @property
    def ox(self):
        if self._ox is None:
            self._generate_ox_oy()
        return self._ox

    @property
    def oy(self):
        if self._oy is None:
            self._generate_ox_oy()
        return self._oy

    @property
    def ox_float(self):
        if self._ox_float is None:
            self._generate_ox_oy()
        return self._ox_float

    @property
    def oy_float(self):
        if self._oy_float is None:
            self._generate_ox_oy()
        return self._oy_float

    @property
    def mask(self):
        if self._mask is None:
            self._generate_ox_oy()
        return self._mask

    @property
    def ox_inv(self):
        if self._ox_inv is None:
            self._generate_ox_oy_inv()
        return self._ox_inv

    @property
    def oy_inv(self):
        if self._oy_inv is None:
            self._generate_ox_oy_inv()
        return self._oy_inv

    @property
    def ox_float_inv(self):
        if self._ox_float_inv is None:
            self._generate_ox_oy_inv()
        return self._ox_float_inv

    @property
    def oy_float_inv(self):
        if self._oy_float_inv is None:
            self._generate_ox_oy_inv()
        return self._oy_float_inv

    @property
    def mask_inv(self):
        if self._mask_inv is None:
            self._generate_ox_oy_inv()
        return self._mask_inv

    def _generate_ox_oy(self):
        xx, yy = np.meshgrid(
            range(self.dewarped_resolution[0]), range(self.dewarped_resolution[1])
        )
        ox, oy, mask = self._warp_points(xx, yy)
        self._ox_float = np.minimum(np.maximum(ox, 0), self.width - 1).astype(
            np.float32
        )
        self._oy_float = np.minimum(np.maximum(oy, 0), self.height - 1).astype(
            np.float32
        )
        self._ox = self._ox_float.astype(int)
        self._oy = self._oy_float.astype(int)
        self._mask = (
            mask & (ox >= 0) & (oy >= 0) & (ox < self.width) & (oy < self.height)
        )

    def _generate_ox_oy_inv(self):
        xx, yy = np.meshgrid(range(self.width), range(self.height))
        ox, oy, mask = self._dewarp_points(xx, yy)
        self._ox_float_inv = np.minimum(
            np.maximum(ox, 0), self.dewarped_resolution[0] - 1
        ).astype(np.float32)
        self._oy_float_inv = np.minimum(
            np.maximum(oy, 0), self.dewarped_resolution[1] - 1
        ).astype(np.float32)
        self._ox_inv = self._ox_float_inv.astype(int)
        self._oy_inv = self._oy_float_inv.astype(int)
        self._mask_inv = (
            mask
            & (ox >= 0)
            & (oy >= 0)
            & (ox < self.dewarped_resolution[0])
            & (oy < self.dewarped_resolution[1])
        )

    def _warp_points(self, xx, yy):
        xx = xx + self.xoffset
        yy = yy + self.yoffset
        if self.homography is not None:
            pkt = np.array([xx.flat[:], yy.flat[:], np.ones_like(xx.flat)])
            pkt = np.dot(np.linalg.inv(self.homography), pkt)
            pkt = pkt / pkt[2]
            xx = pkt[0].reshape(xx.shape)
            yy = pkt[1].reshape(yy.shape)
        px, py = self.principal
        cx, cy = xx - px, yy - py
        if self.nominal_homography is not None:
            pkt = np.array(
                [
                    cx.flat[:] / self.focal,
                    cy.flat[:] / self.focal,
                    np.ones_like(cx.flat),
                ]
            )
            pkt = np.dot(np.linalg.inv(self.nominal_homography), pkt)
            mask = pkt[2].reshape(cx.shape) > 0
            pkt = pkt / pkt[2]
            cx = pkt[0].reshape(cx.shape) * self.focal
            cy = pkt[1].reshape(cy.shape) * self.focal
        else:
            mask = True
        rr = np.sqrt(cx ** 2 + cy ** 2) / self.focal
        arg = np.arctan2(cy, cx)
        if self.polar_pixel_transform is not None:
            rr, arg = self.polar_pixel_transform(rr, arg)
        rr = self.a2d(np.arctan(rr))
        cx = rr * np.cos(arg)
        cy = rr * np.sin(arg)
        ox, oy = cx + px, cy + py
        return ox, oy, mask

    def _dewarp_points(self, ox, oy):
        px, py = self.principal
        cx, cy = ox - px, oy - py
        rr = np.sqrt(cx ** 2 + cy ** 2)
        arg = np.arctan2(cy, cx)
        rr = np.tan(self.d2a(rr))
        if self.polar_pixel_transform_inv is not None:
            rr, arg = self.polar_pixel_transform_inv(rr, arg)
        else:
            assert self.polar_pixel_transform is None
        rr *= self.focal
        cx = rr * np.cos(arg)
        cy = rr * np.sin(arg)
        if self.nominal_homography is not None:
            pkt = np.array(
                [
                    cx.flat[:] / self.focal,
                    cy.flat[:] / self.focal,
                    np.ones_like(cx.flat),
                ]
            )
            pkt = np.dot(self.nominal_homography, pkt)
            mask = pkt[2].reshape(cx.shape) > 0
            pkt = pkt / pkt[2]
            cx = pkt[0].reshape(cx.shape) * self.focal
            cy = pkt[1].reshape(cy.shape) * self.focal
        else:
            mask = True
        xx, yy = cx + px, cy + py
        assert self.homography is None
        xx = xx - self.xoffset
        yy = yy - self.yoffset
        return xx, yy, mask

    def d2a(self, x):
        x *= self.pixel_width * self.image_scale
        return -sum(k * x ** i for i, k in enumerate(self.dist_poly)) / 180 * np.pi

    def a2d(self, a):
        a0 = -a * 180 / np.pi
        x = (a0 - self.dist_poly[0]) / self.dist_poly[1]
        for i in range(20):
            x = (
                a0 - sum(k * x ** i for i, k in enumerate(self.dist_poly) if i != 1)
            ) / self.dist_poly[1]
        return x / self.pixel_width / self.image_scale

    def dewarp(self, img):
        if len(img.shape) == 3:
            res = img[self.oy, self.ox, :]
        else:
            res = img[self.oy, self.ox]
        return res

    def dewarp_cv(self, img):
        import cv2

        return cv2.remap(
            img,
            self.ox_float,
            self.oy_float,
            cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_DEFAULT,
            borderValue=0,
        )

    def dewarp_points(self, points):
        points = np.atleast_2d(points)
        assert points.shape[1] == 2
        u, v, _ = self._dewarp_points(points[:, 0], points[:, 1])
        return np.array([u, v]).T

    def warp(self, img):
        if len(img.shape) == 3:
            res = img[self.oy_inv, self.ox_inv, :]
        else:
            res = img[self.oy_inv, self.ox_inv]
        return res

    def warp_cv(self, img):
        import cv2

        return cv2.remap(
            img,
            self.ox_float_inv,
            self.oy_float_inv,
            cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_DEFAULT,
            borderValue=0,
        )

    def warp_points(self, image_points):
        image_points = np.atleast_2d(image_points)
        assert image_points.shape[1] == 2
        u, v, _ = self._warp_points(image_points[:, 0], image_points[:, 1])
        return np.array([u, v]).T

    @property
    def K(self):
        px, py = self.principal
        return np.array([[self.focal, 0, px], [0, self.focal, py], [0, 0, 1]])

    def world_to_image(self, world_points):
        world_points = np.atleast_2d(world_points)
        assert world_points.shape[1] == 3
        x, y, z = world_points.T
        image_points = np.array(
            [
                self.focal / z * x + self.principal[0] - self.xoffset,
                self.focal / z * y + self.principal[1] - self.yoffset,
            ]
        ).T
        return self.warp_points(image_points)

    def image_to_world(self, image_points, z):
        image_points = np.atleast_2d(image_points)
        assert image_points.shape[1] == 2
        points = self.dewarp_points(image_points)
        u, v = points.T
        # return np.array([z / self.focal * (u - self.principal[0] + self.xoffset),
        #                  z / self.focal * (v - self.principal[1] + self.yoffset),
        #                  np.atleast_2d(z)]).T
        if len(np.atleast_1d(z)) == 1:
            z = np.array([z] * len(u))
        else:
            z = np.asarray(z)
        return np.vstack(
            [
                z / self.focal * (u - self.principal[0] + self.xoffset),
                z / self.focal * (v - self.principal[1] + self.yoffset),
                z,
            ]
        ).T

    def save_json(self, file_name, extra_data=None):
        camera_params = {
            "dewarped_focal": self.focal,
            "dist_poly": list(self.dist_poly),
            "sensor_width": self.sensor_width,
            "pixel_width": self.pixel_width,
        }
        if self.nominal_homography is not None:
            camera_params["rotation"] = [list(row) for row in self.nominal_homography]
        if extra_data is not None:
            camera_params.update(extra_data)
        with open(file_name, "w") as fd:
            json.dump(camera_params, fd)


def create_lens_from_projective(
    shape, focal_length, principal_point=None, pixel_width=1e-3
):
    h, w, *_ = shape
    uu, vv = np.meshgrid(np.linspace(0, w - 1, 10), np.linspace(0, h - 1, 10))
    if principal_point is None:
        px, py = w / 2, h / 2
    else:
        px, py = principal_point
    rr = np.sqrt((uu - px) ** 2 + (vv - py) ** 2)
    poly = np.polyfit(rr.flat, (-np.arctan(rr / focal_length) * 180 / np.pi).flat, 4)
    for i in range(len(poly)):
        poly[i] /= pixel_width ** (len(poly) - i - 1)
    pw = pixel_width

    class MyLens(LensDist):
        dist_poly = list(reversed(poly))
        sensor_width = shape[1]
        pixel_width = pw

    return MyLens(shape, 1)


def create_perspective_lens(shape, sensor_width, pixel_width, focal=None):
    data = [sensor_width, pixel_width]

    class MyLens(LensDist):
        dist_poly = []
        sensor_width = data[0]
        pixel_width = data[1]

    lens = MyLens(shape, focal=focal)
    return lens


def create_lens_from_json(shape, json_filename):
    data = json.load(open(json_filename))

    class MyLens(LensDist):
        dist_poly = data["dist_poly"]
        sensor_width = data["sensor_width"]
        pixel_width = data["pixel_width"]

    lens = MyLens(shape, data["dewarped_focal"])
    if "rotation" in data:
        lens.update(nominal_homography=np.array(data["rotation"]))
    lens.json_data = data
    return lens


class Projective(LensDist):
    def __init__(self, shape, focal):
        self.sensor_width = shape[1]
        super().__init__(shape, focal)

    def warp_points(self, image_points):
        return image_points

    def dewarp_points(self, image_points):
        return image_points


class DewarpedLens(LensDist):
    def __init__(self, original_lens):
        self.width, self.height = original_lens.dewarped_resolution
        self.image_scale = original_lens.image_scale
        self.sensor_width = original_lens.sensor_width
        self.homography = original_lens.homography
        self.nominal_homography = original_lens.nominal_homography
        self.dewarped_resolution = original_lens.dewarped_resolution
        self.xoffset = original_lens.xoffset
        self.yoffset = original_lens.yoffset
        self.principal = original_lens.principal
        self.focal = original_lens.focal
        self.polar_pixel_transform = original_lens.polar_pixel_transform
        self.polar_pixel_transform_inv = original_lens.polar_pixel_transform_inv
        self._ox = self._oy = self._mask = None

    def d2a(self, x):
        return np.arctan(x)

    def a2d(self, x):
        return np.tan(x)


def rotmat(theta_x=0, theta_y=0, theta_z=0):
    c, s = np.cos(theta_z), np.sin(theta_z)
    Rz = np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)))
    c, s = np.cos(theta_y), np.sin(theta_y)
    Ry = np.array(((c, 0, -s), (0, 1, 0), (s, 0, c)))
    c, s = np.cos(theta_x), np.sin(theta_x)
    Rx = np.array(((1, 0, 0), (0, c, -s), (0, s, c)))
    return np.dot(np.dot(Rx, Ry), Rz)


def rotmat_xyz(theta_x=0, theta_y=0, theta_z=0):
    c, s = np.cos(theta_z), np.sin(theta_z)
    Rz = np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)))
    c, s = np.cos(theta_y), np.sin(theta_y)
    Ry = np.array(((c, 0, -s), (0, 1, 0), (s, 0, c)))
    c, s = np.cos(theta_x), np.sin(theta_x)
    Rx = np.array(((1, 0, 0), (0, c, -s), (0, s, c)))
    return np.dot(np.dot(Rz, Ry), Rx)


class LensDistM3006_43(LensDist):
    sensor_width = 2048
    dist_poly = [-0.02438, -36.24595, -0.08547, -0.33853, 0.01982]
    pixel_width = 1.75e-3


class LensDistM3006_169(LensDistM3006_43):
    sensor_width = 1920


class LensDistF1004(LensDist):
    sensor_width = 1280
    dist_poly = [-0.02792, -25.74656, 0.00561, -0.23004, -0.00172]
    pixel_width = 3.0e-3


class LensDistM3057(LensDist):
    sensor_width = 2048
    pixel_width = 2.4e-3
    dist_poly = list(
        reversed(
            [
                0.007772686612115607,
                -0.40449690156368895,
                -0.006024852924179989,
                -35.12486079668274,
                0.008070330081536146,
            ]
        )
    )


class LensDistM3058(LensDist):
    sensor_width = 2992
    pixel_width = 1.85e-3
    dist_poly = list(
        reversed(
            [
                2.8823897399751908,
                6.265501435429633,
                -13.657537082085232,
                -57.902462008677,
                6.926779731246203,
            ]
        )
    )


class LensDistM3106(LensDist):
    sensor_width = 2688
    pixel_width = 2.0e-3
    dist_poly = list(reversed([-0.00158, -0.02819, 0.00902, -23.95602, -0.02587]))


LensDistM3106MkII = LensDistM3106
