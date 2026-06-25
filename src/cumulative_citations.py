#!/usr/bin/env python3
"""
Plot cumulative yearly citations for an OpenAlex author's top-N papers.

Known limitations:
    1. counts_by_year covers only ~11 recent years; older citations appear as a
       lump sum at the start of the visible series.
    2. Surname extraction uses the last whitespace token and is fragile for
       compound names like 'van der X'.
    3. Author disambiguation relies entirely on the supplied OpenAlex ID.
    4. Citation counts at OpenAlex lag real publication activity by weeks to months.

Usage:
    python src/cumulative_citations.py AUTHOR_ID [--top N] [--output BASENAME]
        [--email EMAIL]

Dependencies: requests>=2.31, pandas>=2.0, matplotlib>=3.8
"""

import argparse
import re
import sys
import time
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests

OPENALEX_BASE = "https://api.openalex.org"
_STYLE_PATH = Path(__file__).parent.parent / "style" / "scientific.mplstyle"


def parse_author_id(raw: str) -> str:
    """
    Extracts a bare OpenAlex author ID from various input formats.

    Arguments:
        raw (str): user input, e.g. 'A5023888391',
            'https://openalex.org/A5023888391', or 'openalex:A5023888391'

    Returns:
        str: bare author ID, e.g. 'A5023888391'
    """
    match = re.search(r"(A\d+)$", raw.strip())
    if not match:
        print(
            f"Error: cannot parse an OpenAlex author ID from '{raw}'.",
            file=sys.stderr,
        )
        print(
            "Accepted formats: A5023888391, https://openalex.org/A5023888391, "
            "openalex:A5023888391",
            file=sys.stderr,
        )
        sys.exit(1)
    return match.group(1)


def make_session(email: str | None) -> requests.Session:
    """
    Creates a requests Session; adds mailto to every request for the polite pool.

    Arguments:
        email (str | None): contact email for the OpenAlex polite pool, or None

    Returns:
        requests.Session: configured session with optional mailto param
    """
    session = requests.Session()
    if email:
        session.params = {"mailto": email}  # type: ignore[assignment]
    return session


def get_with_retry(session: requests.Session, url: str, params: dict) -> dict | None:
    """
    Makes a GET request with exponential-backoff retry on HTTP 429 and 5xx.

    Arguments:
        session (requests.Session): the HTTP session
        url (str): request URL
        params (dict): per-request query parameters

    Returns:
        dict | None: parsed JSON response body, or None on HTTP 404
    """
    delays = [1, 2, 4]
    last_status = None
    for attempt in range(len(delays) + 1):
        try:
            resp = session.get(url, params=params, timeout=30)
        except requests.ConnectionError as exc:
            print(f"Network error: {exc}", file=sys.stderr)
            sys.exit(3)

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            return None
        if resp.status_code == 429 or resp.status_code >= 500:
            last_status = resp.status_code
            if attempt < len(delays):
                time.sleep(delays[attempt])
                continue
            print(
                f"Request failed after {len(delays)} retries. "
                f"Last status: {last_status}",
                file=sys.stderr,
            )
            sys.exit(2)
        print(f"Unexpected HTTP {resp.status_code} from {url}", file=sys.stderr)
        sys.exit(2)
    return None  # unreachable


def fetch_author(author_id: str, session: requests.Session, params: dict) -> dict:
    """
    Fetches author metadata from OpenAlex; exits with code 1 on 404.

    Arguments:
        author_id (str): bare OpenAlex author ID, e.g. 'A5023888391'
        session (requests.Session): the HTTP session
        params (dict): base query parameters

    Returns:
        dict: author metadata including 'display_name'
    """
    url = f"{OPENALEX_BASE}/authors/{author_id}"
    data = get_with_retry(session, url, params)
    if data is None:
        print(f"Author {author_id} not found.", file=sys.stderr)
        sys.exit(1)
    return data


def fetch_works(author_id: str, session: requests.Session, params: dict) -> list[dict]:
    """
    Fetches all works by an author via OpenAlex cursor pagination.

    Arguments:
        author_id (str): bare OpenAlex author ID
        session (requests.Session): the HTTP session
        params (dict): base query parameters

    Returns:
        list[dict]: all work records for the author
    """
    url = f"{OPENALEX_BASE}/works"
    page_params = {
        **params,
        "filter": f"author.id:{author_id}",
        "per-page": 200,
        "select": (
            "id,display_name,publication_year,cited_by_count,"
            "counts_by_year,authorships,doi"
        ),
        "cursor": "*",
    }
    works: list[dict] = []
    while True:
        data = get_with_retry(session, url, page_params)
        if data is None:
            break
        works.extend(data.get("results", []))
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor:
            break
        page_params = {**page_params, "cursor": next_cursor}
    return works


