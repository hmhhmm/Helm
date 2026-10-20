#!/usr/bin/env python3
"""Small Markdown to PDF exporter (headings, paragraphs, bullets, tables, code, one image) built on reportlab.
Usage: python scripts/md_to_pdf.py docs/TECHNICAL.md docs/TECHNICAL.pdf"""
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, ListFlowable, ListItem, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
ss = getSampleStyleSheet()
body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.2, leading=13)
cell = ParagraphStyle("c", parent=body, fontSize=7.8, leading=10)
head = {1: ParagraphStyle("h1", parent=ss["Title"], fontSize=20, alignment=0), 2: ParagraphStyle("h2", parent=ss["Heading2"], fontSize=13, spaceBefore=10), 3: ParagraphStyle("h3", parent=ss["Heading3"], fontSize=10.5, spaceBefore=6)}
code = ParagraphStyle("code", fontName="Courier", fontSize=7.5, leading=9.5, backColor=colors.HexColor("#F3F4F6"), borderPadding=4)


def inline(t: str) -> str:
    t = escape(t)
    t = re.sub(r"`([^`]+)`", r"<font face='Courier'>\1</font>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)
    return t


lines = src.read_text().splitlines()
flow, i = [], 0
while i < len(lines):
    ln = lines[i]
    if ln.startswith("```"):
        j = i + 1
        buf = []
        while j < len(lines) and not lines[j].startswith("```"):
            buf.append(lines[j]); j += 1
        flow += [Preformatted("\n".join(buf), code), Spacer(1, 4)]
        i = j + 1
    elif ln.startswith("!["):
        m = re.match(r"!\[[^\]]*\]\(([^)]+)\)", ln)
        img = (src.parent / m.group(1)).resolve()
        if img.exists():
            flow += [Image(str(img), width=170 * mm, height=170 * mm * 750 / 1586), Spacer(1, 6)]
        i += 1
    elif ln.startswith("#"):
        n = len(ln) - len(ln.lstrip("#"))
        flow.append(Paragraph(inline(ln[n:].strip()), head[min(n, 3)]))
        i += 1
    elif ln.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            if not re.match(r"^\|[\s:|-]+\|$", lines[i]):
                rows.append([Paragraph(inline(c.strip()), cell) for c in lines[i].strip().strip("|").split("|")])
            i += 1
        n = max(len(r) for r in rows)
        t = Table([r + [""] * (n - len(r)) for r in rows], colWidths=[(174 * mm) / n] * n, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow += [t, Spacer(1, 6)]
    elif re.match(r"^\s*[-*] ", ln):
        items = []
        while i < len(lines) and re.match(r"^\s*[-*] ", lines[i]):
            items.append(ListItem(Paragraph(inline(re.sub(r"^\s*[-*] ", "", lines[i])), body)))
            i += 1
        flow.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
    elif ln.strip():
        buf = [ln]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||```|!\[|\s*[-*] )", lines[i]):
            buf.append(lines[i]); i += 1
        flow += [Paragraph(inline(" ".join(buf)), body), Spacer(1, 4)]
    else:
        i += 1
SimpleDocTemplate(str(dst), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=src.stem).build(flow)
print("wrote", dst)
