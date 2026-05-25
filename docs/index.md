# Scientific-Repository-Template

Use this as a template when starting a new project by clicking "Use this template" in the top right.

## Python Style Guide

All code should follow the [PEP 8 Style Guide](https://peps.python.org/pep-0008/). Key rules:

- Every function needs a docstring in this format:

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

- Write [decoupled code](https://goodresearch.dev/decoupled.html): functions do exactly one thing and are as short as possible.
- Naming conventions:
  - `snake_case` for variables and modules
  - `CamelCase` for class names
  - `Camel Case With Spaces.ipynb` for Jupyter notebooks
- Delete dead code. Do not comment out unused code — use git to recover it.
- Use Jupyter notebooks only for explanations and visualization. Logic lives in `.py` files.
- Code is automatically checked with [Ruff](https://docs.astral.sh/ruff/) (formatting, linting, import sorting) via GitHub Actions.

## Testing

Use [pytest](https://docs.pytest.org/) for all tests. Tests live in `tests/` and run automatically on every push. See `tests/test_example.py` for an example.

## Environment Management

Every project uses [UV](https://docs.astral.sh/uv/) for dependency and environment management. Dependencies are defined in `pyproject.toml`.

```bash
uv sync        # install dependencies
uv run pytest  # run tests
```

## Plotting Style

Apply the project style sheet before any plot:

```python
import matplotlib.pyplot as plt
plt.style.use("style/scientific.mplstyle")
```

## Project Structure

| Folder | Purpose |
|--------|---------|
| `src/` | Reusable Python modules |
| `tests/` | pytest test suite |
| `notebooks/` | Jupyter notebooks for visualization/explanation |
| `data/` | Raw input data |
| `results/` | Output files (figures, tables) |
| `style/` | Matplotlib style sheet |
| `docs/` | Documentation |

## License

[Apache 2.0](../LICENSE)

## Further Reading

- [Good Research Code Handbook](https://goodresearch.dev/index.html)
- [Best Practices for Scientific Computing](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.1001745)
