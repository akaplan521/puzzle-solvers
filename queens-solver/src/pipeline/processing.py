from dataclasses import dataclass
from enum import Enum, auto

import numpy as np
import cv2

from solver.puzzle import InvalidPuzzleError
from solver.solve import solve, SolveStatus
from vision.scan import scan, ScanError

CROWN_UNIT = np.array([
    [-0.42,  0.35],   #bottom-left
    [-0.42, -0.30],   #left spike tip
    [-0.16,  0.00],   #valley
    [ 0.00, -0.45],   #middle spike tip; slightly taller
    [ 0.16,  0.00],   #valley
    [ 0.42, -0.30],   #right spike tip
    [ 0.42,  0.35],   #bottom-right
], dtype=np.float32)

CROWN_RATIO = 0.55  
CROWN_COLOR = (43, 200, 239)   
CROWN_OUTLINE = (30, 60, 90)

class PipelineStatus(Enum):
    OK = auto()
    SCAN_FAILED = auto()        
    INVALID_PUZZLE = auto()    
    NOT_UNIQUE = auto() 
    UNSAT = auto()


    @property
    def message(self) -> str:
        return _MESSAGES[self]


_MESSAGES = {
    PipelineStatus.OK: "Solved.",
    PipelineStatus.SCAN_FAILED: "Image could not be scanned into a puzzle.", 
    PipelineStatus.INVALID_PUZZLE: "Grid is not a valid puzzle.",
    PipelineStatus.NOT_UNIQUE: "Puzzle solution is not unique.",
    PipelineStatus.UNSAT: "Puzzle solution does not exist.",
}


@dataclass(frozen=True)
class PipelineResult:
    status: PipelineStatus
    image: np.ndarray | None = None      
    solution: np.ndarray | None = None  

    def __post_init__(self):
        #raise ValueError on bad combination
        is_ok = self.status == PipelineStatus.OK
        has_image, has_sol = self.image is not None, self.solution is not None
        if ((is_ok and not (has_image and has_sol)) or (not is_ok and (has_sol or has_image))):
            raise ValueError(f"Status: {self.status} Image exists: {has_image} Solution exists: {has_sol}")
        

def draw_overlay(image: np.ndarray,
                 cell_centers: np.ndarray,
                 solution: np.ndarray) -> np.ndarray:
    """Pure: returns an annotated COPY of image; never mutates the input.

    cell_centers: (n, n, 2) original-image coords from ScanResult.cell_centers()
    solution: the solver's queen matrix
    """
    image_copy = image.copy()

    cell_dist = abs(float(cell_centers[0, 1, 0] - cell_centers[0, 0, 0]))
    size = cell_dist * CROWN_RATIO

    for row, col in np.argwhere(solution):
        center = cell_centers[row, col]  #(x, y) float32
        pts = (CROWN_UNIT * size + center).astype(np.int32)
        cv2.fillPoly(image_copy, [pts], CROWN_COLOR)
        cv2.polylines(image_copy, [pts], isClosed=True,
                      color=CROWN_OUTLINE, thickness=2)

    return image_copy

def process(image: np.ndarray) -> PipelineResult:
    """image: BGR ndarray (decoding bytes is the caller's job).

    Catches ONLY ScanError and InvalidPuzzleError. Anything else is a
    bug and must propagate loudly.
    """
    try:
        scan_result = scan(image)
    except ScanError: 
        return PipelineResult(PipelineStatus.SCAN_FAILED)
    except InvalidPuzzleError:
        return PipelineResult(PipelineStatus.INVALID_PUZZLE)
    
    solve_status, solution = solve(scan_result.puzzle)

    if solve_status == SolveStatus.MULTIPLE:
        return PipelineResult(PipelineStatus.NOT_UNIQUE)
    elif solve_status == SolveStatus.UNSAT:
        return PipelineResult(PipelineStatus.UNSAT)
    
    overlayed = draw_overlay(image, scan_result.cell_centers(), solution)
    return PipelineResult(PipelineStatus.OK, overlayed, solution)