def filter_first_author(works: list[dict], author_id: str) -> list[dict]:
    """
    Keeps only works where the given author is the first author.

    Arguments:
        works (list[dict]): OpenAlex work records, each with an 'authorships' list
        author_id (str): bare OpenAlex author ID to match, e.g. 'A5076268002'

    Returns:
        list[dict]: works whose first authorship belongs to author_id, matched by
            the authorship's 'author_position' == 'first' and the author ID suffix
    """
    first_author_works: list[dict] = []
    for work in works:
        for authorship in work.get("authorships") or []:
            if authorship.get("author_position") != "first":
                continue
            full_id = (authorship.get("author") or {}).get("id") or ""
            if full_id.rsplit("/", 1)[-1] == author_id:
                first_author_works.append(work)
            break
    return first_author_works


def _title_key(work: dict) -> str:
    """
    Normalises a work's title for matching duplicates across versions.

    Arguments:
        work (dict): OpenAlex work record with a 'display_name' field

    Returns:
        str: the title lowercased with surrounding and repeated whitespace
            collapsed; empty string if the work has no usable title
    """
    title = (work.get("display_name") or "").strip()
    return re.sub(r"\s+", " ", title).lower()


def merge_duplicate_titles(works: list[dict]) -> list[dict]:
    """
    Merges works that share the same title into one combined record.

    A preprint and its published version usually appear as separate OpenAlex
    works carrying the same title. This groups works by their normalised title
    (see _title_key) and, for each group of two or more, sums cited_by_count and
    counts_by_year so the pair counts as a single paper. The earliest
    publication_year is kept (citations begin accruing from the preprint) and
    the remaining metadata is taken from the most-cited member of the group.
    Insertion order of the first occurrence of each title is preserved.

    Arguments:
        works (list[dict]): OpenAlex work records, each with 'display_name',
            'publication_year', 'cited_by_count', and 'counts_by_year' fields

    Returns:
        list[dict]: works with same-title duplicates merged into single records;
            works without a usable title are passed through unchanged
    """
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for index, work in enumerate(works):
        key = _title_key(work) or f"__notitle__{index}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(work)

    merged: list[dict] = []
    for key in order:
        group = groups[key]
        if len(group) == 1:
            merged.append(group[0])
            continue

        representative = max(group, key=lambda w: w.get("cited_by_count") or 0)
        combined = dict(representative)
        combined["cited_by_count"] = sum(w.get("cited_by_count") or 0 for w in group)

        pub_years = [
            w.get("publication_year") for w in group if w.get("publication_year")
        ]
        if pub_years:
            combined["publication_year"] = min(pub_years)

        yearly_totals: dict[int, int] = {}
        for w in group:
            for entry in w.get("counts_by_year") or []:
                year = int(entry["year"])
                yearly_totals[year] = yearly_totals.get(year, 0) + int(
                    entry["cited_by_count"]
                )
        combined["counts_by_year"] = [
            {"year": year, "cited_by_count": count}
            for year, count in sorted(yearly_totals.items(), reverse=True)
        ]
        merged.append(combined)

    return merged


def short_label(work: dict) -> str:
    """
    Generates a short display label: '{surname} {year} — {truncated_title}'.

    Arguments:
        work (dict): OpenAlex work record with 'authorships', 'publication_year',
            and 'display_name' fields

    Returns:
        str: label at most 35 characters, with '…' if title is truncated.
            Surname is the last whitespace-separated token of the first author's
            display_name, which is fragile for compound surnames like 'van der X'.
    """
    authorships = work.get("authorships") or []
    if authorships:
        author_name = authorships[0].get("author", {}).get("display_name", "Unknown")
        surname = author_name.split()[-1]
    else:
        surname = "Unknown"

    year = work.get("publication_year", "????")
    title = work.get("display_name") or ""

    prefix = f"{surname} {year} — "
    max_title_len = 35 - len(prefix)
    if max_title_len <= 0:
        return prefix[:35]
    if len(title) > max_title_len:
        title = title[: max_title_len - 1] + "…"

    return f"{prefix}{title}"


