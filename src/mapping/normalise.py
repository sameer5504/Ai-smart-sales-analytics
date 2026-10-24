import re

def normalise(header: str) -> str:
    """Convert a raw file header into a canonical comparable form.

    'Order_Date ' -> 'order date'
    'Price ($)'   -> 'price'
    """
    if header is None:
        return ""
    h = str(header).lower().strip()
    h = re.sub(r"[_\-]+", " ", h)
    h = re.sub(r"[^a-z0-9 ]", "", h)
    return re.sub(r"\s+", " ", h).strip()