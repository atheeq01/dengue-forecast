from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_PDF_DIR = PROJECT_ROOT / "data" / "raw_pdfs"
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"
SILVER_DIR = PROJECT_ROOT / "data" / "silver"
GOLD_DIR = PROJECT_ROOT / "data" / "gold"


# The WER reports by RDHS/DPDHS (health administration) division, not
# strictly by the 25 official districts — Kalmunai is split out of Ampara
# for health reporting, giving 26 rows total. Confirmed against real WER
# PDFs from 2011 and 2026 — same 26 names both times, just spelled/
# truncated differently on the page (handled in pdf_parser.py, not here).
DISTRICT_COORDS = {
    "Colombo":      {"lat": 6.9271,  "lon": 79.8612},
    "Gampaha":      {"lat": 7.0917,  "lon": 79.9995},
    "Kalutara":     {"lat": 6.5854,  "lon": 79.9607},
    "Kandy":        {"lat": 7.2906,  "lon": 80.6337},
    "Matale":       {"lat": 7.4675,  "lon": 80.6234},
    "Nuwara Eliya": {"lat": 6.9497,  "lon": 80.7891},
    "Galle":        {"lat": 6.0535,  "lon": 80.2210},
    "Matara":       {"lat": 5.9485,  "lon": 80.5353},
    "Hambantota":   {"lat": 6.1241,  "lon": 81.1185},
    "Jaffna":       {"lat": 9.6615,  "lon": 80.0255},
    "Kilinochchi":  {"lat": 9.3961,  "lon": 80.3982},
    "Mannar":       {"lat": 8.9810,  "lon": 79.9044},
    "Vavuniya":     {"lat": 8.7514,  "lon": 80.4971},
    "Mullaitivu":   {"lat": 9.2670,  "lon": 80.8142},
    "Batticaloa":   {"lat": 7.7170,  "lon": 81.7000},
    "Ampara":       {"lat": 7.2975,  "lon": 81.6747},
    "Trincomalee":  {"lat": 8.5874,  "lon": 81.2152},
    "Kurunegala":   {"lat": 7.4867,  "lon": 80.3647},
    "Puttalam":     {"lat": 8.0362,  "lon": 79.8283},
    "Anuradhapura": {"lat": 8.3114,  "lon": 80.4037},
    "Polonnaruwa":  {"lat": 7.9403,  "lon": 81.0188},
    "Badulla":      {"lat": 6.9934,  "lon": 81.0550},
    "Monaragala":   {"lat": 6.8721,  "lon": 81.3507},
    "Ratnapura":    {"lat": 6.6828,  "lon": 80.4009},
    "Kegalle":      {"lat": 7.2513,  "lon": 80.3464},
    "Kalmunai":     {"lat": 7.4102,  "lon": 81.8142},
}
DENGUE_THIS_WEEK_IDX = 0
DENGUE_CUMULATIVE_IDX = 1