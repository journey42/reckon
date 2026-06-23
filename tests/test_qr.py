import base64
from rhiz.utils.qr import qr_data_uri


def test_qr_data_uri_prefix():
    uri = qr_data_uri("https://example.com/debate/housing")
    assert uri.startswith("data:image/png;base64,")


def test_qr_data_uri_decodes_to_png():
    uri = qr_data_uri("https://example.com/debate/housing")
    payload = uri.split(",", 1)[1]
    raw = base64.b64decode(payload)
    # PNG magic number
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
