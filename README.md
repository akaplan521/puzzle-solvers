# Queens Puzzle Solver

Solves [LinkedIn's daily Queens puzzle](https://www.linkedin.com/games/queens/) from a screenshot: finds the board, reads the color regions, solves the puzzle with constraint programming, and draws the solution back onto the original image.

<!-- IMAGE: overlay result — a solved board with crowns drawn on. This is the
     money shot; put it here, full width, nothing above it but the title. -->
![Solved puzzle with the solution overlaid](docs/solved.png)

**[Live demo](https://queens-solver-daly.onrender.com/)** — hosted on a free tier, so the first load takes about a minute to wake the server.

---

## The puzzle

An N×N grid divided into N colored regions. Place one queen in every row, every column, and every colored region, and no two queens may touch — including diagonally. Every valid puzzle has exactly one solution.

<!-- IMAGE: an unsolved board next to its solution, or a single annotated board
     showing the rules. Small, side by side if you can. -->
![An unsolved board and its unique solution](docs/unsolved.png)


## The hard part is the vision

The constraint model is only about 20 lines. Recovering the puzzle from a screenshot is the bulk of the project.

### 1. Find the board

The board is the only large saturated object in the screenshot, so it's isolated by **chroma** — distance from neutral in Lab color space — rather than by brightness or hue. A morphological close merges the individual cells into one blob, and the largest contour's bounding rectangle gives the corners.

A fill-ratio check rejects the result if the blob doesn't roughly fill its bounding box, which catches the case where surrounding UI gets merged into the board.

<!-- IMAGE: the chroma mask -->
![Chroma mask isolating the board](docs/chroma_mask.png)

### 2. Warp to a canonical square

A perspective transform maps those four corners to a fixed-size square. Every later stage works in warped space, where cell boundaries are at predictable coordinates and the geometry is trivial — the homography is kept so the solution can be projected back afterward.


### 3. Infer the board size

Board size isn't known in advance. The warped board is converted to a darkness profile along each axis; interior gridlines show up as spikes above the floor of region-color variation. Counting runs above a threshold gives the number of interior lines, and therefore N.

Both axes must agree. Disagreement means the grid was misread, and the scan fails.

<!-- IMAGE: the darkness profile plot with the threshold line drawn across it.
     This one explains itself better than any paragraph can. -->
![Darkness profile with gridline spikes rows](docs/gridline_profile.png)
![Darkness profile with gridline spikes cols](docs\09_col_profile.png)

### 4. Recover the regions

Each cell's color is sampled from a patch at its center, clear of the gridlines, using the median to resist antialiasing. Those colors are converted to Lab and clustered with k-means at k = N.

Setting k = N asserts that the number of color regions equals the board size. The puzzle's rules guarantee it, but a misread board can violate it, which is caught.

### 5. Solve and project back

The region matrix becomes a `Puzzle`, which validates on construction — shape, region completeness, and BFS contiguity of each region. An invalid puzzle can't be constructed, so every `Puzzle` is known valid.

The solver (CPMpy over CP-SAT) places one queen per row, column, and region with no two adjacent, then adds a blocking clause excluding that solution and solves again. A second solution means the scan was wrong, since valid solutions are unique.

The inverse homography maps cell centers back to original-image coordinates, and the crowns are drawn there — so the overlay lands on the user's screenshot.

## Architecture

```
image → scan → solve → overlay
```

```
src/
├── solver/      # Puzzle data model, CP model, uniqueness check
├── vision/      # Screenshot → region matrix
├── pipeline/    # Composition + cross-cutting failure policy
└── web/         # FastAPI adapter + static frontend
```

Dependency points one direction. The pipeline layer owns composition and failure policy; the web layer is a minimal HTTP adapter. pytest and uvicorn are interchangeable callers of the same functions.

### Expected failures are data; unexpected failures are bugs

The pipeline catches exactly two exceptions — a failed scan and an invalid puzzle — and maps non-unique solver results to their own statuses. Everything else propagates. Catching broadly would disguise real defects as ordinary scan failures and throw away the traceback at the moment it was created.

Each failure mode gets its own message: a bad scan means retake the screenshot, a non-unique solution means a cell was misread.

Results carry a coherence invariant, enforced at construction: success implies both an image and a solution are present, and any failure implies neither is. An incoherent result raises immediately at construction rather than surfacing as `None` somewhere.


## Tests

Fixture screenshots paired with hand-typed region matrices; the scan is verified against known grids. Grid inference is unit-tested with synthetic profiles. Pipeline success is verified by asserting the solution's properties — one queen per row, column, and region, none adjacent — rather than by comparing to a stored answer.

Solved or partially solved boards are deliberately excluded as fixtures for the color pipeline, since pre-placed queens change the cell colors being clustered.

## Running it

```bash
pip install -e ".[dev]"
uvicorn web.app:app --reload     # http://localhost:8000
pytest
```

Deployed on Render's free tier. The app is stateless, so spinning down costs nothing but the wake-up.

## Roadmap

**Tango** — Queens was never meant to be the only solver. Tango's constraints are simpler, but its board detection needs a different approach since the grid has no color regions to find, and its constraint symbols sit on cell boundaries rather than in cells.