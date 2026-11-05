import zipfile

import index_evidence as ie
import network_report as nr
from fact_sources import pages_for_file


def test_docx_text(tmp_path):
    path = tmp_path / "a.docx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="x"><w:body><w:p><w:r><w:t>Resolution 12</w:t></w:r></w:p><w:p><w:r><w:t>approved</w:t></w:r></w:p></w:body></w:document>')
    assert ie.extract_office_pages(path) == ["Resolution 12 approved"]
    assert pages_for_file(path) == ["Resolution 12 approved"]


def test_xlsx_text_with_shared_strings(tmp_path):
    path = tmp_path / "a.xlsx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/sharedStrings.xml", '<sst xmlns="x"><si><t>Parcel</t></si><si><t>Acme</t></si></sst>')
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="x"><sheetData><row><c t="s"><v>0</v></c><c t="s"><v>1</v></c><c><v>42</v></c></row></sheetData></worksheet>')
    assert ie.extract_office_pages(path) == ["Parcel Acme 42"]


def test_bad_office_file_returns_nothing(tmp_path):
    path = tmp_path / "bad.docx"
    path.write_bytes(b"not a zip")
    assert ie.extract_office_pages(path) == []


def test_owner_keeps_trailing_llc():
    text = "located at 703 East Lake Street and is owned by J & M Foster Properties LLC. 4. Next"
    assert nr._OWNER.search(text).group(2) == "J & M Foster Properties LLC"
