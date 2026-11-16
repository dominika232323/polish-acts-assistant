"""Download the selected 2026 acts (PDF + metadata) from the Sejm ELI API.

The API serves these acts only as PDF (no HTML text), so we save the PDFs as they are and
write their metadata to data/raw/acts.json. Command line: `scripts/fetch_acts.py`.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from acts.config import ACTS_MANIFEST, DATA_DIR

API = "https://api.sejm.gov.pl/eli/acts/DU/2026"
USER_AGENT = "polish-acts-assistant (student project, WEiTI PW)"

# Standalone acts from Dz.U. 2026: type "Ustawa", excluding amending acts ("o zmianie"),
# ratifications and budget acts. The list is fixed so that the corpus does not change when
# new acts appear in the API; `--discover` shows how it was selected.
ACTS = {
    179: "o ustanowieniu Dnia Inwalidy Wojennego",
    187: "o zawodzie psychologa oraz samorządzie zawodowym psychologów",
    435: "o niekaraniu obywateli RP biorących udział po stronie Ukrainy w konflikcie zbrojnym",
    451: "o wojewódzkich zespołach koordynacji do spraw polityki umiejętności",
    465: "o działalności kosmicznej",
    548: "o zarządzaniu danymi",
    755: "o Krajowym Rejestrze Oznakowanych Psów i Kotów",
    760: "o udziale RP w systemie Eurodac",
    821: "o utworzeniu Wojskowej Akademii Medycznej",
    830: "o szczególnych środkach ochrony w postępowaniu cywilnym osób w debacie publicznej",
    912: "o związku metropolitalnym w województwie pomorskim",
    971: "o szczególnych rozwiązaniach związanych z ewaluacją działalności naukowej 2022-2025",
    985: "o szczególnych rozwiązaniach w sprawach kredytów denominowanych lub indeksowanych",
    986: "o osobach starszych i koordynacji opieki długoterminowej",
    1003: "o systemach sztucznej inteligencji",
    1098: "o osobistych kontach inwestycyjnych",
    1287: "o podatku od nadzwyczajnych zysków ze zbycia paliw ciekłych",
    1308: "o Uniwersytecie Mazowieckim w Płocku",
    1343: "o szczególnych rozwiązaniach związanych z XXVI Światowym Jamboree Skautowym",
    1476: "o umorzeniu należności ZUS powstałych przed dniem 1 stycznia 1999 r.",
}

# Metadata fields kept in acts.json (the full API response has many more).
METADATA_FIELDS = (
    "ELI",
    "displayAddress",
    "pos",
    "title",
    "announcementDate",
    "promulgation",
    "entryIntoForce",
    "status",
    "keywords",
)


def get(url: str, retries: int = 3) -> bytes:
    """GET with a few retries (the API sometimes times out)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as err:
            if attempt == retries:
                raise RuntimeError(f"GET {url} failed: {err}") from err

            time.sleep(2 * attempt)

    raise AssertionError("unreachable")


def get_json(url: str):
    return json.loads(get(url))


def is_standalone(act: dict) -> bool:
    """Selection rule for the corpus (see ACTS)."""
    title = act["title"]

    return (
        act.get("type") == "Ustawa"
        and " o zmianie " not in title
        and "o ratyfikacji" not in title
        and "budżetow" not in title
    )


def discover() -> None:
    """Print standalone acts currently in the API and mark the ones missing from ACTS."""
    items = get_json(API)["items"]

    for act in sorted(filter(is_standalone, items), key=lambda a: a["pos"]):
        mark = " " if act["pos"] in ACTS else "+"
        print(f"{mark} {act['pos']:>5}  {act['title']}")

    print("\n+ = not in ACTS")


def fetch_act(pos: int, force: bool) -> dict:
    """Download one act's PDF and return its metadata (with the local file name)."""
    meta = get_json(f"{API}/{pos}")

    if not meta.get("textPDF"):
        raise RuntimeError(f"{meta['ELI']}: no PDF text in the API")

    file_name = f"D2026{pos:04d}.pdf"
    path = DATA_DIR / file_name

    if force or not path.exists():
        pdf = get(f"{API}/{pos}/text.pdf")

        if not pdf.startswith(b"%PDF"):
            raise RuntimeError(f"{meta['ELI']}: response is not a PDF")

        path.write_bytes(pdf)
        status = f"downloaded ({len(pdf) // 1024} KB)"
    else:
        status = "already exists"

    print(f"{meta['displayAddress']:<22} {status:<22} {meta['title'][:70]}")

    return {field: meta.get(field) for field in METADATA_FIELDS} | {
        "file": file_name,
        "source_url": f"{API}/{pos}/text.pdf",
    }


def fetch_all(force: bool = False) -> list[int]:
    """Download all ACTS, write the manifest and return positions that failed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    acts, failed = [], []

    for pos in ACTS:
        try:
            acts.append(fetch_act(pos, force))
        except RuntimeError as err:
            print(f"ERROR {err}")
            failed.append(pos)

    ACTS_MANIFEST.write_text(
        json.dumps(acts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n{len(acts)}/{len(ACTS)} acts in {DATA_DIR}, metadata: {ACTS_MANIFEST}")

    return failed
