# state file generated using paraview version 6.2.0
import paraview
paraview.compatibility.major = 6
paraview.compatibility.minor = 2

#### import the simple module from the paraview
from paraview.simple import *
#### disable automatic camera reset on 'Show'
paraview.simple._DisableFirstRenderCameraReset()

import os
pat_id = os.environ["PAT_ID"]
pat_dir = os.path.join(os.environ["ROOT_DIR"], pat_id)
masks_dir = os.path.join(pat_dir, "masks")
vol_min = float(os.environ.get("VOL_MIN", "0.0"))   # lesion color scale in mL, set in run_case.py
vol_max = float(os.environ.get("VOL_MAX", "5.0"))
log_volumes = os.environ.get("LOGARITHMIC_VOLUMES", "0") == "1"   # log or linear color scale
zoom = float(os.environ.get("ZOOM", "1.4"))           # >1 makes the brain fill more of the PNG
show_legend = os.environ.get("SHOW_LEGEND", "1") == "1"   # lesion volume color legend on/off
brain_opacity = float(os.environ.get("BRAIN_OPACITY", "0.7"))  # scales the DWI opacity curve, 1.0 = as designed
LoadDistributedPlugin('AnalyzeNIfTIReaderWriter', remote=False, ns=globals())

# ----------------------------------------------------------------
# setup views used in the visualization
# ----------------------------------------------------------------

# White background, black text (also applies to the color legend)
LoadPalette('WhiteBackground')

# Create a new 'Render View'
renderView1 = CreateView('RenderView')
renderView1.Set(
    ViewSize=[1330, 1213],
    CenterOfRotation=[41.06475830078125, 33.20381164550781, 51.723998069763184],
    CameraPosition=[-545.8569395255906, 405.8974163693313, -105.25916901089502],
    CameraFocalPoint=[41.06475830078108, 33.20381164550786, 51.723998069763276],
    CameraViewUp=[-0.43679783999407085, -0.3364718953801314, 0.8342627347519581],
    CameraParallelScale=184.47486391258994,
)
renderView1.UseColorPaletteForBackground = 0
renderView1.Background = [1.0, 1.0, 1.0]

SetActiveView(None)

# ----------------------------------------------------------------
# setup view layouts
# ----------------------------------------------------------------

# create new layout object 'Layout #1'
layout1 = CreateLayout(name='Layout #1')
layout1.AssignView(0, renderView1)
layout1.SetSize(1330, 1213)

# ----------------------------------------------------------------
# restore active view
SetActiveView(renderView1)
# ----------------------------------------------------------------

# ----------------------------------------------------------------
# setup the data processing pipelines
# ----------------------------------------------------------------

# create a new 'NIfTI Volume reader'
lesions = NIfTIVolumereader(registrationName='Lesions', FileName=os.path.join(masks_dir, f"{pat_id}_lesion_vol.nii"))

# create a new 'NIfTI Volume reader'
binary = NIfTIVolumereader(registrationName='Binary', FileName=os.path.join(masks_dir, f"{pat_id}_lesion_bin.nii"))

# create a new 'Contour'
contour1 = Contour(registrationName='Contour1', Input=binary)
contour1.Set(
    ContourBy=['POINTS', 'NIfTIImage'],
    Isosurfaces=[0.5],
)

# create a new 'Smooth'
smooth1 = Smooth(registrationName='Smooth1', Input=contour1)
smooth1.NumberofIterations = 100

# create a new 'Resample With Dataset'
resampleWithDataset1 = ResampleWithDataset(registrationName='ResampleWithDataset1', SourceDataArrays=lesions,
    DestinationMesh=smooth1)

# create a new 'NIfTI Volume reader'
dWI = NIfTIVolumereader(registrationName='DWI', FileName=os.path.join(pat_dir, f"{pat_id}_dwi_bet_new.nii"))

# ----------------------------------------------------------------
# setup the visualization in view 'renderView1'
# ----------------------------------------------------------------

# show data from dWI
dWIDisplay = Show(dWI, renderView1, 'UniformGridRepresentation')

