import re
from pathlib import Path
import requests

from src.config import RAW_PDF_DIR

LISTING_URL = "https://www.epid.gov.lk/weekly-epidemiological-report"

PDF_LINK_PATTERN = re.compile(
    r'href="(https://www\.epid\.gov\.lk/storage/post/pdfs/[^"]+\.pdf)"'
)

VOL_WEEK_PATTERN = re.compile(r"[Vv]ol[_ ]?(\d+)[_ ]?[Nn][Oo][_ ]?(\d+)")


def find_pdf_links(html: str) -> list[str]:
    """Every distinct absolute PDF URL on the listing page."""
    return sorted(set(PDF_LINK_PATTERN.findall(html)))


def year_week_from_url(url: str) -> tuple[int, int] | None:
    """
       Derives (year, week) from the URL's own Vol_NN_no_WW pattern.
       Year = Volume + 1973 — confirmed against real filenames spanning
       2016 to 2026.

       Returns None if the pattern isn't found, or if the resulting year
       falls outside a sane range. The site genuinely archives reports back
       to ~2009 (Vol 36), so the range must be wide enough to admit those;
       it only exists to catch impossible values (a garbled volume number
       computing to a wildly old or future year) rather than mis-date data.
    """
    filename = url.split("/")[-1]
    match = VOL_WEEK_PATTERN.search(filename)
    if not match:
        return None
    volume, week = int(match.group(1)), int(match.group(2))
    year = volume + 1973
    if not (2005<=year<=2030):
        print(f"[warning] '{filename}' implies year {year} looks wrong,"
              f"check this file by hand before trusting it")
        return None
    return year, week

def download_pdf(url:str,dest_path:Path) -> None:
    if dest_path.exists():
        return
    resp = requests.get(url,timeout=30)
    resp.raise_for_status()
    dest_path.write_bytes(resp.content)
    return

def download_all_wer_pdfs():
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    listing= requests.get(LISTING_URL,timeout=30)
    listing.raise_for_status()

    links = find_pdf_links(listing.text)
    print(f"Found {len(links)} PDF links on the listing page")

    for url in links:
        parsed = year_week_from_url(url)
        if parsed is None:
            print(f"[skip] Could not confidently date: {url}")
            continue
        year, week = parsed
        dest_path = RAW_PDF_DIR / f"wer_{year}_w{week:02d}.pdf"
        try:
            download_pdf(url, dest_path)
            print(f"[success] '{dest_path}' was downloaded")
        except requests.RequestException as e:
            print(f"[error] Failed to download {url}: {e}")


if __name__ == "__main__":
    download_all_wer_pdfs()