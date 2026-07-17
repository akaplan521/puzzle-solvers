from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from solver.puzzle import Puzzle

CHROMA_THRESHOLD = 7    # !! fragile: ~1-unit margin vs almanac navy bg; calibrated on 8 fixtures
WARP_SIZE = 840         # canonical warped board size; divisible by every n in 4..12 except 11
MAX_N = 12              # largest board size; also sizes edge trim in _count_gridlines
SPIKE_FRACTION = 0.33   # gridline threshold between profile floor and peak; calibrated on 8 fixtures
MIN_FILL_RATIO = 0.80   # hull/bbox agreement below this -> refuse


class ScanError(Exception):
    """Raised when an image cannot be scanned into a puzzle."""


# eq=False because numpy arrays don't compare to a single bool, so the
# generated __eq__ would raise. frozen because a ScanResult is read only.
@dataclass(frozen=True, eq=False)
class ScanResult:
    """
    Attributes:
        puzzle: The recovered puzzle. Validated in __init__.
        corners: (4, 2) float32, board corners in ORIGINAL image pixel
            coordinates, ordered top-left, top-right, bottom-right, bottom-left

        NEEDED FOR OVERLAY AND LIVE SCANNING:
        warp: (3, 3) float64 homography matrix mapping original image to warped square
        warped_size: Pixel side length S of the warped square
    """

    puzzle: Puzzle
    corners: np.ndarray
    warp: np.ndarray
    warped_size: int

    @property
    def n(self) -> int:
        return self.puzzle.n

    def cell_centers(self) -> np.ndarray:
        """Cell centers projected back into original-image coordinates.
        Returns an (n, n, 2) float32 array indexed [row, col] -> (x, y)
        """
        n = self.n
        step = self.warped_size / n
        rows, cols = np.mgrid[0:n, 0:n]
        pts = np.stack(
            [(cols + 0.5) * step, (rows + 0.5) * step], axis=-1
        ).astype(np.float32)

        inverse = np.linalg.inv(self.warp)  #inverse homography matrix: warped -> original
        #perspectiveTransform requires shape (K, 1, 2)
        flat = pts.reshape(-1, 1, 2)
        original = cv2.perspectiveTransform(flat, inverse)
        return original.reshape(n, n, 2)


