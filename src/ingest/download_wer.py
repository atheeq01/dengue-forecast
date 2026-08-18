import re
from pathlib import Path
import requests

from src.config import RAW_PDF_DIR

LISTING_URL = "https://www.epid.gov.lk/weekly-epidemiological-report"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/pdf,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

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

def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        REQUEST_HEADERS
    )
    return session


def download_pdf(
    url:str,
    dest_path:Path,
    session: requests.Session | None = None,
) -> bool:
    if dest_path.exists():
        return False
    if session is None:
        session = make_session()
    resp = session.get(url,timeout=30)
    resp.raise_for_status()
    dest_path.write_bytes(resp.content)
    return True

def download_all_wer_pdfs() -> dict[str, int]:
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    session = make_session()
    listing= session.get(LISTING_URL,timeout=30)
    listing.raise_for_status()

    links = find_pdf_links(listing.text)
    print(f"Found {len(links)} PDF links on the listing page")

    counts = {
        "found": len(links),
        "downloaded": 0,
        "existing": 0,
        "skipped": 0,
        "errors": 0,
    }

    for url in links:
        parsed = year_week_from_url(url)
        if parsed is None:
            counts["skipped"] += 1
            print(f"[skip] Could not confidently date: {url}")
            continue
        year, week = parsed
        dest_path = RAW_PDF_DIR / f"wer_{year}_w{week:02d}.pdf"
        try:
            downloaded = download_pdf(
                url,
                dest_path,
                session=session,
            )
            if downloaded:
                counts["downloaded"] += 1
                print(f"[downloaded] {dest_path}")
            else:
                counts["existing"] += 1
        except requests.RequestException as e:
            counts["errors"] += 1
            print(f"[error] Failed to download {url}: {e}")

    print(
        "[WER download] "
        f"downloaded={counts['downloaded']:,}, "
        f"existing={counts['existing']:,}, "
        f"skipped={counts['skipped']:,}, "
        f"errors={counts['errors']:,}"
    )

    return counts


if __name__ == "__main__":
    download_all_wer_pdfs()
