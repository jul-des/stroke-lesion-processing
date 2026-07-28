import nibabel as nib
import numpy as np
import os
from scipy import ndimage
import SimpleITK as sitk
import pandas as pd
from typing import Optional, Dict, List, Sequence
import logging
from utils.pyradiomics_utils import *
import xml.etree.ElementTree as ET

def load_image(id, root, suffix, mask = False):
    if mask:
        path = os.path.join(root, id, "masks", id + suffix)
    else:
        path = os.path.join(root, id, "images", id + suffix)
    img = nib.load(path)
    fdata = img.get_fdata()
    vox_dims = img.header.get_zooms()
    shape = fdata.shape
    return fdata, vox_dims, shape

def calculate_total_lesion_volume(mask_data, voxel_dims, unit='mm3'):

    
    # Count lesion voxels
    num_lesion_voxels = np.count_nonzero(mask_data)

    # Calculate volume in mm³
    voxel_volume_mm3 = np.prod(voxel_dims)
    total_volume_mm3 = num_lesion_voxels * voxel_volume_mm3
    
    # Convert to requested unit
    if unit.lower() in ['mm3', 'mm^3']:
        return total_volume_mm3
    elif unit.lower() in ['cm3', 'cm^3', 'ml']:
        return total_volume_mm3 / 1000.0  # 1 cm³ = 1000 mm³
    else:
        raise ValueError(f"Unknown unit: {unit}. Use 'mm3', 'cm3', or 'ml'")



def analyze_stroke_lesions(lesion_mask, lesion_mask_mni, voxel_dims, vascular_atlas, excluded_territories = {0}, unit = "ml"): 

    
    # Get unique lesion labels (excluding background)
    lesion_ids = np.unique(lesion_mask)
    lesion_ids = lesion_ids[lesion_ids != 0]
    n_lesions = len(lesion_ids)
    
    # Calculate voxel volume in mm³
    voxel_volume = np.prod(voxel_dims) 
    if unit.lower() in ['mm3', 'mm^3']:
        pass
    elif unit.lower() in ['cm3', 'cm^3', 'ml']:
        voxel_volume /= 1000.0  # Convert mm³ to cm³ or ml
    else:
        raise ValueError(f"Unknown unit: {unit}. Use 'mm3', 'cm3', or 'ml'")

    
    results = {'Lesion ID': [], 'Individual lesion volume' : [], 'centroid' : [], 'region' : [], 'overlap percentage': []}
    
    for lesion_id in lesion_ids:
        # Create binary mask for this lesion
        lesion_binary = (lesion_mask == lesion_id)
        lesion_binary_mni = (lesion_mask_mni == lesion_id)
        
        # 1. Calculate volume using original mask
        num_voxels = np.sum(lesion_binary)
        volume = num_voxels * voxel_volume
        
        # 2. Calculate centroid using MNI-registered mask
        centroid = ndimage.center_of_mass(lesion_binary_mni)
        
        # 3. Determine vascular territory using MNI-registered mask
        # Extract vascular territory labels where lesion exists
        lesion_territories = vascular_atlas[lesion_binary_mni]
        
        # Get unique territories and counts
        unique_territories, counts = np.unique(lesion_territories, return_counts=True)
        
        # Filter out excluded territories
        valid_mask = ~np.isin(unique_territories, list(excluded_territories))
        valid_territories = unique_territories[valid_mask]
        valid_counts = counts[valid_mask]
        
        # Determine vascular territory
        if len(valid_territories) > 0:
            # Find most common valid territory
            most_common_idx = np.argmax(valid_counts)
            vascular_territory = valid_territories[most_common_idx]
            overlap_percentage = (valid_counts[most_common_idx] / len(lesion_territories)) * 100
        else:
            # Lesion is completely in excluded territories
            vascular_territory = None
            overlap_percentage = 0.0
        
        # Store results
        results['Lesion ID'].append(lesion_id)
        results['Individual lesion volume'].append(volume)
        results['centroid'].append(centroid)
        results['region'].append(vascular_territory)
        results['overlap percentage'].append(overlap_percentage)
    
    return pd.DataFrame(results), n_lesions





def load_label_dict_txt(path, level=1):
    if level==1:
        value_idx = 1
        label_idx = 2
    elif level==2:
        value_idx = 3
        label_idx = 4
    else:
        print("ERROR: Level should be 1 or 2")
        return
    with open(path) as f:
        lines = f.readlines()
    mapping_dict = {0: "background"}
    for line in lines[7:]:
        line = line.strip()
        line = line.split("\t")
        mapping_dict[int(line[value_idx])] = line[label_idx]
    return mapping_dict

def load_label_dict_xml(xml_path, include_background=True):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    labels = {int(label.get('index')) + 1: label.text for label in root.iter('label')}
    if include_background:
        labels[0] = 'Background'
    return labels