# get color transfer function/color map for 'NIfTIImage'
nIfTIImageLUT = GetColorTransferFunction('NIfTIImage')
nIfTIImageLUT.Set(
    RGBPoints=GenerateRGBPoints(
        preset_name='Grayscale',
        range_min=0.0,
        range_max=640.0,
    ),
    ShowDataHistogram=1,
    ColorSpace='RGB',
    NanColor=[1.0, 0.0, 0.0],
    ScalarRangeInitialized=1.0,
    EnableOpacityMapping=1,
)

# get opacity transfer function/opacity map for 'NIfTIImage'
nIfTIImagePWF = GetOpacityTransferFunction('NIfTIImage')
nIfTIImagePWF.Set(
    # (value, opacity, midpoint, sharpness) per point; opacities scaled by brain_opacity
    Points=[0.0, 0.0 * brain_opacity, 0.5, 0.0,
            63.88591384887695, 0.0 * brain_opacity, 0.5, 0.0,
            117.50444793701172, 0.0580357164144516 * brain_opacity, 0.5, 0.0,
            199.6434783935547, 0.0401785746216774 * brain_opacity, 0.5, 0.0,
            640.0, 1.0 * brain_opacity, 0.5, 0.0],
    ScalarRangeInitialized=1,
)

# get 2D transfer function for 'NIfTIImage'
nIfTIImageTF2D = GetTransferFunction2D('NIfTIImage')
nIfTIImageTF2D.Set(
    ScalarRangeInitialized=1,
    Range=[0.0, 640.0, 0.0, 193.87611627578735],
)

# trace defaults for the display properties.
dWIDisplay.Set(
    Representation='Volume',
    ColorArrayName=['POINTS', 'NIfTIImage'],
    LookupTable=nIfTIImageLUT,
    OSPRayScaleArray='NIfTIImage',
    ScaleFactor=23.88688713312149,
    SelectScaleArray='NIfTIImage',
    GlyphTableIndexArray='NIfTIImage',
    GaussianRadius=1.1943443566560745,
    SetScaleArray=['POINTS', 'NIfTIImage'],
    OpacityArray=['POINTS', 'NIfTIImage'],
    ScalarOpacityUnitDistance=2.9713655150114566,
    ScalarOpacityFunction=nIfTIImagePWF,
    TransferFunction2D=nIfTIImageTF2D,
    OpacityArrayName=['POINTS', 'NIfTIImage'],
    ColorArray2Name=['POINTS', 'NIfTIImage'],
    IsosurfaceValues=[320.0],
    Slice=21,
    SelectInputVectors=[None, ''],
)

# init the 'Piecewise Function' selected for 'ScaleTransferFunction'
dWIDisplay.ScaleTransferFunction.Points = [0.0, 0.0, 0.5, 0.0, 640.0, 1.0, 0.5, 0.0]

# init the 'Piecewise Function' selected for 'OpacityTransferFunction'
dWIDisplay.OpacityTransferFunction.Points = [0.0, 0.0, 0.5, 0.0, 640.0, 1.0, 0.5, 0.0]

# init the 'Polar Axes Representation' selected for 'PolarAxes'
dWIDisplay.PolarAxes.MaximumRadius = 238.8688713312149

# init the 'Plane' selected for 'SliceFunction'
dWIDisplay.SliceFunction.Origin = [41.064760982990265, 33.20381432771683, 51.72399628162384]

# show data from resampleWithDataset1
resampleWithDataset1Display = Show(resampleWithDataset1, renderView1, 'GeometryRepresentation')

# get separate color transfer function/color map for 'NIfTIImage'
separate_resampleWithDataset1Display_NIfTIImageLUT = GetColorTransferFunction('NIfTIImage', resampleWithDataset1Display, separate=True)
separate_resampleWithDataset1Display_NIfTIImageLUT.Set(
    RGBPoints=GenerateRGBPoints(
        preset_name='Inferno',
        range_min=vol_min,
        range_max=vol_max,
    ),
    ShowDataHistogram=1,
    ScalarRangeInitialized=1.0,
    AutomaticRescaleRangeMode='Never',   # keep the same mL scale for every patient
)
if log_volumes:
    # Spread the color points evenly in log space, then map colors logarithmically
    separate_resampleWithDataset1Display_NIfTIImageLUT.MapControlPointsToLogSpace()
    separate_resampleWithDataset1Display_NIfTIImageLUT.UseLogScale = 1

