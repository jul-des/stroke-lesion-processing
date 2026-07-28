import pandas as pd
import ants
import numpy as np
import os
import cc3d
import nibabel as nib


def dice_coefficient(mask1, mask2):
    m1 = mask1.numpy() > 0
    m2 = mask2.numpy() > 0

    intersection = np.logical_and(m1, m2).sum()
    size_sum = m1.sum() + m2.sum()

    if size_sum == 0:
        return np.nan

    return 2.0 * intersection / size_sum

def run_registration_qc(
    flair_brain_mask,
    dwi_brain_mask, 
    mni_brain_mask_path,
    flair_to_mni_transforms,
    lesion_mask_path,
    dwi_to_mni_transforms,
    mni
):
    """
    Automated QC for registration.
    Returns a dict of QC metrics.
    """

    # --------------------------------------------------
    # Load masks
    # --------------------------------------------------
    mni_brain = ants.image_read(mni_brain_mask_path)
    lesion_mask = ants.image_read(lesion_mask_path)

    # --------------------------------------------------
    # Transform FLAIR brain mask → MNI
    # --------------------------------------------------
    flair_brain_mni = ants.apply_transforms(
        fixed=mni,
        moving=flair_brain_mask,
        transformlist=flair_to_mni_transforms,
        interpolator="nearestNeighbor"
    )

    # --------------------------------------------------
    # Brain overlap Dice
    # --------------------------------------------------
    brain_dice_flair = dice_coefficient(flair_brain_mni, mni_brain)


    # --------------------------------------------------
    # Transform lesion → MNI (single step, already correct)
    # --------------------------------------------------
    lesion_mni = ants.apply_transforms(
        fixed=mni,
        moving=lesion_mask,
        transformlist=dwi_to_mni_transforms,
        interpolator="nearestNeighbor"
    )


    lesion_np = lesion_mni.numpy() > 0
    brain_np = mni_brain.numpy() > 0

    lesion_voxels = lesion_np.sum()
    lesion_in_brain = np.logical_and(lesion_np, brain_np).sum()

    if lesion_voxels == 0:
        lesion_brain_fraction = np.nan
    else:
        lesion_brain_fraction = lesion_in_brain / lesion_voxels
    
     # --------------------------------------------------
    # Transform DWI brain mask → MNI
    # --------------------------------------------------
    dwi_brain_mni = ants.apply_transforms(
        fixed=mni,
        moving=dwi_brain_mask,
        transformlist=dwi_to_mni_transforms,
        interpolator="nearestNeighbor"
    )

    # --------------------------------------------------
    # Brain overlap Dice
    # --------------------------------------------------
    brain_dice_dwi = dice_coefficient(dwi_brain_mni, mni_brain)

    return {
        "Brain Dice FLAIR": brain_dice_flair,
        "Brain Dice DWI": brain_dice_dwi,
        "Lesion Fraction within Brain Mask": lesion_brain_fraction
    }





def register_lesion_to_mni(
    flair,
    dwi,
    mni_flair_template_path,
    flair_brain_mask,
    dwi_brain_mask,
    mni_brain_mask_path,
    output_folder,
    sub_id,
):
    """
    Lesion-masked DWI → MNI registration using ANTs SyN.
    Final lesion transformation is done in ONE step only.
    """

    # --------------------------------------------------
    # Load images
    # --------------------------------------------------
    dwi_lesion_path = os.path.join(output_folder, sub_id, "masks", f"{sub_id}_lesion_msk.nii.gz")
    
    lesion_mask = nib.load(dwi_lesion_path)
    affine = lesion_mask.affine
    lesion_data = lesion_mask.get_fdata()
    
    lesion_components, N = cc3d.connected_components(lesion_data, connectivity=26, return_N = True)
    lesion_components = nib.Nifti1Image(lesion_components, affine)
    lesion_components_path = os.path.join(output_folder, sub_id, "masks", f"{sub_id}_lesion_components.nii.gz")
    nib.save(lesion_components, lesion_components_path)
    
    lesion_components = ants.image_read(lesion_components_path, pixeltype="uint8")
    mni = ants.image_read(mni_flair_template_path)

    # --------------------------------------------------
    # Step 1: DWI → FLAIR (linear)
    # --------------------------------------------------
    print("... Registering DWI → FLAIR (rigid)...")

    dwi_to_flair = ants.registration(
        fixed=flair,
        moving=dwi,
        type_of_transform="Rigid",
        reg_iterations=(100, 50, 20),
        verbose=False
    )

    dwi_to_flair_tx = dwi_to_flair["fwdtransforms"][0]


    # --------------------------------------------------
    # Step 2: FLAIR → MNI (SyN)
    # --------------------------------------------------
    print("... Registering FLAIR → MNI (SyN)...")

    flair = ants.resample_image(flair, mni.spacing, use_voxels=False)

    flair_to_mni = ants.registration(
        fixed=mni,
        moving=flair,
        type_of_transform="SyN",

        syn_metric="MI",
        syn_sampling=32,

        reg_iterations=(70, 50, 20),
        shrink_factors=(4, 2, 1),
        smoothing_sigmas=(2, 1, 0),
        verbose=False
    )

    ants.image_write(
            flair_to_mni["warpedmovout"],
            os.path.join(output_folder, sub_id, f"{sub_id}_flair_mni.nii.gz")
        )

    # --------------------------------------------------
    # Step 3: Compose transforms DWI → MNI
    # --------------------------------------------------
    dwi_to_mni_transforms = [
        flair_to_mni["fwdtransforms"][1],  # SyN warp
        flair_to_mni["fwdtransforms"][0],  # affine
        dwi_to_flair_tx                    # rigid
    ]

    # --------------------------------------------------
    # Step 4: Apply composed transform to DWI
    # --------------------------------------------------

    dwi_mni = ants.apply_transforms(
        fixed=mni,
        moving=dwi,
        transformlist=dwi_to_mni_transforms,
        interpolator="linear"
    )

    ants.image_write(dwi_mni, os.path.join(output_folder, sub_id, f"{sub_id}_dwi_mni.nii.gz"))


    # --------------------------------------------------
    # Step 5b: Apply composed transform to lesion 
    # --------------------------------------------------

    lesion_mni = ants.apply_transforms(
        fixed=mni,
        moving=lesion_components,
        transformlist=dwi_to_mni_transforms,
        interpolator="nearestNeighbor"
    )
    ants.image_write(lesion_mni, os.path.join(output_folder, sub_id, "masks", f"{sub_id}_lesion_components_mni.nii.gz"))

    print("... Registration complete.")

    qc_metrics = run_registration_qc(
    flair_brain_mask=flair_brain_mask,
    dwi_brain_mask=dwi_brain_mask,
    mni_brain_mask_path=mni_brain_mask_path,
    flair_to_mni_transforms=flair_to_mni["fwdtransforms"],
    lesion_mask_path=dwi_lesion_path,
    dwi_to_mni_transforms=dwi_to_mni_transforms,
    mni=mni
    )

    print("... QC metrics:")
    for k, v in qc_metrics.items():
        print(f"... ... {k}: {v:.3f}")
    return qc_metrics

