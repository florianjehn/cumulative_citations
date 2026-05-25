import pytest

from src.cumulative_citations import (
    build_cumulative_dataframe,
    parse_author_id,
    short_label,
)

# ---------------------------------------------------------------------------
# parse_author_id
# ---------------------------------------------------------------------------


def test_parse_author_id_bare():
    assert parse_author_id("A5023888391") == "A5023888391"


def test_parse_author_id_url():
    assert parse_author_id("https://openalex.org/A5023888391") == "A5023888391"


def test_parse_author_id_prefix():
    assert parse_author_id("openalex:A5023888391") == "A5023888391"


def test_parse_author_id_with_whitespace():
    assert parse_author_id("  A9999999999  ") == "A9999999999"


def test_parse_author_id_invalid_exits():
    with pytest.raises(SystemExit) as exc:
        parse_author_id("not-an-id")
    assert exc.value.code == 1


def test_parse_author_id_empty_exits():
    with pytest.raises(SystemExit) as exc:
        parse_author_id("")
    assert exc.value.code == 1


# ---------------------------------------------------------------------------
# short_label
# ---------------------------------------------------------------------------


def _work(title, year, author_display_name):
    return {
        "display_name": title,
        "publication_year": year,
        "authorships": [{"author": {"display_name": author_display_name}}],
        "cited_by_count": 0,
        "counts_by_year": [],
        "doi": None,
        "id": "W0",
    }


def test_short_label_structure():
    label = short_label(_work("Climate change impacts", 2021, "Jane Smith"))
    assert "Smith" in label
    assert "2021" in label
    assert "—" in label


def test_short_label_max_length():
    long_title = "A" * 100
    label = short_label(_work(long_title, 2020, "Alice Beta"))
    assert len(label) <= 35


def test_short_label_truncation_ellipsis():
    long_title = "A" * 100
    label = short_label(_work(long_title, 2020, "Alice Beta"))
    assert label.endswith("…")


def test_short_label_no_truncation_short_title():
    label = short_label(_work("Short", 2020, "Bob Gamma"))
    assert not label.endswith("…")
    assert len(label) <= 35


def test_short_label_no_authorships():
    work = {
        "display_name": "Orphan paper",
        "publication_year": 2019,
        "authorships": [],
        "cited_by_count": 0,
        "counts_by_year": [],
        "doi": None,
        "id": "W0",
    }
    label = short_label(work)
    assert "Unknown" in label


def test_short_label_missing_counts_by_year():
    work = {
        "display_name": "Paper",
        "publication_year": 2022,
        "authorships": [{"author": {"display_name": "Carol Delta"}}],
        "cited_by_count": 5,
        "counts_by_year": None,
        "doi": None,
        "id": "W0",
    }
    label = short_label(work)
    assert "Delta" in label


# ---------------------------------------------------------------------------
# build_cumulative_dataframe
# ---------------------------------------------------------------------------


def _mock_works():
    return [
        {
            "id": "W1",
            "display_name": "Top paper",
            "publication_year": 2018,
            "cited_by_count": 100,
            "counts_by_year": [
                {"year": 2019, "cited_by_count": 50},
                {"year": 2020, "cited_by_count": 50},
            ],
            "authorships": [{"author": {"display_name": "Alice Alpha"}}],
            "doi": None,
        },
        {
            "id": "W2",
            "display_name": "Second paper",
            "publication_year": 2019,
            "cited_by_count": 80,
            "counts_by_year": [{"year": 2020, "cited_by_count": 80}],
            "authorships": [{"author": {"display_name": "Bob Beta"}}],
            "doi": None,
        },
        {
            "id": "W3",
            "display_name": "Old paper with hidden citations",
            "publication_year": 2015,
            "cited_by_count": 200,
            "counts_by_year": [{"year": 2020, "cited_by_count": 100}],
            "authorships": [{"author": {"display_name": "Carol Gamma"}}],
            "doi": None,
        },
    ]


def test_build_selects_top_n():
    df, _, _ = build_cumulative_dataframe(_mock_works(), top_n=2)
    assert len(df.columns) == 2


def test_build_orders_by_citations_descending():
    df, _, paper_ages = build_cumulative_dataframe(_mock_works(), top_n=2)
    # W3 (200) and W1 (100) must be selected; W2 (80) must not appear
    end_values = sorted(
        [float(df[c].iloc[paper_ages[c]]) for c in df.columns], reverse=True
    )
    assert end_values[0] == pytest.approx(200.0)
    assert end_values[1] == pytest.approx(100.0)


def test_build_cumulative_end_equals_cited_by_count():
    df, _, paper_ages = build_cumulative_dataframe(_mock_works(), top_n=3)
    for col in df.columns:
        for w in _mock_works():
            lbl = short_label(w)
            if lbl == col or col.startswith(lbl):
                assert df[col].iloc[paper_ages[col]] == pytest.approx(
                    float(w["cited_by_count"])
                )


def test_build_detects_prewindow():
    # W3: cited_by_count=200, counts_by_year sums to 100 → pre_window=100
    _, prewindow_labels, _ = build_cumulative_dataframe(_mock_works(), top_n=3)
    assert len(prewindow_labels) == 1
    pw_label = next(iter(prewindow_labels))
    assert "Gamma" in pw_label


def test_build_no_prewindow_when_totals_match():
    # W1 and W2 have no pre-window citations
    _, prewindow_labels, _ = build_cumulative_dataframe(_mock_works()[:2], top_n=2)
    assert len(prewindow_labels) == 0


def test_build_unique_labels():
    same_works = [
        {
            "id": f"W{i}",
            "display_name": "Identical title",
            "publication_year": 2020,
            "cited_by_count": 10 - i,
            "counts_by_year": [{"year": 2021, "cited_by_count": 10 - i}],
            "authorships": [{"author": {"display_name": "Same Author"}}],
            "doi": None,
        }
        for i in range(3)
    ]
    df, _, _ = build_cumulative_dataframe(same_works, top_n=3)
    assert len(df.columns) == len(set(df.columns)) == 3


def test_build_index_is_age_range():
    df, _, _ = build_cumulative_dataframe(_mock_works(), top_n=3)
    from datetime import date

    assert df.index[0] == 0  # always starts at publication year
    assert df.index[-1] == date.today().year - 2015  # oldest paper is 2015


def test_build_paper_ages():
    from datetime import date

    _, _, paper_ages = build_cumulative_dataframe(_mock_works(), top_n=3)
    current_year = date.today().year
    # W3 published 2015, W1 published 2018, W2 published 2019
    ages = sorted(paper_ages.values(), reverse=True)
    assert ages[0] == current_year - 2015
    assert ages[1] == current_year - 2018
    assert ages[2] == current_year - 2019


def test_build_missing_counts_by_year_field():
    works = [
        {
            "id": "W1",
            "display_name": "Paper",
            "publication_year": 2020,
            "cited_by_count": 10,
            "counts_by_year": None,  # missing / null field
            "authorships": [{"author": {"display_name": "Eve Epsilon"}}],
            "doi": None,
        }
    ]
    df, prewindow_labels, paper_ages = build_cumulative_dataframe(works, top_n=1)
    col = df.columns[0]
    assert df[col].iloc[paper_ages[col]] == pytest.approx(10.0)
    assert len(prewindow_labels) == 1
