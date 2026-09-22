from note_auto_poster.sessions import session_key


def test_strips_numbered_suffix_with_fullwidth_space():
    assert session_key("夜撮影会　その④") == "夜撮影会"


def test_strips_numbered_suffix_with_halfwidth_space():
    assert session_key("夜撮影会 その⑤") == "夜撮影会"


def test_strips_trailing_emoji():
    assert session_key("BBQ撮影会 🆕") == "BBQ撮影会"


def test_strips_suffix_with_no_space():
    assert session_key("制服撮影会その②") == "制服撮影会"


def test_title_without_suffix_is_unchanged():
    assert session_key("福岡撮影会") == "福岡撮影会"


def test_never_returns_empty_string():
    assert session_key("その①") == "その①"
