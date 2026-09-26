import pymupdf
import pytest

from app.ingest import extract_evidence


def test_csv_source_row_and_python_summary():
    items = extract_evidence("log.csv", b"status,component\n500,api\n200,api\n")
    assert items[0]["row_num"] == 2
    assert items[0]["locator"] == "CSV row 2"
    assert "Calculated row count: 2" in items[-1]["content"]
    assert "500=1" in items[-1]["content"]
    assert "200=1" in items[-1]["content"]
    assert items[-1]["row_end"] == 3


def test_pdf_page_location():
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Synthetic inspection note")
    items = extract_evidence("note.pdf", pdf.tobytes())
    assert items[0]["page_num"] == 1
    assert items[0]["locator"] == "page 1, chunk 1"


def test_unsupported_file_rejected():
    with pytest.raises(ValueError):
        extract_evidence("script.py", b"print('unsafe')")
