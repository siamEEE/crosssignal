"""Safe rendering of external text inside Streamlit Markdown."""

# Streamlit Markdown also interprets $...$ (LaTeX) and :directives[...],
# so escape every punctuation character that can start markup.
_MARKDOWN_SPECIAL = set("\\`*_{}[]()#+-.!|$<>~:")


def escape_markdown(text: str) -> str:
    return "".join(f"\\{c}" if c in _MARKDOWN_SPECIAL else c for c in text)


def markdown_link(label: str, url: str) -> str:
    """A Markdown link whose label and URL cannot break out of the syntax."""
    safe_url = url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
    return f"[{escape_markdown(label)}]({safe_url})"


def join_names(names: list[str]) -> str:
    """'A', 'A and B', or 'A, B and C'."""
    if len(names) <= 2:
        return " and ".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"
