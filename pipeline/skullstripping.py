import os
import shutil
import subprocess
import ants


def skullstrip_flair_hd_bet(sub_id, input_path, output_dir, device="cuda:0"):
    """
    Skull-strip FLAIR using hd-bet.
    """
    output_path = os.path.join(output_dir, f"{sub_id}_flair_bet.nii.gz")
    cmd = [
        "hd-bet",
        "-i", input_path,
        "-o", output_path,
        "--save_bet_mask",
        "-device", device
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)
    
    flair_mask_path = os.path.join(output_dir, f"{sub_id}_flair_brain_mask.nii.gz")
    os.rename(output_path.replace("_bet.nii.gz", "_bet_bet.nii.gz"), flair_mask_path)

    return flair_mask_path


def register_flair_to_dwi(flair_path, dwi_path):
    """
    Register skull-stripped FLAIR to DWI using ANTs.
    Returns the ANTs registration result dict (contains transform paths).
    """
    flair = ants.image_read(flair_path, pixeltype="float")
    dwi = ants.image_read(dwi_path, pixeltype="float")

    registration = ants.registration(
        fixed=dwi,
        moving=flair,
        type_of_transform="Rigid",  # equivalent to Euler3DTransform used before
        aff_metric="mattes",        # Mattes mutual information, matches original metric
        aff_sampling=32,            # number of histogram bins, matches original
        random_seed=42
    )

    return registration


def apply_mask_to_image(image, mask):
    """
    Apply binary mask to image via elementwise multiplication.
    """
    return image * mask


def preprocess_dwi_adc_flair(
    adc_path,
    dwi_path,
    flair_path,
    sub_id,
    output_dir,
    center,
    device
):
    """
    Skull-strip FLAIR, register to DWI, transform brain mask,
    and apply it to DWI and ADC.
    """

    output_dir = os.path.join(output_dir, sub_id)

    # ----------------------------------
    # Step 1: Skull-strip FLAIR
    # ----------------------------------
    flair_mask_path = skullstrip_flair_hd_bet(
        sub_id=sub_id, input_path=flair_path, output_dir=output_dir, device=device
    )

    # ----------------------------------
    # Step 2: Register FLAIR → DWI
    # ----------------------------------
    registration = register_flair_to_dwi(flair_path, dwi_path)


    # ----------------------------------
    # Step 3: Transform brain mask to DWI space
    # ----------------------------------
    dwi = ants.image_read(dwi_path, pixeltype="float")
    adc = ants.image_read(adc_path, pixeltype="float")
    flair_mask = ants.image_read(flair_mask_path, pixeltype="uint8")

    mask_in_dwi = ants.apply_transforms(
        fixed=dwi,
        moving=flair_mask,
        transformlist=registration["fwdtransforms"],
        interpolator="nearestNeighbor"
    )
    mask_in_dwi = mask_in_dwi.astype("uint8")

    mask_dwi_path = os.path.join(output_dir, f"{sub_id}_dwi_adc_brain_mask.nii.gz")
    ants.image_write(mask_in_dwi, mask_dwi_path)

    # ----------------------------------
    # Step 4: Apply mask to DWI and ADC
    # ----------------------------------
    dwi_masked = apply_mask_to_image(dwi, mask_in_dwi)
    adc_masked = apply_mask_to_image(adc, mask_in_dwi)

    dwi_out = os.path.join(output_dir, f"{sub_id}_dwi_bet.nii.gz")
    adc_out = os.path.join(output_dir, f"{sub_id}_adc_bet.nii.gz")

    ants.image_write(dwi_masked, dwi_out)
    ants.image_write(adc_masked, adc_out)

