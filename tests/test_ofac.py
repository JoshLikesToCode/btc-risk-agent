from pathlib import Path

import pytest

from btc_risk.sanctions import SanctionsList

FIXTURE = Path(__file__).parent / "fixtures" / "sdn_sample.csv"


@pytest.fixture(scope="module")
def sanctions() -> SanctionsList:
    return SanctionsList.from_csv_text(FIXTURE.read_text())


def test_only_xbt_addresses_are_extracted(sanctions):
    # two XBT addresses on entity A; the ETH address and other rows are ignored
    assert len(sanctions) == 2


def test_base58_lookup_returns_entry(sanctions):
    entry = sanctions.lookup("1ExampleBase58AddressAAAAAAAAAAAAAA")
    assert entry is not None
    assert entry.entity_name == "EXAMPLE ENTITY A"
    assert entry.program == "CYBER2"
    assert entry.ent_num == "1001"


def test_base58_lookup_is_case_sensitive(sanctions):
    assert sanctions.lookup("1examplebase58addressaaaaaaaaaaaaaa") is None


def test_bech32_lookup_is_case_insensitive(sanctions):
    assert sanctions.lookup("BC1QEXAMPLEBECH32ADDRESSAAAAAAAAAAAAAAAAAAA") is not None


def test_unlisted_address_returns_none(sanctions):
    assert sanctions.lookup("1NotListedAddressBBBBBBBBBBBBBBBBB") is None


def test_short_or_blank_rows_are_skipped():
    assert len(SanctionsList.from_csv_text("\n1,2,3\n")) == 0


XML_FIXTURE = Path(__file__).parent / "fixtures" / "sdn_sample.xml"


def test_xml_parser_extracts_only_xbt_with_name_and_programs():
    s = SanctionsList.from_xml(XML_FIXTURE)
    assert len(s) == 2
    entry = s.lookup("1ExampleBase58AddressAAAAAAAAAAAAAA")
    assert entry.entity_name == "ENTITY A, Example"
    assert entry.program == "CYBER2, DPRK3"
    assert entry.ent_num == "1001"
    assert s.lookup("BC1QEXAMPLEBECH32ADDRESSAAAAAAAAAAAAAAAAAAA") is not None


def test_csv_parser_drops_truncated_address_fragments():
    row = '1,"X",-0- ,"CYBER2",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,"Digital Currency Address - XBT 1Gq"'
    assert len(SanctionsList.from_csv_text(row)) == 0
