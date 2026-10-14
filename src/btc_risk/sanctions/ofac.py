"""OFAC SDN list: extract listed Bitcoin (XBT) addresses.

Use the XML export (`from_xml`). It lists each address as an `<id>` element and is complete.

The CSV export (`from_csv_text`) is kept for tests and quick looks only: its Remarks column is
length-capped, so long remarks are cut off mid-address and every address after the cut is silently
missing (about half of the listed Bitcoin addresses at the time of writing). Truncated fragments
are dropped by an address-shape check, but the missing ones cannot be recovered.

CSV columns (no header row): ent_num, SDN_Name, SDN_Type, Program, Title, Call_Sign, Vess_type,
Tonnage, GRT, Vess_flag, Vess_owner, Remarks. Addresses appear in Remarks as
"Digital Currency Address - XBT <address>;".
"""

import csv
import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from pydantic import BaseModel

SDN_CSV_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
SDN_XML_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
_XBT_ID_TYPE = "Digital Currency Address - XBT"
# Shape check only (charset + length); rejects truncated fragments such as "1Gq" or "3".
_ADDRESS_SHAPE = re.compile(
    r"^(bc1[a-z0-9]{20,90}|[13][a-km-zA-HJ-NP-Z1-9]{25,39})$", re.IGNORECASE
)

_XBT_RE = re.compile(r"Digital Currency Address - XBT\s+([A-Za-z0-9]+)")
_COL_ENT_NUM, _COL_NAME, _COL_PROGRAM, _COL_REMARKS = 0, 1, 3, 11


class SanctionEntry(BaseModel):
    address: str
    entity_name: str
    program: str
    ent_num: str


def normalize_address(address: str) -> str:
    """Bech32 addresses are case-insensitive; base58 addresses are not."""
    address = address.strip()
    return address.lower() if address.lower().startswith(("bc1", "tb1")) else address


class SanctionsList:
    def __init__(self, entries: list[SanctionEntry]):
        self._by_address = {normalize_address(e.address): e for e in entries}

    def __len__(self) -> int:
        return len(self._by_address)

    @classmethod
    def from_csv_text(cls, text: str) -> "SanctionsList":
        entries: list[SanctionEntry] = []
        for row in csv.reader(io.StringIO(text)):
            if len(row) <= _COL_REMARKS:
                continue
            for address in _XBT_RE.findall(row[_COL_REMARKS]):
                if not _ADDRESS_SHAPE.match(address):
                    continue  # truncated by the CSV's remark length cap
                entries.append(
                    SanctionEntry(
                        address=address,
                        entity_name=row[_COL_NAME].strip(),
                        program=row[_COL_PROGRAM].strip(),
                        ent_num=row[_COL_ENT_NUM].strip(),
                    )
                )
        return cls(entries)

    @classmethod
    def from_xml(cls, source: str | Path) -> "SanctionsList":
        """Parse the SDN XML export (path to file, streamed) into a list of XBT addresses."""
        entries: list[SanctionEntry] = []
        for _, elem in ET.iterparse(str(source), events=("end",)):
            if not elem.tag.endswith("sdnEntry"):
                continue
            ns = elem.tag[: elem.tag.index("}") + 1] if elem.tag.startswith("{") else ""
            uid = (elem.findtext(f"{ns}uid") or "").strip()
            name = ", ".join(
                p.strip()
                for p in (elem.findtext(f"{ns}lastName"), elem.findtext(f"{ns}firstName"))
                if p and p.strip()
            )
            programs = ", ".join(
                (p.text or "").strip() for p in elem.findall(f"{ns}programList/{ns}program")
            )
            for id_el in elem.findall(f"{ns}idList/{ns}id"):
                if (id_el.findtext(f"{ns}idType") or "").strip() == _XBT_ID_TYPE:
                    address = (id_el.findtext(f"{ns}idNumber") or "").strip()
                    if address:
                        entries.append(
                            SanctionEntry(
                                address=address, entity_name=name, program=programs, ent_num=uid
                            )
                        )
            elem.clear()
        return cls(entries)

    def lookup(self, address: str) -> SanctionEntry | None:
        return self._by_address.get(normalize_address(address))


def fetch_sdn_csv(url: str = SDN_CSV_URL, timeout: float = 60.0) -> str:
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.text


def download_sdn_xml(dest: Path, url: str = SDN_XML_URL, timeout: float = 180.0) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
    tmp.replace(dest)  # never leave a half-downloaded list in place
