import re
import subprocess
from datetime import datetime
from pathlib import Path

from src.config import (
    CANONICAL_RDHS,
    TABLE_SCHEMAS,
)


# =============================================================================
# CONSTANTS
# =============================================================================

# Older WER PDFs sometimes truncate district names.
#
# Examples:
#   Nuwara      -> Nuwara Eliya
#   Kilinoch-   -> Kilinochchi
#   Anuradha    -> Anuradhapura
#
# We require at least this many matching characters before accepting
# a truncated district name.
MIN_MATCH_LEN = 5


# Matches examples such as:
#
#   11th – 17th May 2026 (20th Week)
#   25th –31th December - 2010(52nd Week)
#
# We deliberately extract the date from the report body rather than
# trusting the PDF filename.
WEEK_PATTERN = re.compile(
    r"(\d{1,2})\w{0,2}\s*[–—-]\s*(\d{1,2})\w{0,2}\s+(\w+)"
    r"\s*[–—-]?\s*(\d{4})\s*\(\s*(\d{1,2})\w{0,2}\s*Week\)",
    re.IGNORECASE,
)


# =============================================================================
# PDF TEXT EXTRACTION
# =============================================================================

def pdf_to_text(pdf_path: Path) -> str:
    """
    Extract PDF text using pdftotext -layout.

    -layout is important because WER PDFs contain table-like layouts whose
    columns can become scrambled without it.
    """

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF does not exist: {pdf_path}"
        )

    result = subprocess.run(
        [
            "pdftotext",
            "-layout",
            str(pdf_path),
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout


# =============================================================================
# REPORT WEEK EXTRACTION
# =============================================================================

def extract_report_week(text: str) -> dict:
    """
    Extract the reporting week from the body of the WER PDF.

    Returns:
        {
            "week_ending": datetime,
            "epi_week": int,
            "year": int,
        }
    """

    match = WEEK_PATTERN.search(text)

    if not match:
        raise ValueError(
            "Could not find reporting week/date in PDF text"
        )

    (
        _start_day,
        end_day,
        month_name,
        year,
        week_no,
    ) = match.groups()

    try:
        week_ending = datetime.strptime(
            f"{end_day} {month_name} {year}",
            "%d %B %Y",
        )
    except ValueError as exc:
        raise ValueError(
            "Could not parse report date: "
            f"{end_day} {month_name} {year}"
        ) from exc

    return {
        "week_ending": week_ending,
        "epi_week": int(week_no),
        "year": int(year),
    }


# =============================================================================
# DISTRICT LABEL PARSING
# =============================================================================

def _leading_label(line: str) -> str:
    """
    Extract everything before the first numeric character.

    Example:

        'Kilinoch-  12 34 5 6'

    becomes approximately:

        'Kilinoch'

    The trailing hyphen and surrounding whitespace are removed.
    """

    stripped = line.strip()

    match = re.match(
        r"^(\D+)",
        stripped,
    )

    if not match:
        return ""

    return (
        match.group(1)
        .strip()
        .rstrip("-")
        .strip()
    )


def _normalize_label(label: str) -> str:
    """
    Basic normalization for district labels.

    This does NOT attempt fuzzy matching.
    """

    label = label.strip()

    label = re.sub(
        r"\s+",
        " ",
        label,
    )

    return label


def _match_district_label(
    label: str,
    known_names: list[str],
) -> str | None:
    """
    Match a possibly truncated WER district label against canonical RDHS names.

    Exact match is preferred.

    For truncated names, the beginning of the label must match the beginning
    of exactly one canonical RDHS name.

    Ambiguous matches are rejected instead of guessed.
    """

    label = _normalize_label(label)

    if not label:
        return None

    # ---------------------------------------------------------
    # First: exact match
    # ---------------------------------------------------------

    exact_matches = [
        name
        for name in known_names
        if name.lower() == label.lower()
    ]

    if len(exact_matches) == 1:
        return exact_matches[0]

    # ---------------------------------------------------------
    # Second: prefix/truncated match
    # ---------------------------------------------------------

    candidates = []

    for name in known_names:

        shared = min(
            len(label),
            len(name),
        )

        if shared < MIN_MATCH_LEN:
            continue

        if (
            label[:shared].lower()
            == name[:shared].lower()
        ):
            candidates.append(name)

    if len(candidates) == 1:
        return candidates[0]

    # Ambiguous or unknown
    return None


# =============================================================================
# FIND DISTRICT ROWS
# =============================================================================

def find_all_district_rows(
    text: str,
) -> dict[str, list[int]]:
    """
    Find candidate disease-table rows for all known RDHS.

    Returns:

        {
            "Colombo": [ ...numbers... ],
            "Gampaha": [ ...numbers... ],
            ...
        }

    Important:
    A district may appear multiple times in a PDF because other tables may
    contain district names.

    Therefore, after collecting candidates, we prefer a candidate whose number
    count matches one of the known WER table schemas.
    """

    candidates_by_name: dict[
        str,
        list[list[int]],
    ] = {}

    for line in text.splitlines():

        stripped = line.strip()

        if not stripped:
            continue

        if not stripped[0].isalpha():
            continue

        label = _leading_label(stripped)

        if not label:
            continue

        matched = _match_district_label(
            label,
            CANONICAL_RDHS,
        )

        if matched is None:
            continue

        # Remove the district label from the beginning of the line.
        rest = stripped[len(label):]

        # Extract all integer values after the label.
        numbers = [
            int(value)
            for value in re.findall(
                r"\d+",
                rest,
            )
        ]

        if not numbers:
            continue

        candidates_by_name.setdefault(
            matched,
            [],
        ).append(numbers)

    # ---------------------------------------------------------
    # Select best candidate for every RDHS
    # ---------------------------------------------------------

    rows: dict[str, list[int]] = {}

    for name, candidate_list in candidates_by_name.items():

        schema_matches = [
            candidate
            for candidate in candidate_list
            if len(candidate) in TABLE_SCHEMAS
        ]

        if schema_matches:
            # Prefer the last schema-compatible occurrence.
            rows[name] = schema_matches[-1]
        else:
            # No known schema match.
            #
            # Keep the last candidate so parse_disease_row() can raise a
            # useful error later.
            rows[name] = candidate_list[-1]

    return rows


# =============================================================================
# PARSE DISEASE ROW
# =============================================================================

def parse_disease_row(
    values: list[int],
) -> dict:
    """
    Convert a flat numeric WER row into named disease fields.

    Example:

        [
            dengue_this_week,
            dengue_cumulative,
            dysentery_this_week,
            dysentery_cumulative,
            ...
        ]

    The exact interpretation depends on the historical WER schema.
    """

    schema = TABLE_SCHEMAS.get(
        len(values)
    )

    if schema is None:

        raise ValueError(
            f"Unrecognized WER row shape: "
            f"{len(values)} numeric values. "
            f"Known schemas: {sorted(TABLE_SCHEMAS)}."
        )

    diseases = schema["diseases"]

    expected_disease_values = len(diseases) * 2

    if len(values) < expected_disease_values:
        raise ValueError(
            f"Row contains {len(values)} values, but "
            f"{expected_disease_values} are required for "
            f"{len(diseases)} diseases."
        )

    result = {}

    # ---------------------------------------------------------
    # Disease this-week / cumulative values
    # ---------------------------------------------------------

    for index, disease in enumerate(diseases):

        result[
            f"{disease}_this_week"
        ] = values[index * 2]

        result[
            f"{disease}_cumulative"
        ] = values[index * 2 + 1]

    # ---------------------------------------------------------
    # Trailing reporting fields
    # ---------------------------------------------------------

    trailing_values = values[
        expected_disease_values:
    ]

    trailing_fields = schema[
        "trailing_fields"
    ]

    if len(trailing_values) != len(trailing_fields):
        raise ValueError(
            f"Schema mismatch for row with {len(values)} values. "
            f"Expected {len(trailing_fields)} trailing fields, "
            f"but found {len(trailing_values)}."
        )

    for field_name, value in zip(
        trailing_fields,
        trailing_values,
    ):
        result[field_name] = value

    return result


# =============================================================================
# PARSE ONE COMPLETE WER PDF
# =============================================================================

def parse_wer_pdf(
    pdf_path: Path,
) -> list[dict]:
    """
    Parse one WER PDF into one record per RDHS.

    Pipeline:

        PDF
         ↓
        pdftotext -layout
         ↓
        extract report week
         ↓
        find RDHS rows
         ↓
        parse disease values
         ↓
        return structured records
    """

    text = pdf_to_text(
        pdf_path
    )

    week_info = extract_report_week(
        text
    )

    all_rows = find_all_district_rows(
        text
    )

    records = []

    for district in CANONICAL_RDHS:

        values = all_rows.get(
            district
        )

        # -----------------------------------------------------
        # Missing district
        # -----------------------------------------------------

        if values is None:

            print(
                f"[warn] "
                f"RDHS '{district}' not found "
                f"in {pdf_path.name}"
            )

            continue

        # -----------------------------------------------------
        # Parse disease row
        # -----------------------------------------------------

        try:

            record = parse_disease_row(
                values
            )

        except ValueError as exc:

            print(
                f"[warn] "
                f"Could not parse '{district}' "
                f"in {pdf_path.name}: {exc}"
            )

            continue

        # -----------------------------------------------------
        # Add metadata
        # -----------------------------------------------------

        record["district"] = district

        record["source_file"] = (
            pdf_path.name
        )

        record.update(
            week_info
        )

        records.append(
            record
        )

    return records


# =============================================================================
# COLOMBO-ONLY HELPER
# =============================================================================

def parse_wer_pdf_colombo_only(
    pdf_path: Path,
) -> dict | None:
    """
    Sprint-0 helper used for testing the walking skeleton.

    Returns only Colombo's dengue information.
    """

    records = parse_wer_pdf(
        pdf_path
    )

    for record in records:

        if record["district"] == "Colombo":

            return {
                "district": "Colombo",

                "dengue_this_week": (
                    record[
                        "dengue_fever_this_week"
                    ]
                ),

                "dengue_cumulative": (
                    record[
                        "dengue_fever_cumulative"
                    ]
                ),

                "week_ending": (
                    record[
                        "week_ending"
                    ]
                ),

                "epi_week": (
                    record[
                        "epi_week"
                    ]
                ),

                "source_file": (
                    record[
                        "source_file"
                    ]
                ),
            }

    return None