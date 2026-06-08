import html


def escape_html(text: str) -> str:
    return html.escape(str(text), quote=False)


def link(url: str, text: str) -> str:
    return f'<a href="{escape_html(url)}">{escape_html(text)}</a>'
