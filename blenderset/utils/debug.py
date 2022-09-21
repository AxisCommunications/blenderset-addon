import bpy
import numpy as np


def show_points(pkts):
    for p in pkts:
        bpy.ops.mesh.primitive_ico_sphere_add(radius=0.1, location=p)


def show_line(p1, p2):
    n = 10
    pkts = [(i * p1 + (n - i) * p2) / n for i in range(n + 1)]
    show_points(pkts)


def show_poly(pkts, replace=False):
    pkts = np.asarray(pkts)
    for i in range(len(pkts)):
        show_line(pkts[i - 1], pkts[i])
