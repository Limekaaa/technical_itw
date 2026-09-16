from datetime import datetime
from dateutil import parser
import re

DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

def standardize_date(date_str: str, input_format: str = None) -> str:
    """
    Standardizes a date string to the format: YYYY-MM-DD HH:MM:SS.fff
    
    Args:
        date_str (str): The date string to parse.
        input_format (str, optional): The specific format of the input date.
        
    Returns:
        str: The standardized date string.
    """
    if not date_str:
        return ""

    if input_format:
        dt = datetime.strptime(date_str, input_format)
    else:
        # Heuristic: If the date uses slashes (e.g., 11/01/19), assume DD/MM/YY. 
        # Otherwise, stick to standard ISO formatting (YYYY-MM-DD).
        processed_str = re.sub(r'^(\d{4}):(\d{1,2}):(\d{1,2})', r'\1-\2-\3', date_str)
        is_dayfirst = "/" in processed_str
        dt = parser.parse(processed_str, dayfirst=is_dayfirst)

    # %f generates 6-digit microseconds. Slice the last 3 digits off to get milliseconds (.fff)
    return dt.strftime(DATE_FORMAT)[:-3]

_DATE_ONLY_PATTERNS = (
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$"),
)


def _is_date_only(value: str) -> bool:
    text = value.strip()
    return any(p.match(text) for p in _DATE_ONLY_PATTERNS)


def _resolve_bounds(start_date: str, end_date=None):
    """Return (lower, upper, upper_inclusive) as standardized strings."""
    std_start = standardize_date(start_date)
    start_day = std_start[:10]
    if _is_date_only(start_date):
        lower = f"{start_day} 00:00:00.000"
    else:
        lower = std_start
    if end_date is None:
        return lower, f"{start_day} 23:59:59.999", True
    if _is_date_only(end_date):
        end_day = standardize_date(end_date)[:10]
        return lower, f"{end_day} 23:59:59.999", True
    return lower, standardize_date(end_date), False

def _matches(ts_std: str, lower: str, upper: str, upper_inclusive: bool) -> bool:
    if ts_std < lower:
        return False
    if upper_inclusive:
        return ts_std <= upper
    return ts_std < upper