def build_cumulative_dataframe(
    works: list[dict], top_n: int
) -> tuple[pd.DataFrame, set[str], dict[str, int]]:
    """
    Selects the top-N most-cited works and builds a cumulative yearly citation
    DataFrame.

    Arguments:
        works (list[dict]): all OpenAlex work records for the author
        top_n (int): number of top papers to select

    Returns:
        tuple[pd.DataFrame, set[str], dict[str, int]]: wide DataFrame
            (index=years_since_publication, columns=paper labels),
            set of column labels whose papers carried pre-window citations,
            and dict mapping each label to its age (current_year - pub_year)
    """
    sorted_works = sorted(
        works,
        key=lambda w: (-w.get("cited_by_count", 0), w.get("publication_year") or 0),
    )
    selected = sorted_works[:top_n]

    seen: dict[str, int] = {}
    labels: list[str] = []
    for work in selected:
        base = short_label(work)
        if base not in seen:
            seen[base] = 0
            labels.append(base)
        else:
            seen[base] += 1
            labels.append(f"{base} ({seen[base]})")

    current_year = date.today().year
    pub_years = [
        w.get("publication_year") for w in selected if w.get("publication_year")
    ]
    max_age = max(current_year - py for py in pub_years) if pub_years else 0
    all_ages = list(range(0, max_age + 1))

    prewindow_labels: set[str] = set()
    paper_ages: dict[str, int] = {}
    series_dict: dict[str, pd.Series] = {}

    for work, label in zip(selected, labels):
        pub_year = work.get("publication_year") or current_year
        paper_ages[label] = current_year - pub_year
        counts_by_year = work.get("counts_by_year") or []
        yearly: dict[int, float] = {
            int(entry["year"]) - pub_year: float(entry["cited_by_count"])
            for entry in counts_by_year
        }

        total = float(work.get("cited_by_count") or 0)
        windowed_sum = sum(yearly.values())
        pre_window = total - windowed_sum

        s = pd.Series(0.0, index=all_ages)
        for age, cnt in yearly.items():
            if age in s.index:
                s[age] = cnt

        if pre_window > 0:
            earliest_age = min(yearly.keys()) if yearly else 0
            target = earliest_age if earliest_age in s.index else 0
            s[target] += pre_window
            prewindow_labels.add(label)

        series_dict[label] = s.cumsum()

    df = pd.DataFrame(series_dict)
    df.index.name = "years_since_publication"
    return df, prewindow_labels, paper_ages


