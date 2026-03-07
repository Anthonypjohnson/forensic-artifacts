import csv
import io

from flask import Response

_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def make_csv_response(headers: list, rows: list, filename: str) -> Response:
    """Return a CSV file download Response built from a list of row dicts."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=headers, extrasaction="ignore", lineterminator="\r\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({h: (row.get(h) if row.get(h) is not None else "") for h in headers})
    csv_bytes = output.getvalue().encode("utf-8-sig")  # BOM for Excel compat
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def make_template_csv(headers: list, example: dict, filename: str) -> Response:
    """Return a header-only CSV with one example row for download."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=headers, extrasaction="ignore", lineterminator="\r\n"
    )
    writer.writeheader()
    writer.writerow({h: (example.get(h, "") or "") for h in headers})
    csv_bytes = output.getvalue().encode("utf-8-sig")
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def parse_csv_upload(file_storage) -> tuple:
    """
    Parse an uploaded CSV FileStorage object.
    Returns (rows: list[dict], error: str | None).
    Keys are stripped and lowercased; values are stripped of whitespace.
    """
    try:
        content = file_storage.read(_MAX_BYTES + 1)
        if len(content) > _MAX_BYTES:
            return [], "File exceeds the 5 MB size limit."
        if not content:
            return [], "Uploaded file is empty."
        text = content.decode("utf-8-sig")  # strip BOM if Excel-generated
    except Exception as exc:
        return [], f"Could not read file: {exc}"

    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = []
        for row in reader:
            clean = {
                k.strip().lower(): (v.strip() if v else "")
                for k, v in row.items()
            }
            rows.append(clean)
    except Exception as exc:
        return [], f"CSV parse error: {exc}"

    if not rows:
        return [], "CSV file contains no data rows."

    return rows, None
