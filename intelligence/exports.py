"""Spreadsheet-safe, in-memory exports, without writing business files."""
from io import BytesIO
import pandas as pd


def safe_frame(frame):
    result = frame.copy()
    for column in result.columns:
        if pd.api.types.is_datetime64_any_dtype(result[column]):
            result[column] = result[column].astype(str)
        result[column] = result[column].map(lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v)
    result.columns = ["'" + str(c) if str(c).lstrip().startswith(('=', '+', '-', '@')) else str(c) for c in result.columns]
    return result


def export_csv(frame):
    return safe_frame(frame).to_csv(index=False).encode('utf-8-sig')


def export_excel(frame):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        safe_frame(frame).to_excel(writer, index=False, sheet_name='Report')
    return output.getvalue()
