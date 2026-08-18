"""Parse district disease rows from Sri Lanka Weekly Epidemiological Reports.

The labels emitted by ``pdftotext`` are not authoritative: the WER disease
table has a stable row order, while labels may be truncated or OCR-damaged.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from src.config import CANONICAL_RDHS, TABLE_SCHEMAS


# A report row has at least 8 A/B pairs plus reporting percentage(s).
# This rejects administrative strings such as "COLOMBO 10".
MIN_NUMERIC_VALUES = 5
LABEL_MATCH_THRESHOLD = 0.60
MAX_LINE_GAP = 18

# This is the *published WER table order*.  Do not substitute a geographic or
# alphabetic district list here: in particular Hambantota is before Matara and
# Kalmunai is the final row.
WER_ROW_ORDER = (
    "Colombo", "Gampaha", "Kalutara", "Kandy", "Matale", "Nuwara Eliya",
    "Galle", "Hambantota", "Matara", "Jaffna", "Kilinochchi", "Mannar",
    "Vavuniya", "Mullaitivu", "Batticaloa", "Ampara", "Trincomalee",
    "Kurunegala", "Puttalam", "Anuradhapura", "Polonnaruwa", "Badulla",
    "Monaragala", "Ratnapura", "Kegalle", "Kalmunai",
)

WEEK_PATTERNS = [
    # Standard format: 20th – 26th November 2010 (46th Week) or 27th Jan - 2nd Feb 2007 ( 5th Week)
    re.compile(
        r"(\d{1,2})\w*(?:\s+[A-Za-z]+)?\s*[–—-]\s*(\d{1,2})\w*\s+([A-Za-z]+)"
        r"\s*[–—-]?\s*(\d{4})\s*\(\s*(\d{1,2})\w*\s*Week\s*\)",
        re.IGNORECASE,
    ),
    # Volume/Number header format: Vol. 52 No. 02 04th Jan – 10th Jan 2025
    re.compile(
        r"Vol\.\s*(\d+)\s*No\s*\.?\s*(\d+)\s+(\d{1,2})\w*(?:\s+[A-Za-z]+)?\s*[–—-]\s*(\d{1,2})\w*\s+([A-Za-z]+)\s+(\d{4})",
        re.IGNORECASE,
    ),
]


@dataclass(frozen=True)
class CandidateRow:
    line_number: int
    label: str
    values: list[int]


def pdf_to_text(pdf_path: Path) -> str:
    """Extract layout-preserving text from *pdf_path*."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _normalise(value: str) -> str:
    """Normalise only for matching; never use this to alter numeric values."""
    value = value.casefold().replace("–", "-").replace("—", "-")
    # A leading digit joined to text is a common extraction artefact:
    # 0Vavuniya -> Vavuniya.  Digits separated from text remain data values.
    value = re.sub(r"^\d+(?=[a-z])", "", value)
    return re.sub(r"[^a-z]", "", value)


def _label_score(label: str, district: str) -> float:
    """Return a conservative match score, including truncated labels."""
    lhs, rhs = _normalise(label), _normalise(district)
    if not lhs:
        return 0.0
    if lhs == rhs:
        return 1.0
    if len(lhs) >= 5 and (rhs.startswith(lhs) or lhs.startswith(rhs)):
        return 0.96
    return SequenceMatcher(None, lhs, rhs).ratio()


def _best_label_match(label: str) -> tuple[str | None, float]:
    district, score = max(
        ((district, _label_score(label, district)) for district in WER_ROW_ORDER),
        key=lambda item: item[1],
    )
    return (district, score) if score >= LABEL_MATCH_THRESHOLD else (None, score)


def _clean_line_values(tail: str) -> list[int]:
    """Extract integer values from tail text, cleaning attached punctuation/symbols."""
    cleaned_tail = re.sub(r"[`'\"%*,]+", " ", tail)
    return [int(v) for v in re.findall(r"-?\d+", cleaned_tail)]


def _candidate_from_line(line: str, line_number: int) -> CandidateRow | None:
    """Return one numeric district-row candidate if present on a single line."""
    match = re.match(r"^\s*(?P<label>.*?)(?=\s+-?\d+(?:\s|[`'\"%*]|$))(?P<tail>\s+.*)$", line)
    if not match:
        return None
    label = match.group("label").strip(" \t:.-")
    tail = match.group("tail")
    values = _clean_line_values(tail)
    if len(values) < MIN_NUMERIC_VALUES or not re.search(r"[A-Za-z]", label):
        return None
    matched, _score = _best_label_match(label)
    if matched is None:
        return None
    return CandidateRow(line_number=line_number, label=label, values=values)


