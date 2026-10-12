"""Prepare one patient for ParaView.

Usage: python prepare_for_paraview.py <pat_id> <root_dir>

Expects  <root_dir>/<pat_id>/<pat_id>_dwi_bet.nii.gz
         <root_dir>/<pat_id>/masks/<pat_id>_lesion_msk.nii.gz          (binary 0/1)
         <root_dir>/<pat_id>/masks/<pat_id>_lesion_components.nii.gz   (0 = background, 1..n = lesions)
Writes   <root_dir>/<pat_id>/<pat_id>_dwi_bet_new.nii
         <root_dir>/<pat_id>/masks/<pat_id>_lesion_bin.nii
         <root_dir>/<pat_id>/masks/<pat_id>_lesion_vol.nii
"""
import os
import sys

import numpy as np
import SimpleITK as sitk

pat_id, root_dir = sys.argv[1:3]
pat_dir = os.path.join(root_dir, pat_id)
masks_dir = os.path.join(pat_dir, "masks")

dwi_in = os.path.join(pat_dir, f"{pat_id}_dwi_bet.nii.gz")
binary_in = os.path.join(masks_dir, f"{pat_id}_lesion_msk.nii.gz")
components_in = os.path.join(masks_dir, f"{pat_id}_lesion_components.nii.gz")
dwi_out = os.path.join(pat_dir, f"{pat_id}_dwi_bet_new.nii")
binary_out = os.path.join(masks_dir, f"{pat_id}_lesion_bin.nii")   # 0/1, use for the Contour
volume_out = os.path.join(masks_dir, f"{pat_id}_lesion_vol.nii")   # lesion volume in mL per voxel

# --- Header fix: give both masks the DWI's geometry ---
dwi = sitk.ReadImage(dwi_in)
binary = sitk.Cast(sitk.ReadImage(binary_in), sitk.sitkUInt8)
binary.CopyInformation(dwi)
labels = sitk.Cast(sitk.ReadImage(components_in), sitk.sitkUInt16)  # UInt16: allows >255 lesions
labels.CopyInformation(dwi)

# --- Reorient to LPS so every patient is stored the same way. ParaView's NIfTI
# reader turns this into RAS display axes (+x = Right, +y = Anterior,
# +z = Superior), which the L/R/A/P/S/I labels in render_case.py rely on.
dwi = sitk.DICOMOrient(dwi, "LPS")
binary = sitk.DICOMOrient(binary, "LPS")
labels = sitk.DICOMOrient(labels, "LPS")

# --- Lesion volumes ---
stats = sitk.LabelShapeStatisticsImageFilter()
stats.Execute(labels)

lab = sitk.GetArrayFromImage(labels)
vol = np.zeros(lab.shape, dtype=np.float32)
for l in stats.GetLabels():
    ml = stats.GetPhysicalSize(l) / 1000.0   # mm³ -> mL
    vol[lab == l] = ml
    print(f"{pat_id} lesion {l}: {ml:.3f} mL")

vol_img = sitk.GetImageFromArray(vol)
vol_img.CopyInformation(labels)
# Grow values 1 voxel outward so the contour surface (which sits between
# lesion and background voxels) picks up the full volume, not a blend with 0
vol_img = sitk.GrayscaleDilate(vol_img, [1, 1, 1])

# --- Write uncompressed .nii for ParaView ---
sitk.WriteImage(dwi, dwi_out)
sitk.WriteImage(binary, binary_out)
sitk.WriteImage(vol_img, volume_out)
