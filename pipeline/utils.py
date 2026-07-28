
import os 
import shutil
import pandas as pd
import SimpleITK as sitk
import ants

def cleanup_deepisles_output(output_dir, sub_id):

    os.rename(os.path.join(output_dir, sub_id, "results"), os.path.join(output_dir, sub_id, "masks"))
    
    shutil.move(os.path.join(output_dir, sub_id, sub_id + "_flair_brain_mask.nii.gz"), 
                os.path.join(output_dir, sub_id, "masks", sub_id + "_flair_brain_mask.nii.gz"))
    
    shutil.move(os.path.join(output_dir, sub_id, sub_id + "_dwi_adc_brain_mask.nii.gz"), 
                os.path.join(output_dir, sub_id, "masks", sub_id + "_dwi_adc_brain_mask.nii.gz"))
    
    os.rename(os.path.join(output_dir, sub_id, "masks","lesion_msk.nii.gz"),
              os.path.join(output_dir, sub_id, "masks", sub_id + "_lesion_msk.nii.gz"))
    
    os.rename(os.path.join(output_dir, sub_id, "masks","output_screenshot.png"),
              os.path.join(output_dir, sub_id, "masks", sub_id + "_qc_segmentation.png"))


def save_metrics(metrics, output_dir, sub_id, center=None):

    metrics_path = os.path.join(output_dir, "qc_metrics_external.csv")
    if os.path.exists(metrics_path):
        qc_metrics = pd.read_csv(metrics_path).to_dict(orient="list")
    else:
        qc_metrics = {"Patient ID": [], "Brain Dice FLAIR": [], "Brain Dice DWI": [], "Lesion Fraction within Brain Mask": []}
        if center is not None:
            qc_metrics["Center"] = []
    

    qc_metrics["Patient ID"].append(sub_id)
    if center is not None:
        qc_metrics["Center"].append(center)
    if metrics is None:
        qc_metrics["Brain Dice FLAIR"].append("NA")
        qc_metrics["Brain Dice DWI"].append("NA")
        qc_metrics["Lesion Fraction within Brain Mask"].append("NA")

    else:
        qc_metrics["Brain Dice FLAIR"].append(metrics["Brain Dice FLAIR"])
        qc_metrics["Brain Dice DWI"].append(metrics["Brain Dice DWI"])
        qc_metrics["Lesion Fraction within Brain Mask"].append(metrics["Lesion Fraction within Brain Mask"])


    df = pd.DataFrame(qc_metrics)
    df.to_csv(metrics_path, index=False)

def load_images_simple_itk(output_dir, sub_id):
    bet_flair = sitk.ReadImage(os.path.join(output_dir,sub_id, f"{sub_id}_flair_bet.nii.gz"))
    brain_mask_flair = sitk.ReadImage(os.path.join(output_dir, sub_id, f"{sub_id}_flair_brain_mask.nii.gz"))
    bet_dwi = sitk.ReadImage(os.path.join(output_dir,sub_id, f"{sub_id}_dwi_bet.nii.gz"))
    brain_mask_dwi = sitk.ReadImage(os.path.join(output_dir, sub_id, f"{sub_id}_dwi_adc_brain_mask.nii.gz"))
    bet_adc = sitk.ReadImage(os.path.join(output_dir,sub_id, f"{sub_id}_adc_bet.nii.gz"))
    brain_mask_adc = sitk.ReadImage(os.path.join(output_dir, sub_id, f"{sub_id}_dwi_adc_brain_mask.nii.gz"))
    
    images = {
        "bet_images": {
            "dwi": bet_dwi,
            "adc": bet_adc,
            "flair": bet_flair
        },
        "masks": {
            "dwi": brain_mask_dwi,
            "adc": brain_mask_adc,
            "flair": brain_mask_flair
        }
    }

    return images

def load_images_ants(output_dir, sub_id):
    bet_flair = ants.image_read(os.path.join(output_dir,sub_id, f"{sub_id}_flair_bet.nii.gz"), pixeltype="float")
    brain_mask_flair = ants.image_read(os.path.join(output_dir, sub_id, "masks", f"{sub_id}_flair_brain_mask.nii.gz"), pixeltype="uint8")
    bet_dwi = ants.image_read(os.path.join(output_dir,sub_id, f"{sub_id}_dwi_bet.nii.gz"), pixeltype="float")
    brain_mask_dwi = ants.image_read(os.path.join(output_dir, sub_id, "masks", f"{sub_id}_dwi_adc_brain_mask.nii.gz"), pixeltype="uint8")
    bet_adc = ants.image_read(os.path.join(output_dir,sub_id, f"{sub_id}_adc_bet.nii.gz"), pixeltype="float")
    brain_mask_adc = ants.image_read(os.path.join(output_dir, sub_id, "masks", f"{sub_id}_dwi_adc_brain_mask.nii.gz"), pixeltype="uint8")
    
    images = {
        "bet_images": {
            "dwi": bet_dwi,
            "adc": bet_adc,
            "flair": bet_flair
        },
        "masks": {
            "dwi": brain_mask_dwi,
            "adc": brain_mask_adc,
            "flair": brain_mask_flair
        }
    }

    return images

def device_to_docker_gpus(device: str) -> str | None:
    """
    Convert a torch-style device string ("cpu", "cuda", "cuda:0", "cuda:1", ...)
    into the value for `docker run --gpus <value>`.
    Returns None if no GPU should be requested (i.e. cpu).
    """
    if device == "cpu":
        return None
    if device == "cuda":
        return "all"
    if device.startswith("cuda:"):
        idx = device.split(":", 1)[1]
        if not idx.isdigit():
            raise ValueError(f"Unexpected device string: {device}")
        return f"device={idx}"
    raise ValueError(f"Unrecognized device string: {device}")