# trace defaults for the display properties.
resampleWithDataset1Display.Set(
    Representation='Surface',
    ColorArrayName=['POINTS', 'NIfTIImage'],
    LookupTable=separate_resampleWithDataset1Display_NIfTIImageLUT,
    OSPRayScaleArray='NIfTIImage',
    ScaleFactor=10.788947677612306,
    SelectScaleArray='NIfTIImage',
    GlyphTableIndexArray='NIfTIImage',
    GaussianRadius=0.5394473838806152,
    SetScaleArray=['POINTS', 'NIfTIImage'],
    OpacityArray=['POINTS', 'NIfTIImage'],
    SelectInputVectors=[None, ''],
)

# init the 'Piecewise Function' selected for 'ScaleTransferFunction'
resampleWithDataset1Display.ScaleTransferFunction.Points = [0.00442148745059967, 0.0, 0.5, 0.0, 1.7730166912078857, 1.0, 0.5, 0.0]

# init the 'Piecewise Function' selected for 'OpacityTransferFunction'
resampleWithDataset1Display.OpacityTransferFunction.Points = [0.00442148745059967, 0.0, 0.5, 0.0, 1.7730166912078857, 1.0, 0.5, 0.0]

# init the 'Polar Axes Representation' selected for 'PolarAxes'
resampleWithDataset1Display.PolarAxes.MaximumRadius = 107.88947677612305

# set separate color map
resampleWithDataset1Display.UseSeparateColorMap = True

# setup the color legend parameters for each legend in this view

# get color legend/bar for separate_resampleWithDataset1Display_NIfTIImageLUT in view renderView1
separate_resampleWithDataset1Display_NIfTIImageLUTColorBar = GetScalarBar(separate_resampleWithDataset1Display_NIfTIImageLUT, renderView1)
separate_resampleWithDataset1Display_NIfTIImageLUTColorBar.Set(
    WindowLocation='Upper Right Corner',
    Position=[0.912781954887218, 0.6595218466611706],
    Title='Lesion volume (mL)',
    ComponentTitle='',
    HorizontalTitle=1,                   # title above the bar, so it can't overlap the labels
    TitleColor=[0.0, 0.0, 0.0],
    LabelColor=[0.0, 0.0, 0.0],
    RangeLabelFormat='{:.3g}',             # min/max as 0.01 and 30 instead of 1.0e-02 and 3.0e+01
)
if log_volumes:
    # Label only the powers of ten inside the range (e.g. 0.1, 1, 10) and drop
    # the many minor log ticks
    import math
    decades = [10.0 ** k for k in range(math.ceil(math.log10(vol_min)),
                                        math.floor(math.log10(vol_max)) + 1)]
    decades = [d for d in decades if not (math.isclose(d, vol_min) or math.isclose(d, vol_max))]
    separate_resampleWithDataset1Display_NIfTIImageLUTColorBar.Set(
        UseCustomLabels=1,
        CustomLabels=decades,
        AutomaticLabelFormat=0,
        LabelFormat='{:.3g}',
        DrawTickMarks=0,
    )

# set color bar visibility
separate_resampleWithDataset1Display_NIfTIImageLUTColorBar.Visibility = int(show_legend)

# show color legend
resampleWithDataset1Display.SetScalarBarVisibility(renderView1, show_legend)

# ----------------------------------------------------------------
# setup color maps and opacity maps used in the visualization
# note: the Get..() functions create a new object, if needed
# ----------------------------------------------------------------

# get separate opacity transfer function/opacity map for 'NIfTIImage'
separate_resampleWithDataset1Display_NIfTIImagePWF = GetOpacityTransferFunction('NIfTIImage', resampleWithDataset1Display, separate=True)
separate_resampleWithDataset1Display_NIfTIImagePWF.Set(
    Points=[vol_min, 0.0, 0.5, 0.0, vol_max, 1.0, 0.5, 0.0],
    ScalarRangeInitialized=1,
)

