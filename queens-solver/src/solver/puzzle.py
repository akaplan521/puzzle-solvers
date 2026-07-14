from collections import deque  #for BFS flood fill
import numpy as np #for puzzle arrays


class InvalidPuzzleError(ValueError):
    pass


class Puzzle:
    """a validated Queens puzzle
    2-D integer array
    ex:
        puzzle = Puzzle([
            [0, 0, 1],
            [0, 2, 1],
            [2, 2, 1],
        ])
    InvalidPuzzleError if the grid is not a valid puzzle.
    """

    def __init__(self, regions):
        #converting input to a numpy array and validating it
        self.regions = np.asarray(regions)
        self._validate()

    @property
    def n(self):
        return self.regions.shape[0]
        #shape returns a tuple of (n,m)


    def _validate(self):
        self._check_shape()
        self._check_values()
        self._check_region_set()
        self._check_contiguity()

    def _check_shape(self):
        if self.regions.ndim != 2: #if regions array dimensins not equal 2
            raise InvalidPuzzleError(
                f"{self.regions.ndim} dimensions, expected 2"
            )
        rows, cols = self.regions.shape
        if rows != cols: #not square; uneven rows and cols
            raise InvalidPuzzleError(
                f"{self.regions.shape} shape"
            )
        if rows < 1: 
            raise InvalidPuzzleError("empty puzzle")
        elif rows < 2:
            raise InvalidPuzzleError("puzzle too small")

    def _check_values(self):
        if not np.issubdtype(self.regions.dtype, np.integer): #checks all value types and compares with int
            raise InvalidPuzzleError("all regions must be ints")

    def _check_region_set(self):
        unique_regions = np.unique(self.regions) #unique region ids
        if len(unique_regions) != self.n: #making sure all region ids exist
            raise InvalidPuzzleError(
                f"expected {self.n} regions, found {len(unique_regions)}"
            )
        if unique_regions[0] != 0 or unique_regions[-1] != self.n - 1: #id out of range
            raise InvalidPuzzleError(
                f"region ids must be 0..{self.n - 1}, found {unique_regions.tolist()}"
            )

    def _check_contiguity(self):
        for k in range(self.n): #iterate through regions
            cells = np.argwhere(self.regions == k)  #all cells belonging to region k
            total_count = len(cells) #expected size of region k
            start_row, start_col = cells[0] #arbitrary starting cell for the flood fill
            reached = self._flood_fill_count(start_row, start_col)
            if reached < total_count: #fewer cells reached than exist means region k is split apart
                raise InvalidPuzzleError(f"region {k} is not contiguous")

    def _flood_fill_count(self, start_row, start_col):
        #BFS staying within the same region_id to count connected cells reachable from starting cell
        region_id = self.regions[start_row, start_col]
        visited = {(start_row, start_col)}
        queue = deque([(start_row, start_col)])
        while queue:
            row, col = queue.popleft()
            for d_row, d_col in ((-1, 0), (1, 0), (0, -1), (0, 1)): #up down left right cells
                r, c = row + d_row, col + d_col
                if not (0 <= r < self.n and 0 <= c < self.n): #skip out-of-bounds neighbors
                    continue
                if (r, c) in visited: #skip cells already counted
                    continue
                if self.regions[r, c] != region_id: #skip cells belonging to a different region
                    continue
                visited.add((r, c))
                queue.append((r, c))
        return len(visited) #total cells reachable from the start within region_id