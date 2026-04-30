"""Convert a Markdown file to a minimal .docx (no external deps).

Supports headings (#, ##, ###) and plain paragraphs.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple
from zipfile import ZipFile, ZIP_DEFLATED


def escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&apos;")
    )


def parse_markdown(md_text: str) -> List[Tuple[str, str]]:
    lines = md_text.splitlines()
    paras: List[Tuple[str, str]] = []
    buffer: List[str] = []

    def flush_buffer():
        nonlocal buffer
        if buffer:
            text = "\n".join(buffer).strip()
            if text:
                paras.append((text, "Normal"))
        buffer = []

    for line in lines:
        if line.startswith("### "):
            flush_buffer()
            paras.append((line[4:].strip(), "Heading3"))
        elif line.startswith("## "):
            flush_buffer()
            paras.append((line[3:].strip(), "Heading2"))
        elif line.startswith("# "):
            flush_buffer()
            paras.append((line[2:].strip(), "Heading1"))
        elif line.strip() == "":
            flush_buffer()
        else:
            buffer.append(line)
    flush_buffer()
    return paras


def build_document_xml(paragraphs: List[Tuple[str, str]]) -> str:
    parts = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>",
        '<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:w10="urn:schemas-microsoft-com:office:word" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
        'xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" '
        'xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" mc:Ignorable="w14 wp14">',
        "<w:body>",
    ]
    for text, style in paragraphs:
        text = escape_xml(text)
        if style != "Normal":
            parts.append(
                f"<w:p><w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>"
            )
        else:
            parts.append(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>")
    parts.append("<w:sectPr></w:sectPr>")
    parts.append("</w:body></w:document>")
    return "".join(parts)


def build_styles_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:style w:type=\"paragraph\" w:default=\"1\" w:styleId=\"Normal\">"
        "<w:name w:val=\"Normal\"/></w:style>"
        "<w:style w:type=\"paragraph\" w:styleId=\"Heading1\"><w:name w:val=\"heading 1\"/></w:style>"
        "<w:style w:type=\"paragraph\" w:styleId=\"Heading2\"><w:name w:val=\"heading 2\"/></w:style>"
        "<w:style w:type=\"paragraph\" w:styleId=\"Heading3\"><w:name w:val=\"heading 3\"/></w:style>"
        "</w:styles>"
    )


def build_content_types_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )


def build_root_rels() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def build_document_rels() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )


def build_core_props() -> str:
    now = datetime.now(timezone.utc).isoformat()
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>Status</dc:title><dc:subject>Milestone</dc:subject><dc:creator>aialib</dc:creator>"
        f"<cp:lastModifiedBy>aialib</cp:lastModifiedBy><dcterms:created xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:created>"
        f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:modified></cp:coreProperties>"
    )


def build_app_props() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>aialib</Application></Properties>"
    )


def write_docx(paragraphs: List[Tuple[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(out_path, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", build_content_types_xml())
        z.writestr("_rels/.rels", build_root_rels())
        z.writestr("docProps/core.xml", build_core_props())
        z.writestr("docProps/app.xml", build_app_props())
        z.writestr("word/_rels/document.xml.rels", build_document_rels())
        z.writestr("word/styles.xml", build_styles_xml())
        z.writestr("word/document.xml", build_document_xml(paragraphs))


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--in", dest="input_path", required=True, type=Path)
    p.add_argument("--out", dest="output_path", required=True, type=Path)
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    text = args.input_path.read_text(encoding="utf-8")
    paragraphs = parse_markdown(text)
    write_docx(paragraphs, args.output_path)


if __name__ == "__main__":
    main()

