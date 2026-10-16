"""Prepare one patient and open it in ParaView, save front/side/top PNGs,
or save a rotating video.

Usage:  python run_case.py <pat_id> <root_dir> [--png] [--video]

Run this with the Python that has SimpleITK and numpy installed; it uses the
same Python for prepare_for_paraview.py and ParaView's own pvpython for
render_case.py. Works on macOS, Linux and Windows. --video needs ffmpeg
(https://ffmpeg.org) on the PATH to join the frames into an MP4.
"""
import argparse
import glob
import os
import platform
import shutil
import subprocess
import sys

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# Lesion volume color scale (mL): colors run from VOL_MIN to VOL_MAX
VOL_MIN = 0.0
VOL_MAX = 20

# Color lesion volumes on a logarithmic (True) or linear (False) scale.
# A log scale needs VOL_MIN > 0; 0 is replaced by LOG_MIN_FALLBACK.
LOGARITHMIC_VOLUMES = True
LOG_MIN_FALLBACK = 0.01

# PNG zoom: 1.0 = ParaView's default fit, larger = brain fills more of the image
ZOOM = 2.0

# Show the lesion volume color legend
SHOW_LEGEND = True

# Opacity of the 3D brain: scales the whole DWI opacity curve.
# 1.0 = as designed in ParaView, smaller = more transparent
BRAIN_OPACITY = 0.5

# Rotating video (--video): length of one full turn and frame rate
VIDEO_SECONDS = 8
VIDEO_FPS = 30

# Folder containing pvpython / paraview. Leave as None to search the usual
# install locations, or set it, e.g.
#   macOS:   "/Applications/ParaView-6.2.0.app/Contents/bin"
#   Linux:   "/opt/ParaView-6.2.0/bin"
#   Windows: r"C:\Program Files\ParaView 6.2.0\bin"
PARAVIEW_BIN = None

# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def find_paraview():
    """Return (pvpython, paraview) executable paths."""
    system = platform.system()
    exe = ".exe" if system == "Windows" else ""

    if PARAVIEW_BIN:
        candidates = [PARAVIEW_BIN]
    elif system == "Darwin":
        candidates = sorted(glob.glob("/Applications/ParaView*.app/Contents/bin"), reverse=True)
    elif system == "Windows":
        candidates = sorted(glob.glob(r"C:\Program Files\ParaView*\bin"), reverse=True)
    else:
        candidates = sorted(glob.glob("/opt/ParaView*/bin")
                            + glob.glob(os.path.expanduser("~/ParaView*/bin")), reverse=True)
        on_path = shutil.which("pvpython")
        if on_path:
            candidates.insert(0, os.path.dirname(on_path))

    for bin_dir in candidates:
        pvpython = os.path.join(bin_dir, "pvpython" + exe)
        if not os.path.isfile(pvpython):
            continue
        if system == "Darwin":
            # The GUI executable sits in Contents/MacOS inside the app bundle
            paraview = os.path.join(os.path.dirname(bin_dir), "MacOS", "paraview")
        else:
            paraview = os.path.join(bin_dir, "paraview" + exe)
        return pvpython, paraview

    sys.exit("Could not find ParaView. Set PARAVIEW_BIN at the top of run_case.py "
             "to the folder that contains pvpython.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pat_id")
    parser.add_argument("root_dir")
    parser.add_argument("--png", action="store_true",
                        help="save front/side/top PNGs instead of opening ParaView")
    parser.add_argument("--video", action="store_true",
                        help="save a rotating MP4 video instead of opening ParaView")
    args = parser.parse_args()

    vol_min = VOL_MIN
    if LOGARITHMIC_VOLUMES and vol_min <= 0:
        print(f"Log scale needs VOL_MIN > 0; using {LOG_MIN_FALLBACK} mL instead of {vol_min}.")
        vol_min = LOG_MIN_FALLBACK

    pvpython, paraview = find_paraview()

    # 1. Prepare the images (this Python, which has SimpleITK)
    subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "prepare_for_paraview.py"),
                    args.pat_id, args.root_dir], check=True)

    # 2. Render (ParaView's Python); settings are passed as environment variables
    env = dict(os.environ,
               PAT_ID=args.pat_id,
               ROOT_DIR=args.root_dir,
               VOL_MIN=str(vol_min),
               VOL_MAX=str(VOL_MAX),
               LOGARITHMIC_VOLUMES="1" if LOGARITHMIC_VOLUMES else "0",
               ZOOM=str(ZOOM),
               SHOW_LEGEND="1" if SHOW_LEGEND else "0",
               BRAIN_OPACITY=str(BRAIN_OPACITY))
    render_script = os.path.join(SCRIPT_DIR, "render_case.py")

    base = os.path.join(args.root_dir, args.pat_id, f"{args.pat_id}_3d")

    if args.png:
        env["OUT_PNG"] = base       # _front/_side/_top.png are appended
        subprocess.run([pvpython, render_script], env=env, check=True)
        print(f"Saved {base}_front.png, {base}_side.png, {base}_top.png")

    if args.video:
        frames_dir = f"{base}_video_frames"
        env.pop("OUT_PNG", None)
        env["OUT_VIDEO_FRAMES"] = frames_dir
        env["VIDEO_FRAMES"] = str(VIDEO_SECONDS * VIDEO_FPS)
        subprocess.run([pvpython, render_script], env=env, check=True)

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            try:   # ffmpeg bundled with the imageio-ffmpeg package (pip install imageio-ffmpeg)
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except ImportError:
                pass
        if ffmpeg is None:
            print(f"ffmpeg not found: the frames are in {frames_dir}. Install ffmpeg "
                  "to have them joined into an MP4 automatically.")
        else:
            video = f"{base}_rotation.mp4"
            subprocess.run([ffmpeg, "-y", "-loglevel", "error",
                            "-framerate", str(VIDEO_FPS),
                            "-i", os.path.join(frames_dir, "frame_%04d.png"),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                            video], check=True)
            shutil.rmtree(frames_dir)
            print(f"Saved {video}")

    if not (args.png or args.video):
        subprocess.run([paraview, f"--script={render_script}"], env=env, check=True)


if __name__ == "__main__":
    main()
