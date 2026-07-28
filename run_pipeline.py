import os
os.environ["TMPDIR"] = "path/to/tmp/dir" #define path to tmp dir for ANTS registration. ANTS can sometimes have incomplete deletion of /tmp files. By specifying the tmp directory, manual deletion can be perfomred if necesary
os.makedirs(os.environ["TMPDIR"], exist_ok=True)

from pipeline.skullstripping import *
from pipeline.mni_registration import *
from pipeline.utils import *
import pandas as pd


file = pd.read_csv("/path/to/masterfile.csv")
mni_template_path = "/path/to/flair/mni/template.nii.gz"
atlas_path = "/path/to/atlas.nii.gz"


total = len(file)
output = "/path/to/output/directory"
device = "cuda"

for index, row in file.iterrows():
    sub_id = row["Patient ID"]
    if "Center" in file.columns:
        center = row["Center"]
        output_dir = os.path.join(output, center)
    else: 
        output_dir = output
        center = None

    os.makedirs(output_dir, exist_ok=True)

    flair_path = row["Path flair"]
    dwi_path = row["Path dwi"]
    adc_path = row["Path adc"]

    

    print(f"Working on [{index+1}/{total}]", sub_id)
    if not os.path.isfile(flair_path):
        print("[WARNING] FLAIR path does not exist (Skipping)")
        continue
    elif not os.path.isfile(dwi_path):
        print("[WARNING] DWI path does not exist (Skipping)")
        continue
    elif not os.path.isfile(adc_path):
        print("[WARNING] ADC path does not exist (Skipping)")
        continue

    done = os.listdir(output_dir)
    if sub_id in done:
        print("... Skipping (already processed)")
    try:
        preprocess_dwi_adc_flair(sub_id = sub_id, dwi_path=dwi_path, flair_path=flair_path, adc_path=adc_path,
                                output_dir=output_dir, center=center, device=device) 
        print("... Skullstripping completed")   
    except (subprocess.CalledProcessError, RuntimeError, ValueError) as e:
        print("[WARNING] Skullstripping Failed")
        continue

    

    gpus_arg = device_to_docker_gpus(device)

    cmd = ["docker", "run", "--rm"]

    if gpus_arg is not None:
        cmd += ["--gpus", gpus_arg]

    cmd += [
        "-v", os.path.join(output_dir, sub_id) + ":/app/data",
        "isleschallenge/deepisles",
        "--dwi_file_name", sub_id + "_dwi_bet.nii.gz",
        "--adc_file_name", sub_id + "_adc_bet.nii.gz",
        "--flair_file_name", sub_id + "_flair_bet.nii.gz",
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

    cleanup_deepisles_output(output_dir, sub_id)
    
    print("... Lesion segmentation completed")

    lesion_mask = ants.image_read(os.path.join(output_dir, sub_id, "masks", f"{sub_id}_lesion_msk.nii.gz"), pixeltype="uint8")

    images = load_images_ants(output_dir, sub_id)

    if not lesion_mask.numpy().any():
        print("[WARNING] No lesions detected, skipping registration to MNI")
        metrics = None

    else:
        metrics = register_lesion_to_mni(
            flair=images["bet_images"]["flair"],
            dwi=images["bet_images"]["dwi"],
            mni_flair_template_path=mni_template_path,     
            output_folder = output_dir,
            sub_id=sub_id,
            flair_brain_mask=images["masks"]["flair"],
            dwi_brain_mask=images["masks"]["dwi"],
            mni_brain_mask_path=atlas_path
        )
        print("... MNI registration completed")

    save_metrics(metrics, output, sub_id, center)

    
    
    
