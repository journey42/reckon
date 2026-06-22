from rhiz.utils.slugs import slugify, unique_slug


def test_slugify_basic():
    assert slugify("Housing is a Human Right!") == "housing-is-a-human-right"


def test_slugify_collapses_and_trims():
    assert slugify("  Multiple   Spaces & Symbols?? ") == "multiple-spaces-symbols"


def test_slugify_empty_fallback():
    assert slugify("!!!") == "debate"


def test_unique_slug_appends_suffix():
    taken = {"housing", "housing-2"}
    assert unique_slug("housing", lambda s: s in taken) == "housing-3"


def test_unique_slug_free_returns_base():
    assert unique_slug("free", lambda s: False) == "free"
