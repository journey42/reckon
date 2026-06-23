from rhiz.utils.urls import safe_next_path


def test_accepts_relative_paths():
    assert safe_next_path("/debate/housing") == "/debate/housing"
    assert safe_next_path("/your_drafts") == "/your_drafts"


def test_rejects_external_and_tricks():
    for bad in [
        "//evil.com", "/\\evil.com", "http://evil.com", "https://evil.com",
        "javascript:alert(1)", "/%2Fevil.com", "/%2f%2fevil.com",
        "%2F%2Fevil.com", "evil.com", None, "",
    ]:
        assert safe_next_path(bad) is None