def plot_cumulative(
    df: pd.DataFrame,
    author_name: str,
    prewindow_labels: set[str],
    output_path: Path,
    top_n: int,
    paper_ages: dict[str, int],
) -> None:
    """
    Creates and saves the cumulative citations PNG figure with direct line labels.

    Arguments:
        df (pd.DataFrame): wide DataFrame with years_since_publication index
            and paper-label columns
        author_name (str): author display name for the figure title
        prewindow_labels (set[str]): column labels of papers with pre-window citations
        output_path (Path): destination PNG path
        top_n (int): number of papers shown, used in the subtitle
        paper_ages (dict[str, int]): maps each label to its age in years
            (current_year - publication_year); each line is drawn only up to this age

    Returns:
        None
    """
    if _STYLE_PATH.exists():
        plt.style.use(str(_STYLE_PATH))

    fig, ax = plt.subplots()
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    display_labels = {
        col: (f"{col}†" if col in prewindow_labels else col) for col in df.columns
    }

    col_index = {col: i for i, col in enumerate(df.columns)}
    x_right = max(paper_ages.values()) if paper_ages else 0

    # Draw each paper's line and mark its true endpoint with a colored dot.
    for col in df.columns:
        age = paper_ages[col]
        col_color = colors[col_index[col] % len(colors)]
        ax.plot(
            df.index[: age + 1],
            df[col].iloc[: age + 1],
            linewidth=1.5,
            color=col_color,
        )
        ax.plot(
            age,
            float(df[col].iloc[age]),
            marker="o",
            markersize=3,
            color=col_color,
            zorder=3,
        )

    # Place labels in a right-hand column, nudging them apart vertically, and
    # connect each one back to its line's true endpoint with a colored leader so
    # the association stays unambiguous even where lines and labels are crowded.
    y_min = float(df.values.min())
    y_max = float(df.values.max())
    y_range = y_max - y_min
    min_gap = 0.04 * y_range if y_range > 0 else 1.0

    sorted_cols = sorted(df.columns, key=lambda c: float(df[c].iloc[paper_ages[c]]))

    placed: list[float] = []
    for col in sorted_cols:
        age = paper_ages[col]
        col_color = colors[col_index[col] % len(colors)]
        y_end = float(df[col].iloc[age])
        y_pos = y_end
        if placed and y_pos < placed[-1] + min_gap:
            y_pos = placed[-1] + min_gap
        placed.append(y_pos)

        # Leader from the true endpoint to the (possibly nudged) label anchor.
        ax.plot(
            [age, x_right],
            [y_end, y_pos],
            color=col_color,
            linewidth=0.6,
            alpha=0.5,
            zorder=2,
        )

        ax.annotate(
            display_labels[col],
            xy=(x_right, y_pos),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            ha="left",
            fontsize=6,
            color=col_color,
            annotation_clip=False,
        )

    ax.set_xlabel("Years since publication")
    ax.set_ylabel("Cumulative citations")
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    fig.suptitle(author_name, fontsize=12)
    ax.set_title(f"Top {top_n} papers by total citations", fontsize=9, color="grey")

    today_str = date.today().strftime("%Y-%m-%d")
    ax.text(
        1.0,
        -0.12,
        f"Data: OpenAlex, retrieved {today_str}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7,
        color="grey",
    )

    if prewindow_labels:
        ax.text(
            1.0,
            -0.17,
            (
                "* paper(s) marked † include citations accumulated "
                "before OpenAlex's yearly-counts window"
            ),
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=6,
            color="grey",
            style="italic",
        )

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    """
    CLI entry point: parse arguments, fetch data, build DataFrame, save outputs.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(
        prog="cumulative_citations",
        description=(
            "Plot cumulative yearly citations for an author's top-N papers.\n\n"
            "Known limitations:\n"
            "  1. counts_by_year covers only ~11 recent years; older citations\n"
            "     appear as a lump sum at the start of the visible series.\n"
            "  2. Surname extraction uses the last whitespace token, fragile\n"
            "     for compound names like 'van der X'.\n"
            "  3. Author disambiguation relies entirely on the supplied ID.\n"
            "  4. Citation counts at OpenAlex lag real activity by weeks to months."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "author_id",
        help="OpenAlex author ID (A5023888391, URL, or openalex:A5023888391)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        metavar="N",
        help="Number of top papers to plot (default: 5)",
    )
    parser.add_argument(
        "--output",
        metavar="BASENAME",
        help="Output file basename without extension (default: {author_id}_{date})",
    )
    parser.add_argument(
        "--email",
        metavar="EMAIL",
        help="Your email for the OpenAlex polite pool (strongly recommended)",
    )
    parser.add_argument(
        "--first-author-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Only include papers where this author is the first author "
            "(default: on; use --no-first-author-only to include all)"
        ),
    )
    args = parser.parse_args()

    if not args.email:
        print(
            "Warning: --email not provided. Requests may be rate-limited.",
            file=sys.stderr,
        )

    author_id = parse_author_id(args.author_id)
    today_str = date.today().strftime("%Y-%m-%d")
    output_base = args.output or f"{author_id}_{today_str}"
    output_path = Path(output_base)

    session = make_session(args.email)

    print(f"Fetching author {author_id} ...")
    author = fetch_author(author_id, session, {})
    author_name = author.get("display_name", author_id)

    print(f"Fetching works for {author_name} ...")
    works = fetch_works(author_id, session, {})

    if not works:
        print(f"No works found for author {author_id}.")
        sys.exit(0)

    merged_works = merge_duplicate_titles(works)
    n_merged = len(works) - len(merged_works)
    if n_merged:
        print(
            f"Merged {n_merged} same-title duplicate(s) "
            "(e.g. preprint + published version)."
        )
    works = merged_works

    if args.first_author_only:
        works = filter_first_author(works, author_id)
        print(f"Keeping first-author papers only: {len(works)} remain.")
        if not works:
            print(f"No first-author works found for author {author_id}.")
            sys.exit(0)

    top_n = args.top
    if len(works) < top_n:
        print(
            f"Warning: author has only {len(works)} works; "
            f"using all instead of {top_n}."
        )
        top_n = len(works)

    print(f"Building cumulative citation series for top {top_n} papers ...")
    df, prewindow_labels, paper_ages = build_cumulative_dataframe(works, top_n)

    csv_path = output_path.with_suffix(".csv")
    png_path = output_path.with_suffix(".png")

    df.to_csv(csv_path, index_label="years_since_publication")

    plot_cumulative(df, author_name, prewindow_labels, png_path, top_n, paper_ages)

    total_citations = int(df.iloc[-1].sum())
    print(f"\nAuthor:                    {author_name}")
    print(f"Works retrieved:           {len(works)}")
    print(f"Total citations (top {top_n}): {total_citations}")
    print(f"CSV:                       {csv_path}")
    print(f"Figure:                    {png_path}")


if __name__ == "__main__":
    main()
