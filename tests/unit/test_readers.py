"""Reading CSV and XLSX sources into datasets."""

from __future__ import annotations

import datetime as dt
import zipfile
from decimal import Decimal

import pytest
from openpyxl import Workbook

from data_automation.config import InputSpec
from data_automation.readers import InputReadError, read_input
from data_automation.types import python_values


def _spec(**overrides):
    data = {"id": "sales", "type": "csv", "path": "x.csv"} | overrides
    return InputSpec.model_validate(data)


def _write(tmp_path, name, content, encoding="utf-8"):
    path = tmp_path / name
    path.write_bytes(content.encode(encoding) if isinstance(content, str) else content)
    return path


def test_csv_typed_columns_and_missing_values(tmp_path):
    path = _write(tmp_path, "s.csv", "id,amount,day\n007,12.50,2026-09-01\n008,,2026-09-02\n")
    result = read_input(_spec(types={"amount": "decimal", "day": "date"}), [path], tmp_path)
    frame = result.dataset.frame()
    assert result.dataset.types == {"id": "string", "amount": "decimal", "day": "date"}
    assert python_values(frame["id"]) == ["007", "008"]  # identifiers stay text: leading zeros kept
    assert python_values(frame["amount"]) == [Decimal("12.50"), None]  # empty = missing, never 0
    assert python_values(frame["day"]) == [dt.date(2026, 9, 1), dt.date(2026, 9, 2)]
    assert result.files == [{"path": "s.csv", "rows": 2, "columns": ["id", "amount", "day"]}]


def test_invalid_typed_values_fail_with_file_row_and_value(tmp_path):
    path = _write(tmp_path, "s.csv", 'amount\n1.5\n"1,5"\nabc\n')
    with pytest.raises(InputReadError) as info:
        read_input(_spec(types={"amount": "decimal"}), [path], tmp_path)
    message = str(info.value)
    assert message.startswith("s.csv: column 'amount': 2 value(s) are not valid decimal")
    assert "row 3: '1,5'" in message and "row 4: 'abc'" in message


def test_decimal_comma_and_semicolon_delimiter(tmp_path):
    path = _write(tmp_path, "s.csv", "amount;label\n1234,50;x\n")
    result = read_input(_spec(types={"amount": "decimal"}, decimal_separator=",", delimiter=";"), [path], tmp_path)
    assert python_values(result.dataset.frame()["amount"]) == [Decimal("1234.50")]


def test_one_part_per_file_with_origin(tmp_path):
    a = _write(tmp_path, "a.csv", "x\n1\n")
    b = _write(tmp_path, "b.csv", "x\n2\n3\n")
    dataset = read_input(_spec(), [a, b], tmp_path).dataset
    assert [(p.origin, len(p.frame)) for p in dataset.parts] == [("a.csv", 1), ("b.csv", 2)]
    assert dataset.rows == 3
    with pytest.raises(ValueError, match="combine them with a 'concatenate' step"):
        dataset.frame()


@pytest.mark.parametrize(
    "content, message",
    [
        ("a,b\n1,2\n3\n", "line 3 (1 fields)"),
        ("a,a\n1,2\n", "duplicate column name(s) ['a']"),
        ("a,,c\n1,2,3\n", "column(s) 2 have no name"),
        ('a,b\n"unclosed,2\n', "invalid CSV"),
    ],
)
def test_malformed_csv_fails(tmp_path, content, message):
    with pytest.raises(
        InputReadError, match=message.replace("(", r"\(").replace(")", r"\)").replace("[", r"\[").replace("]", r"\]")
    ):
        read_input(_spec(), [_write(tmp_path, "s.csv", content)], tmp_path)


def test_required_and_declared_columns_must_exist(tmp_path):
    path = _write(tmp_path, "s.csv", "region\nNorth\n")
    with pytest.raises(InputReadError, match=r"missing column\(s\) 'amount'"):
        read_input(_spec(required_columns=["region", "amount"]), [path], tmp_path)
    with pytest.raises(InputReadError, match=r"missing column\(s\) 'day'"):
        read_input(_spec(types={"day": "date"}), [path], tmp_path)


def test_encodings(tmp_path):
    bom = _write(tmp_path, "bom.csv", "city\nZürich\n", encoding="utf-8-sig")
    assert list(read_input(_spec(), [bom], tmp_path).dataset.frame().columns) == ["city"]
    latin = _write(tmp_path, "latin.csv", "city\nMontréal\n", encoding="cp1252")
    with pytest.raises(InputReadError, match="not valid utf-8"):
        read_input(_spec(), [latin], tmp_path)
    result = read_input(_spec(encoding="cp1252"), [latin], tmp_path)
    assert python_values(result.dataset.frame()["city"]) == ["Montréal"]


def test_empty_file_policy(tmp_path):
    empty = _write(tmp_path, "empty.csv", "")
    full = _write(tmp_path, "full.csv", "x\n1\n")
    with pytest.raises(InputReadError, match="empty.csv is empty"):
        read_input(_spec(), [empty, full], tmp_path)
    result = read_input(_spec(on_empty_file="skip"), [empty, full], tmp_path)
    assert result.dataset.rows == 1 and "empty.csv is empty and was skipped" in result.warnings[0]
    with pytest.raises(InputReadError, match="all 1 matching file"):
        read_input(_spec(on_empty_file="skip"), [empty], tmp_path)


