"""EPUB export with HTML chapters, table of contents, and CSS styling."""
import html
import zipfile
from pathlib import Path


_CSS = """/* style.css */
body {
  font-family: "Palatino Linotype", "Book Antiqua", Palatino, Georgia, serif;
  font-size: 1.1em;
  line-height: 1.6;
  margin: 2em;
  color: #222;
}
h1 {
  text-align: center;
  font-size: 1.6em;
  margin-bottom: 1em;
  font-weight: bold;
}
p {
  text-indent: 1.5em;
  margin: 0.3em 0;
}
nav ol {
  list-style-type: none;
  padding: 0;
}
nav li {
  margin: 0.5em 0;
}
a { color: #333; text-decoration: none; }
"""


def _chapter_xhtml(ch_num: int, title: str, body: str) -> str:
    paras = "".join(
        f"<p>{html.escape(p.strip())}</p>\n"
        for p in body.strip().split("\n\n")
        if p.strip()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        "<head>\n"
        '  <meta charset="UTF-8"/>\n'
        f"  <title>{html.escape(title)}</title>\n"
        '  <link rel="stylesheet" type="text/css" href="style.css"/>\n'
        "</head>\n"
        "<body>\n"
        f"  <h1>{html.escape(title)}</h1>\n"
        f"{paras}"
        "</body>\n"
        "</html>"
    )


def _toc_xhtml(title: str, chapters: list[dict]) -> str:
    items = "".join(
        f'      <li><a href="chapter_{ch["chapter_num"]}.xhtml">'
        f'{html.escape(ch.get("title_vi", "Chương " + str(ch["chapter_num"])))}'
        f"</a></li>\n"
        for ch in chapters
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        "<head>\n"
        '  <meta charset="UTF-8"/>\n'
        "  <title>Mục lục</title>\n"
        '  <link rel="stylesheet" type="text/css" href="style.css"/>\n'
        "</head>\n"
        "<body>\n"
        "  <h1>Mục lục</h1>\n"
        '  <nav epub:type="toc">\n'
        "    <ol>\n"
        f"{items}"
        "    </ol>\n"
        "  </nav>\n"
        "</body>\n"
        "</html>"
    )


def _ncx(title: str, chapters: list[dict]) -> str:
    nav_points = "".join(
        f'  <navPoint id="navPoint-{i+1}" playOrder="{i+1}">\n'
        f'    <navLabel><text>'
        f'{html.escape(ch.get("title_vi", "Chương " + str(ch["chapter_num"])))}'
        f'</text></navLabel>\n'
        f'    <content src="chapter_{ch["chapter_num"]}.xhtml"/>\n'
        f"  </navPoint>\n"
        for i, ch in enumerate(chapters)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" '
        '"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005.1">\n'
        "  <head>\n"
        f'    <meta name="dtb:uid" content="urn:uuid:translate-comics-{html.escape(title)}"/>\n'
        '    <meta name="dtb:depth" content="1"/>\n'
        '    <meta name="dtb:totalPageCount" content="0"/>\n'
        '    <meta name="dtb:maxPageNumber" content="0"/>\n'
        "  </head>\n"
        f"  <docTitle><text>{html.escape(title)}</text></docTitle>\n"
        "  <navMap>\n"
        f"{nav_points}"
        "  </navMap>\n"
        "</ncx>"
    )


def _content_opf(title: str, author: str, chapters: list[dict]) -> str:
    uid = f"urn:uuid:translate-comics-{html.escape(title)}"
    chapter_items = "".join(
        f'    <item id="chapter_{ch["chapter_num"]}" '
        f'href="chapter_{ch["chapter_num"]}.xhtml" '
        'media-type="application/xhtml+xml"/>\n'
        for ch in chapters
    )
    spine_items = "".join(
        f'    <itemref idref="chapter_{ch["chapter_num"]}"/>\n'
        for ch in chapters
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        'unique-identifier="pub-id">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'    <dc:identifier id="pub-id">{uid}</dc:identifier>\n'
        f"    <dc:title>{html.escape(title)}</dc:title>\n"
        "    <dc:language>vi</dc:language>\n"
        f"    <dc:creator>{html.escape(author)}</dc:creator>\n"
        "  </metadata>\n"
        "  <manifest>\n"
        '    <item id="toc" properties="nav" href="toc.xhtml" '
        'media-type="application/xhtml+xml"/>\n'
        '    <item id="ncx" href="toc.ncx" '
        'media-type="application/x-dtbncx+xml"/>\n'
        '    <item id="css" href="style.css" media-type="text/css"/>\n'
        f"{chapter_items}"
        "  </manifest>\n"
        '  <spine toc="ncx">\n'
        f"{spine_items}"
        "  </spine>\n"
        "</package>"
    )


def export_epub(
    output_path: str,
    title: str,
    author: str,
    genre: str,
    chapters: list[dict],
    characters: list[dict],
    terms: list[dict],
) -> str:
    """Generate a standards-compliant EPUB 3 file (no external deps)."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be first and uncompressed
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        zf.writestr(
            "META-INF/container.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<container version="1.0" '
                'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
                "  <rootfiles>\n"
                '    <rootfile full-path="OEBPS/content.opf" '
                'media-type="application/oebps-package+xml"/>\n'
                "  </rootfiles>\n"
                "</container>"
            ),
        )

        zf.writestr("OEBPS/content.opf", _content_opf(title, author, chapters))
        zf.writestr("OEBPS/toc.xhtml", _toc_xhtml(title, chapters))
        zf.writestr("OEBPS/toc.ncx", _ncx(title, chapters))
        zf.writestr("OEBPS/style.css", _CSS)

        for ch in chapters:
            ch_num = ch["chapter_num"]
            ch_title = ch.get("title_vi", f"Chương {ch_num}")
            body = ch.get("content_vi", "")
            zf.writestr(
                f"OEBPS/chapter_{ch_num}.xhtml",
                _chapter_xhtml(ch_num, ch_title, body),
            )

    return str(path)
