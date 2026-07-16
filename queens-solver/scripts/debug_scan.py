from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
"""esitmated by brute force checking the masks for the 8 fixtures. likely fragile
but can keep for now"""
CHROMA_THRESHOLD = 7

class Dumper:
    """Writes debug images into a folder """

    def __init__(self, outdir: Path, enabled: bool = True):
        self.outdir = outdir
        self.enabled = enabled
        self._count = 0
        if self.enabled:
            if self.outdir.exists():
                shutil.rmtree(self.outdir)
            self.outdir.mkdir(parents=True)

    def __call__(self, name: str, image: np.ndarray) -> None:
        if not self.enabled:
            return
        self._count += 1
        path = self.outdir / f"{self._count:02d}_{name}.png"
        cv2.imwrite(str(path), self._to_uint8(image))

    @staticmethod
    def _to_uint8(image: np.ndarray) -> np.ndarray:
        img = np.asarray(image)
        if img.dtype == np.bool_:
            return img.astype(np.uint8) * 255
        if img.dtype == np.uint8:
            return img
        # float / int of some other flavour: stretch to 0..255 so you can
        # actually see it. Fine for eyeballing, useless for measuring.
        return cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    def plot(self, name: str, values: np.ndarray, height: int = 200) -> None:
        """Render a 1-D signal as an image. Handy for gridline projections."""
        if not self.enabled:
            return
        v = np.asarray(values, dtype=np.float64).ravel()
        canvas = np.full((height, len(v), 3), 255, np.uint8)
        span = v.max() - v.min()
        norm = (v - v.min()) / span if span else np.zeros_like(v)
        ys = (height - 1 - norm * (height - 1)).astype(int)
        for x, y in enumerate(ys):
            canvas[y:, x] = (60, 60, 60)
        self(name, canvas)
 

def analyze(image: np.ndarray, dump: Dumper) -> None:
    
    dump("original", image)
    print(f"    shape={image.shape} dtype={image.dtype}")

    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV) #convert to hsv
    dump("saturation", hsv_image[:, :, 1])

    lab_image = cv2.cvtColor(image, cv2.COLOR_BGR2Lab)  # convert to Lab
    a = lab_image[:, :, 1].astype(np.float32) - 128.0   # widen BEFORE subtracting
    b = lab_image[:, :, 2].astype(np.float32) - 128.0
    chroma = np.sqrt(a * a + b * b)                     # distance from neutral
    dump("chroma", chroma)

    mask = chroma > CHROMA_THRESHOLD   # boolean array, shape (H, W)
    dump("mask", mask)

    """ bin_width = 2
    values = chroma.ravel()
    top = float(values.max())
    edges = np.arange(0, top + bin_width, bin_width)
    counts, _ = np.histogram(values, bins=edges)

    peak = counts.max()
    for lo, count in zip(edges[:-1], counts):
        bar = "#" * int(50 * count / peak) if peak else ""
        pct = 100.0 * count / values.size
        print(f"    {lo:5.0f}-{lo + bin_width:<5.0f} {pct:6.2f}% {bar}")

    p = np.percentile(values, [50, 90, 95, 99])
    print(f"    median={p[0]:.1f}  p90={p[1]:.1f}  p95={p[2]:.1f}  p99={p[3]:.1f}")
 """
def iter_images(path: Path):
    if path.is_file():
        yield path
    elif path.is_dir():
        for child in sorted(path.iterdir()):
            if child.suffix.lower() in IMAGE_SUFFIXES:
                yield child
    else:
        sys.exit(f"no such file or directory: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="image file or folder of images")
    parser.add_argument("--out", type=Path, default=Path("debug_out"))
    args = parser.parse_args()

    images = list(iter_images(args.path))
    if not images:
        sys.exit(f"no images found in {args.path}")

    for image_path in images:
        print(f"\n{image_path.name}")
        image = cv2.imread(str(image_path))
        if image is None:
            print("    !! imread returned None (bad path or unsupported file)")
            continue
        dump = Dumper(args.out / image_path.stem)
        try:
            analyze(image, dump)
        except Exception as exc:  # throwaway script: keep going, report later
            print(f"    !! {type(exc).__name__}: {exc}")
        else:
            print(f"    -> {dump.outdir}")


if __name__ == "__main__":
    main()