def test_header_only_file_gives_zero_rows(tmp_path):
    result = read_input(_spec(types={"x": "integer"}), [_write(tmp_path, "h.csv", "x\n")], tmp_path)
    assert result.dataset.rows == 0 and result.dataset.types == {"x": "integer"}


def test_no_file_with_warn_policy_gives_empty_declared_dataset(tmp_path):
    result = read_input(
        _spec(required_columns=["region"], types={"amount": "decimal"}, on_empty_match="warn"), [], tmp_path
    )
    assert result.dataset.columns == ["region", "amount"] and result.dataset.rows == 0


def _xlsx(tmp_path, rows, name="s.xlsx", sheet="Data", extra_sheet=False):
    workbook = Workbook()
    workbook.active.title = sheet
    for row in rows:
        workbook.active.append(row)
    if extra_sheet:
        workbook.create_sheet("Other").append(["z"])
    path = tmp_path / name
    workbook.save(path)
    return path


def test_xlsx_typed_cells_are_read_without_loss(tmp_path):
    path = _xlsx(tmp_path, [["code", "qty", "price", "day"], ["007", 3, 19.99, dt.datetime(2026, 9, 1)]])
    spec = _spec(type="xlsx", path="s.xlsx", types={"qty": "integer", "price": "decimal", "day": "date"})
    frame = read_input(spec, [path], tmp_path).dataset.frame()
    assert python_values(frame["code"]) == ["007"]
    assert python_values(frame["qty"]) == [3]
    assert python_values(frame["price"]) == [Decimal("19.99")]
    assert python_values(frame["day"]) == [dt.date(2026, 9, 1)]


def test_xlsx_numbers_never_use_exponents_and_follow_the_decimal_separator(tmp_path):
    path = _xlsx(tmp_path, [["rate", "big"], [0.00001, 1.5e20], [-2.5, 3.0]])
    types = {"rate": "decimal", "big": "decimal"}
    frame = read_input(_spec(type="xlsx", path="s.xlsx", types=types), [path], tmp_path).dataset.frame()
    assert python_values(frame["rate"]) == [Decimal("0.00001"), Decimal("-2.5")]
    assert python_values(frame["big"]) == [Decimal("150000000000000000000"), Decimal("3")]
    comma = _spec(type="xlsx", path="s.xlsx", types=types, decimal_separator=",")
    assert python_values(read_input(comma, [path], tmp_path).dataset.frame()["rate"]) == [
        Decimal("0.00001"),
        Decimal("-2.5"),
    ]


def test_xlsx_time_of_day_is_not_truncated_to_a_date(tmp_path):
    path = _xlsx(tmp_path, [["day"], [dt.datetime(2026, 9, 1, 14, 30)]])
    with pytest.raises(InputReadError, match="not valid date"):
        read_input(_spec(type="xlsx", path="s.xlsx", types={"day": "date"}), [path], tmp_path)


def test_xlsx_sheet_selection(tmp_path):
    path = _xlsx(tmp_path, [["a"], [1]], extra_sheet=True)
    assert read_input(_spec(type="xlsx", path="s.xlsx", sheet="Other"), [path], tmp_path).dataset.columns == ["z"]
    with pytest.raises(InputReadError, match=r"sheet 'Missing' not found \(available: Data, Other\)"):
        read_input(_spec(type="xlsx", path="s.xlsx", sheet="Missing"), [path], tmp_path)


def test_xlsx_uncalculated_formulas_fail(tmp_path):
    path = _xlsx(tmp_path, [["qty", "total"], [2, "=A2*3"]])
    with pytest.raises(InputReadError, match="1 formula cell.*have no saved value"):
        read_input(_spec(type="xlsx", path="s.xlsx"), [path], tmp_path)


def test_xlsx_values_outside_header_fail(tmp_path):
    path = _xlsx(tmp_path, [["a"], [1, "stray"]])
    with pytest.raises(InputReadError, match="row 2 has values outside the 1 header column"):
        read_input(_spec(type="xlsx", path="s.xlsx"), [path], tmp_path)


def test_corrupt_or_unsafe_xlsx_fails_cleanly(tmp_path):
    fake = _write(tmp_path, "s.xlsx", b"not a zip")
    with pytest.raises(InputReadError, match="cannot be opened as an .xlsx workbook"):
        read_input(_spec(type="xlsx", path="s.xlsx"), [fake], tmp_path)
    # a workbook whose XML declares entities (the basis of 'billion laughs' attacks)
    good = _xlsx(tmp_path, [["a"], [1]], name="good.xlsx")
    unsafe = tmp_path / "unsafe.xlsx"
    with zipfile.ZipFile(good) as src, zipfile.ZipFile(unsafe, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "xl/workbook.xml":
                assert data.startswith(b"<workbook")  # the injection below must really change the file
                data = b'<!DOCTYPE workbook [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>' + data
            dst.writestr(item, data)
    with pytest.raises(InputReadError, match="unsafe XML"):
        read_input(_spec(type="xlsx", path="unsafe.xlsx"), [unsafe], tmp_path)