def _candidate_rows(text: str) -> list[CandidateRow]:
    """Extract district row candidates, seamlessly stitching split lines across page breaks."""
    lines = text.splitlines()
    candidates: list[CandidateRow] = []
    consumed_lines: set[int] = set()

    for i, line in enumerate(lines):
        if i in consumed_lines:
            continue

        # Standard line: label followed by whitespace-separated numbers
        match = re.match(r"^\s*(?P<label>.*?)(?=\s+-?\d+(?:\s|[`'\"%*]|$))(?P<tail>\s+.*)$", line)
        if match:
            label = match.group("label").strip(" \t:.-")
            tail = match.group("tail")
            values = _clean_line_values(tail)
            if re.search(r"[A-Za-z]", label) and len(values) >= MIN_NUMERIC_VALUES:
                matched, _ = _best_label_match(label)
                if matched is not None:
                    candidates.append(CandidateRow(line_number=i, label=label, values=values))
                    consumed_lines.add(i)
                    continue

        # Orphan district label whose numbers landed on an adjacent line across page break
        trimmed = line.strip(" \t:.-")
        if trimmed and re.search(r"^[A-Za-z\s]+$", trimmed):
            matched, _ = _best_label_match(trimmed)
            if matched is not None:
                # Look backward for numbers-only line
                found = False
                for offset in range(1, 14):
                    prev_idx = i - offset
                    if prev_idx < 0:
                        break
                    if prev_idx in consumed_lines:
                        continue
                    prev_line = lines[prev_idx]
                    if not re.search(r"[A-Za-z]", prev_line):
                        v = _clean_line_values(prev_line)
                        if len(v) >= MIN_NUMERIC_VALUES:
                            candidates.append(CandidateRow(line_number=prev_idx, label=trimmed, values=v))
                            consumed_lines.add(prev_idx)
                            consumed_lines.add(i)
                            found = True
                            break
                if found:
                    continue

                # Look forward for numbers-only line
                for offset in range(1, 14):
                    next_idx = i + offset
                    if next_idx >= len(lines):
                        break
                    if next_idx in consumed_lines:
                        continue
                    next_line = lines[next_idx]
                    if not re.search(r"[A-Za-z]", next_line):
                        v = _clean_line_values(next_line)
                        if len(v) >= MIN_NUMERIC_VALUES:
                            candidates.append(CandidateRow(line_number=i, label=trimmed, values=v))
                            consumed_lines.add(next_idx)
                            consumed_lines.add(i)
                            break

    candidates.sort(key=lambda c: c.line_number)
    return candidates


def _best_run(candidates: list[CandidateRow]) -> list[CandidateRow]:
    """Choose the strongest contiguous district-table run.

    WER pages can include a second abbreviated list of administrative areas.
    Selecting a contiguous run with a consistent numeric-column count avoids
    mixing it with the actual disease table.

    OCR artefacts occasionally cause a single row to parse with a different
    numeric-column count (e.g. missing trailing percentages).  Rather than
    splitting the run and losing half the districts, we tolerate a small number
    of outlier rows as long as the run remains spatially contiguous and the
    majority of rows agree on the expected column count.
    """
    MAX_OUTLIERS = 4

    best: list[CandidateRow] = []
    for start, first in enumerate(candidates):
        run = [first]
        previous_line = first.line_number
        for candidate in candidates[start + 1:]:
            if candidate.line_number - previous_line > MAX_LINE_GAP:
                break
            run.append(candidate)
            previous_line = candidate.line_number

        if len(run) <= len(best):
            continue

        # Determine the dominant column count (the mode) for this run.
        count_freq = Counter(len(c.values) for c in run)
        mode_length, _mode_freq = count_freq.most_common(1)[0]
        outlier_count = sum(1 for c in run if len(c.values) != mode_length)

        if outlier_count <= MAX_OUTLIERS:
            best = run

    return best


