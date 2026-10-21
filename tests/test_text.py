from crosssignal.text import escape_markdown, join_names, markdown_link


def test_escape_markdown_neutralises_markup():
    assert escape_markdown("**$5** :red[x]") == r"\*\*\$5\*\* \:red\[x\]"


def test_plain_text_is_unchanged():
    assert escape_markdown("Midnight City") == "Midnight City"


def test_markdown_link_encodes_breaking_characters():
    link = markdown_link("Roads (Live)", "https://music.apple.com/a b(c)")
    assert link == r"[Roads \(Live\)](https://music.apple.com/a%20b%28c%29)"


def test_join_names_reads_naturally():
    assert join_names(["A"]) == "A"
    assert join_names(["A", "B"]) == "A and B"
    assert join_names(["A", "B", "C"]) == "A, B and C"
