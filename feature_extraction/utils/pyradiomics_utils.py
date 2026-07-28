

import numpy as np
import SimpleITK as sitk
from skimage.measure import marching_cubes
from scipy.spatial import ConvexHull
from scipy.spatial.distance import pdist


def _max_pairwise_distance(points: np.ndarray) -> float:
    """Largest pairwise Euclidean distance among a set of points.

    Uses a convex-hull reduction first (the maximum pairwise distance in a
    point set is always achieved between two hull vertices), which keeps this
    fast even for meshes with many thousands of vertices.
    """
    if len(points) < 2:
        return 0.0
    pts = points
    if len(points) > points.shape[1] + 1:
        try:
            hull = ConvexHull(points)
            pts = points[hull.vertices]
        except Exception:
            # Degenerate (e.g. coplanar/collinear) point sets: fall back to
            # the full point set.
            pts = points
    if len(pts) < 2:
        return 0.0
    return float(pdist(pts).max())


def _max_diameter_in_plane(vertices: np.ndarray, axis: int, decimals: int = 6) -> float:
    """Largest pairwise distance between vertices that share an (exact,
    rounded) coordinate on `axis` -- i.e. vertices lying in the same
    axis-aligned plane."""
    vals = np.round(vertices[:, axis], decimals)
    max_d = 0.0
    for v in np.unique(vals):
        group = vertices[vals == v]
        if len(group) < 2:
            continue
        d = _max_pairwise_distance(group)
        if d > max_d:
            max_d = d
    return max_d


def calculate_shape_features(mask: sitk.Image, label: int = 1) -> dict:
    """Calculate a pyradiomics-compatible set of 3D shape features from a
    SimpleITK binary (or labeled) mask.

    Parameters
    ----------
    mask : sitk.Image
        A SimpleITK image containing the segmentation. Can be a binary mask
        (0/1) or a multi-label mask, in which case `label` selects the ROI.
    label : int
        The label value in `mask` that defines the ROI (default 1).

    Returns
    -------
    dict
        Dictionary with keys matching pyradiomics' shape feature names:
        MeshVolume, SurfaceArea, SurfaceVolumeRatio, Sphericity,
        Maximum3DDiameter, Maximum2DDiameterSlice, Maximum2DDiameterColumn,
        Maximum2DDiameterRow, MajorAxisLength, MinorAxisLength,
        LeastAxisLength, Elongation, Flatness
    """
    if mask.GetDimension() != 3:
        raise ValueError("Shape features require a 3D mask.")

    # pyradiomics stores/iterates arrays as (z, y, x); spacing is reversed to match.
    spacing = np.array(mask.GetSpacing()[::-1])  # (sz, sy, sx)

    # --- Pad by 1 voxel, exactly as pyradiomics does, to guarantee a closed surface ---
    mask_arr = sitk.GetArrayFromImage(mask) == label
    mask_arr = np.pad(mask_arr, pad_width=1, mode="constant", constant_values=0)

    if not mask_arr.any():
        raise ValueError(f"No voxels found with label {label} in the mask.")

    # =========================================================================
    # Mesh-based features: MeshVolume, SurfaceArea, SurfaceVolumeRatio,
    # Sphericity, and the 4 diameters.
    # =========================================================================
    verts, faces, _normals, _values = marching_cubes(
        mask_arr.astype(np.uint8), level=0.5, spacing=tuple(spacing)
    )

    p0 = verts[faces[:, 0]]
    p1 = verts[faces[:, 1]]
    p2 = verts[faces[:, 2]]

    # Surface area: sum of triangle areas -- A_i = 1/2 |ab x ac|
    cross_ab_ac = np.cross(p1 - p0, p2 - p0)
    surface_area = float(np.sum(0.5 * np.linalg.norm(cross_ab_ac, axis=1)))

    # Mesh volume: sum of signed tetrahedron volumes w.r.t. the origin
    # V_i = a . (b x c) / 6  (sign depends on consistent face orientation,
    # so we take the absolute value of the total)
    cross_p1_p2 = np.cross(p1, p2)
    signed_vol = np.sum(np.einsum("ij,ij->i", p0, cross_p1_p2)) / 6.0
    mesh_volume = float(abs(signed_vol))

    surface_volume_ratio = surface_area / mesh_volume
    sphericity = (36.0 * np.pi * mesh_volume ** 2) ** (1.0 / 3.0) / surface_area

    # Diameters. Array axes are (z=0 -> slice, y=1 -> row, x=2 -> column).
    max_3d_diameter = _max_pairwise_distance(verts)
    max_2d_diameter_slice = _max_diameter_in_plane(verts, axis=0)   # fixed z  -> row-column (axial) plane
    max_2d_diameter_column = _max_diameter_in_plane(verts, axis=1)  # fixed x  -> row-slice (coronal) plane
    max_2d_diameter_row = _max_diameter_in_plane(verts, axis=2)     # fixed y  -> column-slice (sagittal) plane

    # =========================================================================
    # PCA-based features (do NOT use the mesh): MajorAxisLength,
    # MinorAxisLength, LeastAxisLength, Elongation, Flatness
    # =========================================================================
    coords = np.array(np.where(mask_arr), dtype=float).T  # (N, 3) in (z, y, x) index space
    physical_coords = coords * spacing[None, :]
    physical_coords -= physical_coords.mean(axis=0)
    physical_coords /= np.sqrt(len(physical_coords))

    covariance = physical_coords.T @ physical_coords
    eigen_values = np.linalg.eigvals(covariance)

    # Correct tiny negative eigenvalues caused by floating point error
    # (as pyradiomics does), which can occur e.g. for flat/2D-like ROIs.
    tiny_negative = (eigen_values < 0) & (eigen_values > -1e-10)
    eigen_values[tiny_negative] = 0
    eigen_values = np.sort(eigen_values.real)  # ascending: least, minor, major

    least, minor, major = eigen_values

    major_axis_length = np.sqrt(major) * 4 if major >= 0 else np.nan
    minor_axis_length = np.sqrt(minor) * 4 if minor >= 0 else np.nan
    least_axis_length = np.sqrt(least) * 4 if least >= 0 else np.nan
    elongation = np.sqrt(minor / major) if (minor >= 0 and major >= 0) else np.nan
    flatness = np.sqrt(least / major) if (least >= 0 and major >= 0) else np.nan

    return {
        "MeshVolume": mesh_volume,
        "SurfaceArea": surface_area,
        "SurfaceVolumeRatio": surface_volume_ratio,
        "Sphericity": sphericity,
        "Maximum3DDiameter": max_3d_diameter,
        "Maximum2DDiameterSlice": max_2d_diameter_slice,
        "Maximum2DDiameterColumn": max_2d_diameter_column,
        "Maximum2DDiameterRow": max_2d_diameter_row,
        "MajorAxisLength": float(major_axis_length),
        "MinorAxisLength": float(minor_axis_length),
        "LeastAxisLength": float(least_axis_length),
        "Elongation": float(elongation),
        "Flatness": float(flatness),
    }


