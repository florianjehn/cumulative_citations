# Scientific-Repository-Template

A template for scientific Python projects. Use this as a starting point by clicking **"Use this template"** in the top right.

---

## How to use this template

1. Create a new repository from this template.
2. Update `pyproject.toml` — change the `name`, `description`, and dependencies.
3. Update `README.md` — describe your specific project.
4. Set up your environment: `uv sync`
5. Start coding in `src/`, write tests in `tests/`, and put notebooks in `notebooks/`.

---

## Python Style Guide

All code should follow the [PEP 8 Style Guide](https://peps.python.org/pep-0008/). Key rules:

- **Document every function** with a docstring in this format:

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

- **Write decoupled code**: functions do exactly one thing and are as short as possible. See [here](https://goodresearch.dev/decoupled.html).
- **Naming conventions**:
  - `snake_case` for variables, functions, and modules
  - `CamelCase` for class names
  - `Camel Case With Spaces.ipynb` for Jupyter notebooks
- **Delete dead code.** Do not comment out unused code — use git to find it again.
- **Most code lives in `.py` files.** Notebooks (in `notebooks/`) are for final visualizations and explanations only.

Code is automatically checked with [Ruff](https://docs.astral.sh/ruff/) (formatting, linting, and import sorting) on every push via GitHub Actions. If linting fails, merges are blocked. Pre-commit hooks run Ruff locally before each commit — install with `uv run pre-commit install`.

---

## Environment Management

Every project uses its own virtual environment managed by **[UV](https://docs.astral.sh/uv/)**.

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Set up the project environment
uv sync

# Run code
uv run python src/my_module.py

# Run tests
uv run pytest

# Add a dependency
uv add pandas
```

All dependencies are defined in `pyproject.toml`. The `.python-version` file pins the Python version.

Do **not** use conda, mamba, or bare pip for this project.

---

## Testing

Use [pytest](https://docs.pytest.org/) for all tests. Every reasonable function should have a test. Tests live in `tests/` and are automatically run on every push.

```bash
uv run pytest
```

See `tests/test_function_to_test.py` for an example. Add a testing badge to your repository README by changing the URL:

![Testing](https://github.com/your-org/your-repo/actions/workflows/testing.yml/badge.svg)

---

## Plotting Style

All plots use the project style sheet located at `style/scientific.mplstyle`:

```python
import matplotlib.pyplot as plt

plt.style.use("style/scientific.mplstyle")
```

Key properties: primary color `#573280`, figure size 10×4, display DPI 150, save DPI 300.

---

## Map Plots

For published maps, use the **Winkel Tripel projection** and the included border file at `data/border.geojson`:

```python
import geopandas as gpd
import matplotlib.pyplot as plt

plt.style.use("style/scientific.mplstyle")

def plot_winkel_tripel_map(ax):
    border_geojson = gpd.read_file("data/border.geojson")
    border_geojson.plot(ax=ax, edgecolor="black", linewidth=0.1, facecolor="none")
    ax.set_axis_off()

world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
world = world.to_crs("+proj=wintri")
ax = world.plot()
plot_winkel_tripel_map(ax)
plt.show()
```

**Note**: Winkel Tripel is for visual display only — use an appropriate projection for spatial calculations.

---

## Documentation

- Every repository needs a `README.md` that explains:
  - What the repository is for
  - Installation instructions
  - How the code is organized
  - Links to papers (if applicable)
  - License
- Consider adding a tutorial notebook in `notebooks/` to demonstrate usage.

---

## Making the Repository Citable

Use [Zenodo](https://zenodo.org/) to create a DOI for your repository. Once activated, add a DOI badge to your README:

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)

---

## Project Structure

```
├── data/               # Raw input data (usually not synced to git for large files)
│   └── border.geojson  # Winkel Tripel map border
├── docs/               # Documentation files
├── notebooks/          # Jupyter notebooks for visualization and explanation
├── results/            # Output files: figures, tables, checkpoints (large files gitignored)
├── src/                # Reusable Python modules (imported by notebooks and scripts)
├── style/
│   └── scientific.mplstyle  # Matplotlib style sheet
├── tests/              # pytest test suite
├── .python-version     # Python version for UV
├── pyproject.toml      # Project metadata and dependencies
└── CLAUDE.md           # Rules for AI coding assistants
```

---

## License

[Apache 2.0](LICENSE) — free to use with liability protection.

---

## Further Reading

- [Good Research Code Handbook](https://goodresearch.dev/index.html)
- [Best Practices for Scientific Computing](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.1001745)
- [UV Documentation](https://docs.astral.sh/uv/)
