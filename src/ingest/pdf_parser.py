import re
import subprocess
from datetime import datetime
from pathlib import Path

from src.config import DISTRICT_COORDS

# --- Known table shapes, keyed by total number of values in a row ---
# Confirmed from two real report eras. Add a new entry here whenever a
# PDF from a different era shows a row length that isn't already covered
# — that's the whole "handle column drift" story for this project.
TABLE_SCHEMAS = {
    19: {  # e.g. 2011-era reports
        "diseases": [
            "dengue_fever", "dysentery", "encephalitis", "enteric_fever",
            "food_poisoning", "leptospirosis", "typhus", "viral_hepatitis",
            "human_rabies",
        ],
        "trailing_fields": ["returns_pct"],
    },
    30: {  # e.g. 2026-era reports
        "diseases": [
            "dengue_fever", "dysentery", "encephalitis", "enteric_fever",
            "food_poisoning", "leptospirosis", "typhus", "viral_hepatitis",
            "human_rabies", "chickenpox", "meningitis", "leishmaniasis",
            "tuberculosis", "leprosy",
        ],
        "trailing_fields": ["timeliness_pct", "completeness_pct"],
    },
}

# Confirmed necessary against a 2011 sample: this district-name-truncation
# tolerance is not optional. Below this many shared characters, two
# different district names can share a prefix ('Matale'/'Matara' both
# start with 'Mata'), so matches shorter than this are rejected rather
# than guessed.
MIN_MATCH_LEN = 5

# Matches "11th – 17th May 2026 (20th Week)" or the older, punctuated
# style "25th –31th December - 2010(52nd Week)" — both real, both tested.
# This in-body date is the only date source we trust; it's been confirmed
# to differ from both the cover page and the listing-site's own metadata.
WEEK_PATTERN = re.compile(
    r"(\d{1,2})\w{0,2}\s*[–—-]\s*(\d{1,2})\w{0,2}\s+(\w+)"
    r"\s*[–—-]?\s*(\d{4})\s*\(\s*(\d{1,2})\w{0,2}\s*Week\)"
)


def pdf_to_text(pdf_path: Path) -> str:
    """Runs `pdftotext -layout` on a PDF. -layout is required — without
    it this Publisher-exported table's columns get scrambled."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def extract_report_week(text: str) -> dict:
    """Pulls the real reporting period out of the PDF body."""
    match = WEEK_PATTERN.search(text)
    if not match:
        raise ValueError("Could not find the reporting week/date in this PDF")
    _, end_day, month_name, year, week_no = match.groups()
    week_ending = datetime.strptime(f"{end_day} {month_name} {year}", "%d %B %Y")
    return {"week_ending": week_ending, "epi_week": int(week_no), "year": int(year)}


def _leading_label(line: str) -> str:
    """Everything before the first digit on the line, e.g. 'Kilinoch-' or 'Colombo'."""
    match = re.match(r"^(\D+)", line.strip())
    if not match:
        return ""
    return match.group(1).strip().rstrip("-").strip()


def _match_district_label(label: str, known_names) -> str | None:
    """
    Matches a possibly-truncated label against its canonical district name.
    Older/narrower report layouts cut long names short — 'Nuwara' for
    'Nuwara Eliya', 'Kilinoch-' for 'Kilinochchi', 'Anuradha' for
    'Anuradhapura' — all confirmed against a real 2011 file. Requires at
    least MIN_MATCH_LEN shared characters up front, so a short/ambiguous
    label fails to match rather than guessing wrong.
    """
    candidates = []
    for name in known_names:
        shared = min(len(label), len(name))
        if shared >= MIN_MATCH_LEN and label[:shared] == name[:shared]:
            candidates.append(name)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        exact = [n for n in candidates if n == label]
        return exact[0] if len(exact) == 1 else None
    return None


def find_all_district_rows(text: str) -> dict[str, list[int]]:
    """
    Scans every line once, matching each to a known district (tolerating
    truncated names), and returns {canonical_name: [values]}.

    A district name can appear on more than one line in the same document
    (e.g. an unrelated table elsewhere also starts lines with district
    names) — when that happens, this prefers whichever candidate row's
    length matches a KNOWN schema shape, rather than just taking whichever
    one it saw first or last. That's what actually distinguishes "the real
    disease table row" from "a same-named row in some other table",
    confirmed necessary against a real file.
    """
    candidates_by_name: dict[str, list[list[int]]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or not stripped[0].isalpha():
            continue
        label = _leading_label(stripped)
        if not label:
            continue
        matched = _match_district_label(label, DISTRICT_COORDS.keys())
        if matched is None:
            continue
        rest = stripped[len(label):]
        numbers = [int(n) for n in re.findall(r"\d+", rest)]
        if numbers:
            candidates_by_name.setdefault(matched, []).append(numbers)

    rows = {}
    for name, candidate_list in candidates_by_name.items():
        schema_matches = [c for c in candidate_list if len(c) in TABLE_SCHEMAS]
        rows[name] = schema_matches[-1] if schema_matches else candidate_list[-1]
    return rows


def parse_disease_row(values: list[int]) -> dict:
    """
    Splits a row's flat number list into named fields, using whichever
    known schema matches its length. Raises clearly (rather than silently
    misaligning columns) when the length matches nothing — this is what
    happens for a row with a genuinely missing/blank cell in the source
    PDF (confirmed: real data, not a parsing bug — one division's row in
    a 2011 file is missing one value).
    """
    schema = TABLE_SCHEMAS.get(len(values))
    if schema is None:
        raise ValueError(
            f"Unrecognized row shape: got {len(values)} numbers, expected "
            f"one of {sorted(TABLE_SCHEMAS)}. Likely either a new report "
            f"era with a different disease list, or a missing cell in "
            f"this specific row."
        )
    diseases = schema["diseases"]
    result = {}
    for i, disease in enumerate(diseases):
        result[f"{disease}_this_week"] = values[i * 2]
        result[f"{disease}_cumulative"] = values[i * 2 + 1]
    trailing_values = values[len(diseases) * 2:]
    for field_name, value in zip(schema["trailing_fields"], trailing_values):
        result[field_name] = value
    return result


def parse_wer_pdf(pdf_path: Path) -> list[dict]:
    """
    Full pipeline for one PDF: extract text -> find the report week ->
    match every known district's row -> parse it under whichever schema
    fits. Skips (with a warning) anything that doesn't parse cleanly, so
    one odd row or file doesn't crash a whole batch.
    """
    text = pdf_to_text(pdf_path)
    week_info = extract_report_week(text)
    all_rows = find_all_district_rows(text)

    records = []
    for district in DISTRICT_COORDS.keys():
        values = all_rows.get(district)
        if values is None:
            print(f"[warn] '{district}' not found in {pdf_path.name}")
            continue
        try:
            record = parse_disease_row(values)
        except ValueError as e:
            print(f"[warn] '{district}' in {pdf_path.name}: {e}")
            continue
        record["district"] = district
        record["source_file"] = pdf_path.name
        record.update(week_info)
        records.append(record)
    return records


def parse_wer_pdf_colombo_only(pdf_path: Path) -> dict | None:
    """Sprint-0 helper: just Colombo's dengue counts, for the walking skeleton."""
    for record in parse_wer_pdf(pdf_path):
        if record["district"] == "Colombo":
            return {
                "district": "Colombo",
                "dengue_this_week": record["dengue_fever_this_week"],
                "dengue_cumulative": record["dengue_fever_cumulative"],
                "week_ending": record["week_ending"],
                "epi_week": record["epi_week"],
                "source_file": record["source_file"],
            }
    return None