def find_board(image: np.ndarray) -> np.ndarray:
    """Find the puzzle board in a BGR image.

    Chroma mask -> close -> largest contour -> boundingRect.
    ASSUMES axis-aligned board with >=1 colored cell touching each side

    Returns:
        (4, 2) float32 corners in original-image pixels: TL, TR, BR, BL.

    Raises:
        ScanError: no contours in the chroma mask, or hull/bbox fill ratio
            below MIN_FILL_RATIO (merged UI / partial board).
    """
    lab_image = cv2.cvtColor(image, cv2.COLOR_BGR2Lab)
    a = lab_image[:, :, 1].astype(np.float32) - 128.0  # widen before subtracting; 128 = neutral
    b = lab_image[:, :, 2].astype(np.float32) - 128.0
    chroma = np.sqrt(a * a + b * b)  #distance from neutral = chroma
    mask = chroma > CHROMA_THRESHOLD
    mask_uint8 = mask.astype(np.uint8) * 255
    kernel = np.ones((12, 12), np.uint8)
    closed_gaps = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(
        closed_gaps, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        raise ScanError("no contours found in chroma mask")
    board = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(board)
    corners = np.array(
        [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype=np.float32
    )  # TL, TR, BR, BL by construction

    #if the blob is roughly the full rectangle, hull area ~= box area
    #large difference = merged UI / partial board -> reject
    hull = cv2.convexHull(board)
    fill = cv2.contourArea(hull) / (w * h)
    if fill < MIN_FILL_RATIO:
        raise ScanError(
            f"board blob fills only {fill:.2f} of its bounding box "
            f"(minimum {MIN_FILL_RATIO})"
        )

    return order_corners(corners)


def order_corners(corners: np.ndarray) -> np.ndarray:
    """Order 4 corner points clockwise: TL, TR, BR, BL.

    assumes a roughly axis-aligned rect. 
    x+y is min at TL, max at BR; x-y is max at TR, min at BL.
    """
    s = corners.sum(axis=1)
    d = corners[:, 0] - corners[:, 1]
    return corners[[s.argmin(), d.argmax(), s.argmax(), d.argmin()]]


def warp_board(image: np.ndarray, corners: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Warp the board to a WARP_SIZE x WARP_SIZE square

    Args:
        corners: (4, 2) float32, TL, TR, BR, BL (output of order_corners)

    Returns:
        (warped, homography): the (WARP_SIZE, WARP_SIZE, 3) BGR image and
        the (3, 3) matrix passed to warpPerspective - ScanResult.warp
    """
    destination = np.array(
        [[0, 0], [WARP_SIZE, 0], [WARP_SIZE, WARP_SIZE], [0, WARP_SIZE]],
        dtype=np.float32,
    )
    warp_matrix = cv2.getPerspectiveTransform(corners, destination)
    warped = cv2.warpPerspective(image, warp_matrix, (WARP_SIZE, WARP_SIZE))
    return warped, warp_matrix


def infer_n(warped: np.ndarray) -> int:
    """Infer board size N from gridline projections of the warped board

    Darkness profiles on both axes; interior-line run counting with the
    border zone trimmed (_count_gridlines). Both axes must agree.

    Raises:
        ScanError: axis disagreement, or n outside [4, MAX_N].
    """
    #BGR -> grayscale, inverted so dark gridlines score higher
    darkness = 255 - cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    col_lines = _count_gridlines(darkness.mean(axis=0))
    row_lines = _count_gridlines(darkness.mean(axis=1))

    if col_lines != row_lines:
        raise ScanError(f"axis disagreement: cols={col_lines} rows={row_lines}")
    n = col_lines + 1
    if not (4 <= n <= MAX_N):
        raise ScanError(f"implausible board size n={n}")

    return n


def _count_gridlines(profile: np.ndarray) -> int:
    """Count interior gridlines in a 1-D darkness profile.

    Trims half a minimum cell width off each end so the outer border
    (whole, partial, or absent after the warp) is never counted.
    helper for infer_n; unit-tested with synthetic profiles
    """
    margin = WARP_SIZE // MAX_N // 2
    interior = profile[margin:-margin]

    #threshold between the floor (region-color undulation ~ median) and
    #the spike tops. SPIKE_FRACTION calibrated on fixture profile dumps
    floor = np.percentile(interior, 50)
    peak = interior.max()  #assumes at least one true gridline spike survives trim
    threshold = floor + SPIKE_FRACTION * (peak - floor)
    hot = interior > threshold
    #A line is a run of consecutive True; count run starts (False->True).
    starts = int((np.diff(hot.astype(np.int8)) == 1).sum())
    return starts


def extract_regions(warped: np.ndarray, n: int) -> np.ndarray:
    """Cluster cell-center colors into a region matrix.

    Median patch color per cell -> Lab -> kmeans (k=n, PP centers,
    multiple attempts)

    Returns:
        (n, n) integer region matrix.
    """
    cell = WARP_SIZE / n
    patch_half = int(cell / 6)  #patch = middle third of the cell, clear of gridlines

    samples = np.zeros((n * n, 3), dtype=np.uint8)
    for i in range(n):          
        for j in range(n):     
            cy = int((i + 0.5) * cell)   #row = y
            cx = int((j + 0.5) * cell)   # col = x
            patch = warped[cy - patch_half:cy + patch_half,
                           cx - patch_half:cx + patch_half]
            samples[i * n + j] = np.median(patch.reshape(-1, 3), axis=0)

    #BGR to Lab. cvtColor wants (n*n, 1, 3).
    samples_lab = cv2.cvtColor(
        samples.reshape(-1, 1, 3), cv2.COLOR_BGR2Lab
    ).reshape(-1, 3).astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    _, labels, _ = cv2.kmeans(
        samples_lab, n, None, criteria, attempts=15,
        flags=cv2.KMEANS_PP_CENTERS,
    )
    return labels.reshape(n, n)


def scan(image: np.ndarray) -> ScanResult:
    """Scan a BGR image (as returned by cv2.imread) into a ScanResult

    Composition: find_board -> warp_board -> infer_n -> extract_regions
    -> Puzzle -> ScanResult

    Raises:
        ScanError: no board found, ambiguous grid, or implausible n.
        InvalidPuzzleError: a region matrix was recovered but it is not a
            legal puzzle -- almost always a misread; first line of
            scan-quality defense.
    """
    corners = find_board(image)
    warped, warp_matrix = warp_board(image, corners)
    n = infer_n(warped)
    regions = extract_regions(warped, n)

    puzzle = Puzzle(regions)
    return ScanResult(puzzle=puzzle, corners=corners, warp=warp_matrix, warped_size=WARP_SIZE)