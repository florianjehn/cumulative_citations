# Cumulative yearly citations per paper — implementation plan

## Goal
A single Python script that, given an OpenAlex author ID, produces (a) a PNG figure
showing cumulative yearly citations for that author's top-N most-cited papers
(default N=10), and (b) a CSV of the underlying year-by-paper matrix.

## Stack
Python ≥ 3.10. Dependencies: `requests`, `pandas`, `matplotlib`. Pin versions in a
comment block at the top of the script. No virtualenv assumed; user runs it directly.

## CLI

```
python cumulative_citations.py AUTHOR_ID [--top N] [--output BASENAME] [--email EMAIL]
```

- `AUTHOR_ID`: OpenAlex author ID. Accept any of `A5023888391`,
  `https://openalex.org/A5023888391`, `openalex:A5023888391`. Normalise to bare
  `A\d+` with a regex; reject anything else with a clear error.
- `--top`: integer, default 10. If the author has fewer works than N, use all and
  print a warning.
- `--output`: output basename (no extension). Default
  `{author_id}_{YYYY-MM-DD}`. Writes `{basename}.png` and `{basename}.csv`.
- `--email`: for OpenAlex polite pool. Optional but strongly recommended; print a
  warning if absent.

## Steps

1. **Parse and validate the author ID.** Regex `^(?:.*?)(A\d+)$` against the
   input. Exit with a clear message if no match.

2. **Build a requests Session.** Set a 30 s timeout. Implement a small retry helper
   that retries up to 3 times on HTTP 429 and 5xx with exponential backoff
   (1 s, 2 s, 4 s). Include `mailto={email}` in query params on every request if
   provided.

3. **Fetch author metadata.** `GET /authors/{id}`. Keep `display_name` for the
   figure title. Exit cleanly on 404 with "Author {id} not found".

4. **Fetch all works by the author.** Use cursor pagination:
   `GET /works?filter=author.id:{id}&per-page=200&cursor={cursor}&select=id,display_name,publication_year,cited_by_count,counts_by_year,authorships,doi`.
   Start with `cursor=*`, follow `meta.next_cursor` until null. Aggregate to a list.
   Exit with a clear message if zero works returned.

5. **Select top N papers.** Sort works by `cited_by_count` descending; slice to N.
   Tie-break by `publication_year` ascending (older first) for stability.

6. **Build cumulative yearly series per paper.**
   - For each selected work, convert `counts_by_year` (list of
     `{year, cited_by_count}`) into a pandas Series indexed by year.
   - Compute `pre_window = cited_by_count - sum(yearly_counts)`. If positive,
     prepend it to the earliest visible year. This makes the cumulative end at the
     true total. Track which papers had pre-window citations (for annotation).
   - Take cumulative sum.
   - Reindex onto the full year range from `min(publication_year across selected)`
     to `current_year`, forward-filling and zero-filling appropriately so all
     papers share an x-axis.

7. **Assemble a wide DataFrame.** Index = year, columns = short paper labels
   (see step 9). Save as CSV with `index_label="year"`.

8. **Generate short labels.** `short_label(work)` returns
   `"{surname} {year} — {truncated_title}"`, total ≤ 35 chars. Surname = last
   whitespace-separated token of `authorships[0].author.display_name`. Note the
   limitation: this is fragile for "van der" etc. — document but don't try to fix.
   Truncate title with an ellipsis. Ensure uniqueness by appending a numeric suffix
   if two labels collide.

9. **Plot.**
   - `plt.style.use("https://raw.githubusercontent.com/florianjehn/Scientific-Repository-Template/refs/heads/main/style/scientific.mplstyle")`
   - One line per paper. Line width ~1.5. Use a colour-blind-safe qualitative
     palette (e.g. Okabe–Ito or matplotlib's `tab10`).
   - **No legend.** Direct labels at the line's right endpoint via `ax.annotate`,
     horizontal text, small horizontal offset (e.g. 5 pt).
   - **Label collision avoidance.** After plotting, sort labels by end-y; iterate
     bottom-up, ensure each is at least 3% of y-range above the previous; push up
     if needed. Keep it simple — greedy, no optimisation library.
   - X-axis: year, integer ticks. Y-axis: "Cumulative citations". Title:
     author display name. Subtitle (small grey text under title): "Top {N} papers
     by total citations".
   - **Source annotation** lower-right of axes:
     `"Data: OpenAlex, retrieved {YYYY-MM-DD}"`.
   - **Pre-window note**: if any selected paper had `pre_window > 0`, add a small
     italic note under the source annotation:
     `"* paper(s) marked † include citations accumulated before OpenAlert's
     yearly-counts window"`, and append a † to the label of any such paper.
   - Save PNG at 300 dpi, `bbox_inches="tight"`.

10. **Stdout summary.** Print: author name, number of works retrieved, total
    citations across top N, output paths.

## Function structure

```python
def parse_author_id(raw: str) -> str: ...
def make_session(email: str | None) -> requests.Session: ...
def get_with_retry(session, url, params) -> dict: ...
def fetch_author(author_id: str, session, params) -> dict: ...
def fetch_works(author_id: str, session, params) -> list[dict]: ...
def short_label(work: dict) -> str: ...
def build_cumulative_dataframe(works: list[dict], top_n: int) -> tuple[pd.DataFrame, set[str]]: ...
    # returns (df, set_of_labels_with_prewindow_citations)
def plot_cumulative(df: pd.DataFrame, author_name: str, prewindow_labels: set[str], output_path: Path) -> None: ...
def main() -> None: ...
```

Every function gets a docstring: one-line description, `Arguments:` with types,
`Returns:` with type.

## Error handling
- 404 on author → exit 1, clear message.
- 429 / 5xx → handled by retry helper; if all retries fail, exit 2 with last
  status code.
- Empty works list → exit 0 with informational message; no file written.
- Network failure (no connectivity) → catch `requests.ConnectionError`, exit 3.
- Missing `counts_by_year` field → treat as empty list (don't crash).

## Known limitations to surface in the script's `--help` and docstring
1. `counts_by_year` is yearly only and roughly bounded to recent ~11 years; older
   citations are folded into the starting point of the visible series.
2. First-author surname extraction is naive (last whitespace token).
3. Author disambiguation relies entirely on the supplied OpenAlex ID; no
   name-based fallback.
4. Citation counts at OpenAlex lag real publication activity by weeks to months.

## Suggested manual test
Run against a moderately prolific author with mixed-age publications (e.g. a
mid-career academic with ~50 works, several pre-2015 papers). Verify:
- top 10 papers match the OpenAlex author page sorted by citations
- the latest year's cumulative value equals `cited_by_count` for each line
- pre-2014 papers carry the † marker
- the figure renders with the scientific.mplstyle (sans-serif, no top/right
  spines)

## Out of scope (do not implement)
- Monthly resolution (planned follow-up; would require fetching all citing works
  via `cites:W...` and bucketing by their `publication_date`).
- Author name search / disambiguation.
- Multi-author comparison.
- Caching layer.
