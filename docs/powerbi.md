# Power BI import

The toolkit **prepares files** for Power BI Desktop; it does not connect to Power BI,
publish to Power BI Service or refresh reports.

> **Not tested in Power BI Desktop.** The export format below is tested automatically
> (exact bytes for CSV, typed cells for XLSX). How Power BI Desktop reads these files has
> **not** been verified: the recommendations in this page follow Microsoft's documented
> behaviour of the Text/CSV connector and Power Query, and the M query below has never been
> run. Treat them as a starting point and check the column types after the first import.

## The export contract

| | CSV (recommended) | XLSX |
| --- | --- | --- |
| Encoding | UTF-8 **without BOM**, LF line endings | — |
| Layout | One header row, `,` delimiter, RFC 4180 quoting | One named sheet, one header row |
| Numbers | `.` decimal separator, no thousands separator, no currency sign; decimals keep their places (`162.50`) | Numeric cells |
| Dates | `YYYY-MM-DD`; datetimes `YYYY-MM-DDTHH:MM:SS` | Date cells formatted `yyyy-mm-dd` (datetimes `yyyy-mm-dd hh:mm:ss`) |
| Booleans | `true` / `false` | Boolean cells |
| Text | As is (leading zeros kept; `=SUM(...)` stays text) | Text cells, never formulas |
| Missing | Empty field | Empty cell |

Each file has a [`.metadata.json`](running.md#export-metadata) file with the type of every
column. Power BI does not read it; it documents which type to set in Power Query.

The output path does not change between runs of the same period (`--overwrite` replaces
the file in place after verification), so a Power BI file that imports
`output/monthly_sales_2026-09.csv` can be refreshed after a new run. Files of a new period
have a new name (`{period}` in the path); importing a folder is an alternative.

## Recommended import settings (untested)

1. *Get data* → *Text/CSV*, choose the file.
2. *File origin*: **65001: Unicode (UTF-8)**. Without a BOM, automatic detection may pick
   another code page and break accented letters.
3. *Delimiter*: comma. *Data type detection*: preferably *Do not detect data types*, then
   set the types yourself (step 4).
4. Set the types with the **en-US locale** when Power BI runs with French (or another
   comma-decimal) regional settings: *Transform data* → right-click a column → *Change
   type* → *Using locale…* → *Decimal number*, *English (United States)*. Otherwise
   `162.50` may be read as text or as 16250.

## Power Query example (untested)

For `reports/examples/sales-vs-targets/output/sales_vs_targets_2026-09.csv`; replace the
path:

```text
let
    Source = Csv.Document(
        File.Contents("C:\path\to\output\sales_vs_targets_2026-09.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Headers,
        {
            {"region", type text},
            {"total_sales", type number},
            {"target", type number},
            {"order_count", Int64.Type},
            {"average_order", type number}
        },
        "en-US"
    )
in
    Typed
```

`Table.TransformColumnTypes` with the culture `"en-US"` reads `.` as the decimal separator
whatever the regional settings. Use `type date` for date columns (ISO dates are read the
same way in every culture) and `Currency.Type` (fixed decimal) if exact cents matter.

## XLSX notes

- Numbers are stored as Excel numbers, which do not keep trailing zeros: `250.00` is
  displayed and imported as `250` (the value is the same). Decimal places are recorded in
  the metadata file (`decimal_places`).
- Excel numbers are binary floating point (about 15 significant digits). A decimal that
  an Excel number cannot hold exactly, or an integer above 2^53, makes the export fail
  instead of being rounded silently; use CSV for such values.
- Dates are real date cells; Power BI should type them as dates without a locale.
