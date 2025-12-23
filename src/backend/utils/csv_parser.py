"""CSV parser for leads."""
import csv
from io import StringIO
from typing import Any


def get_csv_headers(csv_content: str) -> list[str]:
    """Get CSV headers (column names).

    Args:
        csv_content: CSV file content as string

    Returns:
        List of column names

    Raises:
        ValueError: If CSV format is invalid
    """
    try:
        reader = csv.DictReader(StringIO(csv_content))
        return list(reader.fieldnames or [])
    except Exception as e:
        raise ValueError(f"Invalid CSV format: {e}")


def parse_csv_leads(csv_content: str, column_mapping: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Parse CSV content and extract leads.

    Expected CSV format:
    - First row: headers (phone, name, and other columns)
    - Subsequent rows: lead data

    Args:
        csv_content: CSV file content as string
        column_mapping: Optional mapping from CSV column names to field names
                        (e.g., {"Email": "email", "Company": "company"})
                        If None, uses automatic detection for phone and name

    Returns:
        List of lead dictionaries with all columns preserved

    Raises:
        ValueError: If CSV format is invalid
    """
    leads = []
    reader = csv.DictReader(StringIO(csv_content))

    for row_num, row in enumerate(reader, start=2):  # Start from 2 (header is row 1)
        lead_data: dict[str, Any] = {}
        
        # If column mapping is provided, use it
        if column_mapping:
            for csv_column, field_name in column_mapping.items():
                if csv_column in row:
                    value = row[csv_column]
                    if value:
                        lead_data[field_name] = value.strip()
            
            # Validate required fields when using column mapping
            if "phone" not in lead_data or "name" not in lead_data:
                raise ValueError(f"Row {row_num}: Missing required fields (phone, name) in column mapping")
        else:
            # Auto-detect phone and name (backward compatibility)
            phone = None
            name = None

            for key, value in row.items():
                key_lower = key.lower().strip()
                if key_lower in ["phone", "телефон", "tel", "номер"]:
                    phone = value.strip() if value else None
                elif key_lower in ["name", "имя", "fio", "фио"]:
                    name = value.strip() if value else None
                else:
                    # Preserve other columns
                    if value:
                        lead_data[key] = value.strip()

            # If not found by header, try first two columns
            if not phone or not name:
                values = list(row.values())
                if len(values) >= 2:
                    if not phone:
                        phone = values[0].strip() if values[0] else None
                    if not name:
                        name = values[1].strip() if values[1] else None

            if not phone or not name:
                raise ValueError(f"Row {row_num}: Missing required fields (phone, name)")

            lead_data["phone"] = phone
            lead_data["name"] = name

        # Validate required fields
        if "phone" not in lead_data or "name" not in lead_data:
            raise ValueError(f"Row {row_num}: Missing required fields (phone, name)")

        leads.append(lead_data)

    if not leads:
        raise ValueError("No leads found in CSV file")

    return leads

