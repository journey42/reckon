"""Generate a QR code as a base64 PNG data URI."""

import base64
import io

import qrcode


def qr_data_uri(url: str) -> str:
    """Return a PNG data URI containing a QR code for `url`."""
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