def reconstruct_district_rows(text: str) -> dict[str, list[int]]:
    """Reconstruct the disease table using WER row position as primary signal.

    A clean 26-row table is mapped position-for-position, even if a label is
    damaged.  Label agreement is diagnostic only; it does not cause a valid
    row such as ``0Vavuniya`` to disappear.  If rows are genuinely missing,
    an order-preserving alignment uses labels to locate the gap.
    """
    run = _best_run(_candidate_rows(text))
    if not run:
        return {}

    # The usual (and safest) case: complete 26-row table mapped 1-to-1 positionally.
    if len(run) == len(WER_ROW_ORDER):
        return {district: row.values for district, row in zip(WER_ROW_ORDER, run)}

    # For incomplete reports, dynamic programming finds the highest-scoring
    # monotonic alignment.  It may skip an expected district, but never shifts
    # every later row after one genuinely missing row.
    n, m = len(WER_ROW_ORDER), len(run)
    dp = [[float("-inf")] * (m + 1) for _ in range(n + 1)]
    back: list[list[str | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            score = dp[i][j]
            if score == float("-inf"):
                continue
            if i < n and score - 0.35 > dp[i + 1][j]:
                dp[i + 1][j], back[i + 1][j] = score - 0.35, "skip_district"
            if j < m and score - 1.0 > dp[i][j + 1]:
                dp[i][j + 1], back[i][j + 1] = score - 1.0, "skip_row"
            if i < n and j < m:
                label_score = _label_score(run[j].label, WER_ROW_ORDER[i])
                match_score = label_score if label_score >= LABEL_MATCH_THRESHOLD else -2.0
                next_score = score + match_score
                if next_score > dp[i + 1][j + 1]:
                    dp[i + 1][j + 1], back[i + 1][j + 1] = next_score, "match"

    rows: dict[str, list[int]] = {}
    i, j = n, m
    while i or j:
        action = back[i][j]
        if action == "match":
            rows[WER_ROW_ORDER[i - 1]] = run[j - 1].values
            i, j = i - 1, j - 1
        elif action == "skip_district":
            i -= 1
        elif action == "skip_row":
            j -= 1
        else:
            break
    return dict(sorted(rows.items(), key=lambda item: WER_ROW_ORDER.index(item[0])))


def find_all_district_rows(text: str) -> dict[str, list[int]]:
    """Backward-compatible public name for district-row reconstruction."""
    return reconstruct_district_rows(text)


def extract_report_week(text: str, filename: str = "") -> dict[str, Any]:
    """Extract week ending date, epidemiological week, and year from a WER."""
    for pattern in WEEK_PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            if len(groups) == 5:
                _start, end, month, year, epi_week = groups
            else:
                vol, no, _start, end, month, year = groups
                epi_week = no
            week_ending = None
            for fmt in ("%d %B %Y", "%d %b %Y"):
                try:
                    week_ending = datetime.strptime(f"{end} {month} {year}", fmt)
                    break
                except ValueError:
                    pass
            if week_ending is not None:
                return {"week_ending": week_ending, "epi_week": int(epi_week), "year": int(year)}

    # Fallback to filename if text matching was unable to resolve the exact date
    if filename:
        fn_match = re.search(r"wer_(\d{4})_w(\d{1,2})", filename)
        if fn_match:
            year, epi_week = int(fn_match.group(1)), int(fn_match.group(2))
            return {"week_ending": None, "epi_week": epi_week, "year": year}

    raise ValueError("Could not find the reporting week/date in PDF text")


def _find_best_schema(target_len: int, doc_mode_len: int | None = None) -> tuple[dict[str, Any] | None, int]:
    """Locate the best matching historical disease schema, tolerating omitted trailing fields."""
    if target_len in TABLE_SCHEMAS:
        return TABLE_SCHEMAS[target_len], target_len

    if doc_mode_len and doc_mode_len in TABLE_SCHEMAS:
        schema = TABLE_SCHEMAS[doc_mode_len]
        num_disease_vals = 2 * len(schema["diseases"])
        if target_len >= num_disease_vals:
            return schema, doc_mode_len

    for schema_len, schema in TABLE_SCHEMAS.items():
        num_disease_vals = 2 * len(schema["diseases"])
        if target_len == num_disease_vals or target_len == num_disease_vals + len(schema.get("trailing_fields", [])):
            return schema, schema_len

    return None, target_len


def _record_from_values(
    district: str,
    values: list[int],
    week: dict[str, Any],
    source: Path,
    doc_mode_len: int | None = None,
) -> dict[str, Any]:
    """Map one validated row to its configured historical table schema."""
    schema, _ = _find_best_schema(len(values), doc_mode_len)
    if schema is None:
        raise ValueError(
            f"Unsupported WER row schema ({len(values)} numeric values) in {source.name}"
        )
    diseases = schema["diseases"]
    trailing = schema.get("trailing_fields", [])

    record: dict[str, Any] = {"district": district, "source_file": source.name, **week}
    for index, disease in enumerate(diseases):
        record[f"{disease}_this_week"] = values[index * 2] if index * 2 < len(values) else 0
        record[f"{disease}_cumulative"] = values[index * 2 + 1] if index * 2 + 1 < len(values) else 0

    trailing_vals = values[2 * len(diseases):]
    for idx, field in enumerate(trailing):
        record[field] = trailing_vals[idx] if idx < len(trailing_vals) else 0

    return record


def parse_wer_pdf(pdf_path: Path) -> list[dict[str, Any]]:
    """Parse all recoverable RDHS records in a single WER PDF."""
    text = pdf_to_text(pdf_path)
    week = extract_report_week(text, pdf_path.name)
    rows = reconstruct_district_rows(text)

    doc_mode_len = None
    if rows:
        val_lens = [len(v) for v in rows.values()]
        doc_mode_len = max(set(val_lens), key=val_lens.count)

    return [
        _record_from_values(district, rows[district], week, pdf_path, doc_mode_len)
        for district in WER_ROW_ORDER
        if district in rows
    ]


# Retain the configuration check, but WER_ROW_ORDER remains the parser's table
# order.  A geographic canonical list need not have the same ordering.
if set(CANONICAL_RDHS) != set(WER_ROW_ORDER):
    raise ValueError("CANONICAL_RDHS and WER_ROW_ORDER must contain the same RDHS names")