# ----------------------------------------------------------------
# setup animation scene, tracks and keyframes
# note: the Get..() functions create a new object, if needed
# ----------------------------------------------------------------

# get time animation track
timeAnimationCue1 = GetTimeTrack()

# get the time-keeper
timeKeeper1 = GetTimeKeeper()

# get animation scene
animationScene1 = GetAnimationScene()

# initialize the animation scene
animationScene1.Set(
    ViewModules=renderView1,
    Cues=timeAnimationCue1,
    AnimationTime=0.0,
)

# ----------------------------------------------------------------
# restore active source
SetActiveSource(resampleWithDataset1)
# ----------------------------------------------------------------

# The saved camera belongs to the patient the state was made from:
# re-centre on this patient's brain, keeping the viewing direction
renderView1.ResetCamera()

# ----------------------------------------------------------------
# PNG export: front, side and top views with orientation labels
# ----------------------------------------------------------------
if "OUT_PNG" in os.environ:
    base = os.environ["OUT_PNG"]
    renderView1.OrientationAxesVisibility = 0

    # ParaView shows the LPS-stored images in RAS display axes:
    # +x = Right, +y = Anterior, +z = Superior
    # name: (camera direction from centre, view-up, labels (screen left, right, top, bottom))
    views = {
        "front": ([0, 1, 0],  [0, 0, 1], ("R", "L", "S", "I")),   # from anterior
        "side":  ([-1, 0, 0], [0, 0, 1], ("A", "P", "S", "I")),   # from the left
        "top":   ([0, 0, 1],  [0, 1, 0], ("L", "R", "A", "P")),   # from superior, nose up
    }

    # Four text labels at the screen edges: left, right, top, bottom
    positions = [[0.02, 0.48], [0.95, 0.48], [0.49, 0.93], [0.49, 0.03]]
    labels = []
    for pos in positions:
        t = Text()
        d = Show(t, renderView1)
        d.WindowLocation = 'Any Location'
        d.Position = pos
        d.FontSize = 28
        d.Bold = 1
        d.Color = [0.0, 0.0, 0.0]
        labels.append(t)

    for name, (direction, up, letters) in views.items():
        for t, letter in zip(labels, letters):
            t.Text = letter
        renderView1.CameraFocalPoint = [0, 0, 0]
        renderView1.CameraPosition = direction
        renderView1.CameraViewUp = up
        renderView1.ResetCamera()          # re-centre on the brain, keep the direction
        GetActiveCamera().Dolly(zoom)      # move closer so the brain fills more of the image
        Render(renderView1)
        SaveScreenshot(f"{base}_{name}.png", renderView1, ImageResolution=[1600, 1200])

# ----------------------------------------------------------------
# Video export: one full turn around the vertical (S) axis,
# starting from the front view; frames are saved as numbered PNGs
# and joined into a video by run_case.py
# ----------------------------------------------------------------
if "OUT_VIDEO_FRAMES" in os.environ:
    frames_dir = os.environ["OUT_VIDEO_FRAMES"]
    n_frames = int(os.environ.get("VIDEO_FRAMES", "240"))
    os.makedirs(frames_dir, exist_ok=True)
    renderView1.OrientationAxesVisibility = 0

    # Front view (from anterior, superior up), see the PNG views above
    renderView1.CameraFocalPoint = [0, 0, 0]
    renderView1.CameraPosition = [0, 1, 0]
    renderView1.CameraViewUp = [0, 0, 1]
    renderView1.ResetCamera()
    camera = GetActiveCamera()
    camera.Dolly(zoom)

    for i in range(n_frames):
        Render(renderView1)
        SaveScreenshot(os.path.join(frames_dir, f"frame_{i:04d}.png"), renderView1,
                       ImageResolution=[1600, 1200])
        camera.Azimuth(360.0 / n_frames)   # rotate around the view-up (S) axis
