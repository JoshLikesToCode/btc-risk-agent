"""OFAC SDN list: extract listed Bitcoin (XBT) addresses.

The SDN CSV has no header row. Columns are:
ent_num, SDN_Name, SDN_Type, Program, Title, Call_Sign, Vess_type,
Tonnage, GRT, Vess_flag, Vess_owner, Remarks.
Listed crypto addresses appear in Remarks as
"Digital Currency Address - XBT <address>;".
"""

import csv
import io
import re

import httpx
from pydantic import BaseModel

SDN_CSV_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"

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
                entries.append(
                    SanctionEntry(
                        address=address,
                        entity_name=row[_COL_NAME].strip(),
                        program=row[_COL_PROGRAM].strip(),
                        ent_num=row[_COL_ENT_NUM].strip(),
                    )
                )
        return cls(entries)

    def lookup(self, address: str) -> SanctionEntry | None:
        return self._by_address.get(normalize_address(address))


def fetch_sdn_csv(url: str = SDN_CSV_URL, timeout: float = 60.0) -> str:
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.text