def extract_lesion_shape_features(
    lesion_mask: np.ndarray,
    spacing: Optional[tuple] = None,
    reference_image: Optional[np.ndarray] = None,
    params: Optional[Dict] = None
) -> pd.DataFrame:


    mask_sitk = sitk.GetImageFromArray(lesion_mask.astype(np.int32))
    
    # Set voxel spacing
    if spacing is not None:
        # Take only first 3 elements (in case of 4D with time dimension)
        # SimpleITK uses (x, y, z) ordering, reverse the input (z, y, x)
        # Convert to Python floats to avoid numpy type issues
        spacing_3d = [float(s) for s in spacing[:3]][::-1]
        mask_sitk.SetSpacing(spacing_3d)
    else:
        mask_sitk.SetSpacing([1.0, 1.0, 1.0])
    
    # Get unique lesion labels (excluding background=0)
    unique_labels = np.unique(lesion_mask)
    unique_labels = unique_labels[unique_labels != 0]  # Remove background
    
    if len(unique_labels) == 0:
        raise ValueError("No lesions found in mask (only background=0 detected)")
    
    
    # Extract features for each lesion
    all_features = []
    
    for label in unique_labels:
        # Check lesion size
        lesion_voxels = np.sum(lesion_mask == label)
        
        # Get lesion bounding box to check dimensionality
        lesion_coords = np.argwhere(lesion_mask == label)
        bbox_size = lesion_coords.max(axis=0) - lesion_coords.min(axis=0) + 1
        num_dimensions = np.sum(bbox_size > 1)  # How many axes have extent > 1
        voxel_volume = np.prod(mask_sitk.GetSpacing())
        total_volume = voxel_volume * lesion_voxels
        
        if lesion_voxels == 1 or num_dimensions < 2:
            # Handle single-voxel or 1D lesions (can't compute meaningful 3D shape features)

            
            shape_features = {
                'N voxels': int(lesion_voxels),
                'MeshVolume': np.nan,
                'SurfaceArea': np.nan,
                'SurfaceVolumeRatio': np.nan,
                'Sphericity': np.nan,
                'Maximum3DDiameter': np.nan,
                'Maximum2DDiameterSlice': np.nan,
                'Maximum2DDiameterColumn': np.nan,
                'Maximum2DDiameterRow': np.nan,
                'MajorAxisLength': np.nan,
                'MinorAxisLength': np.nan,
                'LeastAxisLength': np.nan,
                'Elongation': np.nan,
                'Flatness': np.nan
            }
            
            all_features.append(shape_features)
            continue
        
        # Create binary mask for current lesion
        binary_mask = sitk.BinaryThreshold(
            mask_sitk,
            lowerThreshold=int(label),
            upperThreshold=int(label),
            insideValue=1,
            outsideValue=0
        )
        
        # Extract features
        try:
            features = calculate_shape_features(binary_mask, label=1)
            features['N voxels'] = int(lesion_voxels)
            all_features.append(features)
            
        except Exception as e:
            print(f"Warning: Could not extract features for lesion {label} ({lesion_voxels} voxels): {str(e)}")
            continue
    
    # Create DataFrame
    if not all_features:
        raise ValueError("No features could be extracted from any lesion")
    
    features_df = pd.DataFrame(all_features)

    
    return features_df


def get_available_shape_features() -> List[str]:
    """
    Get list of available shape features in PyRadiomics.
    
    Returns:
    --------
    list
        List of shape feature names
    """
    feature_names = [
        'VoxelVolume', 'MeshVolume', 'SurfaceArea', 'SurfaceVolumeRatio',
        'Sphericity', 'Maximum3DDiameter', 'Maximum2DDiameterSlice', 
        'Maximum2DDiameterColumn', 'Maximum2DDiameterRow', 'MajorAxisLength', 
        'MinorAxisLength', 'LeastAxisLength', 'Elongation', 'Flatness'
    ]
    return feature_names


def calculate_individual_lesion_volumes(mask_data, voxel_dims, unit='ml'):

    voxel_volume_mm3 = np.prod(voxel_dims)
    
    # Conversion factor
    if unit.lower() in ['mm3', 'mm^3']:
        conversion = 1.0
    elif unit.lower() in ['cm3', 'cm^3', 'ml']:
        conversion = 1.0 / 1000.0
    else:
        raise ValueError(f"Unknown unit: {unit}. Use 'mm3', 'cm3', or 'ml'")
    
    # Get unique lesion labels (excluding background = 0)
    lesion_labels = np.unique(mask_data)
    lesion_labels = lesion_labels[lesion_labels != 0]
    
    # Calculate volume for each lesion
    results = []
    for label in lesion_labels:
        num_voxels = np.sum(mask_data == label)
        volume_mm3 = num_voxels * voxel_volume_mm3
        volume_converted = volume_mm3 * conversion
        
        results.append(
            volume_converted
        )
    
    return results



def lesion_atlas_overlap(
    lesion_fdata: np.ndarray,
    atlas_fdata: np.ndarray,
    vox_dims: Sequence[float],
    all_labels: Optional[Sequence[int]] = None,
    unit = 'ml'
) -> pd.DataFrame:
    
    # --- Binarize lesion mask (handles float masks, values != 0/1, etc.) ---
    lesion_arr = lesion_fdata.astype(bool)

    # --- Atlas labels as integers (round in case of float rounding noise) ---
    atlas_arr = np.rint(atlas_fdata).astype(int)

    # --- Voxel volume in mm^3 ---
    voxel_volume_mm3 = float(np.prod(vox_dims))

    if unit.lower() in ['mm3', 'mm^3']:
        conversion = 1.0
    elif unit.lower() in ['cm3', 'cm^3', 'ml']:
        conversion = 1.0 / 1000.0
    else:
        raise ValueError(f"Unknown unit: {unit}. Use 'mm3', 'cm3', or 'ml'")
    
    voxel_volume = voxel_volume_mm3 * conversion

    # --- Fixed, full set of region labels (excluding background) ---
    if all_labels is None:
        all_labels = np.unique(atlas_arr)
    all_labels = np.asarray(sorted(all_labels), dtype=int)

    # --- Voxel counts per label under the lesion ---
    overlapping_labels = atlas_arr[lesion_arr]
    present_labels, present_counts = np.unique(overlapping_labels, return_counts=True)
    counts_by_label = dict(zip(present_labels.tolist(), present_counts.tolist()))

    # --- Build volume for every label in all_labels, 0 if absent ---
    volumes = np.array(
        [counts_by_label.get(int(lbl), 0) * voxel_volume for lbl in all_labels]
    )

    df = pd.DataFrame([volumes], columns=all_labels)

    return df


