# CLAUDE.md

This file defines the rules and conventions for this project. All rules here are mandatory.

You obsessively plan, audit and implement using the totality of your skills and elegance. Think holistically through this from first-principles. Be methodical, genius, high effort - high touch. Execute elegantly, impeccably, thoroughly, production-grade. Don’t waste time optimizing something that shouldn’t exist, ask yourself the hard questions and audit any conclusions. Elegant interventions that break nothing. Robust and scalable.

---

## CRITICAL WORKFLOW REQUIREMENTS

**THESE RULES ARE NON-NEGOTIABLE.**

1. **NEVER claim something works without running a test to prove it.** After writing any code, immediately write and run a test. If you cannot test it, say so explicitly.

2. **Work modularly.** Complete one module at a time. After each module, report what you built, show test results, and wait for confirmation before proceeding.

3. **Iterate and fix errors yourself.** Do not rely on the user to report errors back to you. Run the code, observe the output, and fix problems before presenting results.

4. **Be explicit about unknowns.** If you're uncertain about something, say so. Don't guess.

5. **Use `python3` and `pip3`.** Never use `python` or `pip` directly.

---

## Environment & Dependency Management

- **Always use [UV](https://docs.astral.sh/uv/)** for all package and environment management. Never use conda, mamba, or bare pip.
- Every repository must have its own virtual environment managed by UV (lives in `.venv/`, gitignored).
- Common commands:
  - `uv sync` — install all dependencies from `pyproject.toml`
  - `uv run python script.py` — run a script inside the project environment
  - `uv run pytest` — run tests
  - `uv add <package>` — add a new dependency

---

## Python Style Guide

Follow [PEP 8](https://peps.python.org/pep-0008/). Key rules:

### Docstrings

Every function needs a docstring in this exact format:

```python
def count_line(f, line):
    """
    Counts the number of times a line occurs. Case-sensitive.

    Arguments:
        f (file): the file to scan
        line (str): the line to count

    Returns:
        int: the number of times the line occurs.
    """
```

### Naming Conventions

| Thing | Style | Example |
|---|---|---|
| Variables, functions, modules | snake_case | `my_variable`, `my_module.py` |
| Classes | CamelCase | `MyClass` |
| Jupyter notebooks | Camel Case With Spaces | `Analyze Results.ipynb` |

### Code Quality Rules

- Write decoupled code: each function does exactly one thing and is as short as possible.
- Delete dead code. Never comment out unused code — use git history to recover it.
- No commented-out code blocks.
- Use `print()` for any logging output. Do not use the `logging` module.

### Code Organization

- All reusable logic goes in `.py` files under `src/`.
- Jupyter notebooks (in `notebooks/`) are for final visualizations and explanations only — not for implementing logic.

---

## Testing

- **Always read existing tests before writing new ones.**
- Use `pytest` for all tests. Tests live in `tests/`.
- Every reasonable function should have at least one test.
- Run tests with: `uv run pytest`
- Never claim code works without running the tests and showing passing output.

---

## Plotting Style

**Always apply the project style sheet before creating any plot:**

```python
import matplotlib.pyplot as plt

plt.style.use("style/scientific.mplstyle")
```

The style sheet is at `style/scientific.mplstyle`. It must be applied to every plot — no exceptions. Key properties:

- Primary color: `#573280` (deep violet)
- Figure size: 10 × 4 inches
- Display DPI: 150 / Save DPI: 300
- Grid: on, alpha 0.4
- Color cycle: 15 colors starting with deep violet, burnt orange, cerulean, ...

---

## Map Plots

For published maps, use the **Winkel Tripel projection** and the included border file:

```python
import geopandas as gpd
import matplotlib.pyplot as plt

plt.style.use("style/scientific.mplstyle")

def plot_winkel_tripel_map(ax):
    """
    Adds the Winkel Tripel border and removes axes decorations.

    Arguments:
        ax (matplotlib.axes.Axes): the axes to modify

    Returns:
        None
    """
    border_geojson = gpd.read_file("data/border.geojson")
    border_geojson.plot(ax=ax, edgecolor="black", linewidth=0.1, facecolor="none")
    ax.set_axis_off()

world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
world = world.to_crs("+proj=wintri")
ax = world.plot()
plot_winkel_tripel_map(ax)
plt.show()
```

The border file is at `data/border.geojson`.

**Important**: Winkel Tripel is for visual display only — it does not preserve area, angle, or distance. Use an appropriate projection for any spatial calculations.

---

## Code Formatting & Linting

All code is automatically checked on push via GitHub Actions (lint + test run as separate jobs in `.github/workflows/ci.yml`):

- **Ruff** — formatting, style checks, and import sorting in one tool (replaces Black, Flake8, isort)
- **pytest** — test suite

Pre-commit hooks also run Ruff locally before each commit. Install them once with:

```bash
uv run pre-commit install
```

Fix all linting errors before pushing. Failing checks block merges.
