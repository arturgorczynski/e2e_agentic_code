"""Build the Polish configuration handbook from its editable Markdown source."""

import html
import re
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, PageBreak, Preformatted, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent
FONT = Path("C:/Windows/Fonts")
for name, filename in (("Guide", "arial.ttf"), ("GuideBold", "arialbd.ttf"), ("GuideItalic", "ariali.ttf"), ("GuideMono", "consola.ttf")):
    pdfmetrics.registerFont(TTFont(name, str(FONT / filename)))
pdfmetrics.registerFontFamily("Guide", normal="Guide", bold="GuideBold", italic="GuideItalic", boldItalic="GuideBold")
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle("BodyGuide", fontName="Guide", fontSize=10, leading=15, spaceAfter=9, textColor=colors.HexColor("#203042")))
STYLES.add(ParagraphStyle("Chapter", fontName="GuideBold", fontSize=23, leading=28, spaceAfter=19, textColor=colors.HexColor("#12314b"), keepWithNext=True))
STYLES.add(ParagraphStyle("Section", fontName="GuideBold", fontSize=13, leading=18, spaceBefore=12, spaceAfter=7, textColor=colors.HexColor("#087f86"), keepWithNext=True))
STYLES.add(ParagraphStyle("CodeGuide", fontName="GuideMono", fontSize=8, leading=11, spaceBefore=6, spaceAfter=12, backColor=colors.HexColor("#edf2f6"), borderPadding=8))
STYLES.add(ParagraphStyle("Cell", parent=STYLES["BodyGuide"], fontSize=8.5, leading=12, spaceAfter=0))
STYLES.add(ParagraphStyle("SmallGuide", parent=STYLES["BodyGuide"], fontSize=8, leading=11))


def markup(text):
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<link href="\2" color="#087f86">\1</link>', text)
    text = re.sub(r"`([^`]+)`", r'<font name="GuideMono" size="9">\1</font>', text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)


class Guide(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "Chapter":
            title = flowable.getPlainText()
            key = "chapter-" + str(self.seq.nextf("chapter"))
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, 0, False)
            self.notify("TOCEntry", (0, title, self.page, key))


def footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#d6e1e7"))
    canvas.line(45, 43, width - 45, 43)
    canvas.setFont("Guide", 8)
    canvas.setFillColor(colors.HexColor("#527083"))
    canvas.drawString(45, 29, "CODEX + CLAUDE CODE  /  lokalna konfiguracja  /  07.11.2026")
    canvas.drawRightString(width - 45, 29, str(doc.page))
    canvas.restoreState()


def parse(text):
    flow = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if line.startswith("# "):
            flow.extend([PageBreak(), Paragraph(markup(line[2:]), STYLES["Chapter"])])
        elif line.startswith("## "):
            flow.append(Paragraph(markup(line[3:]), STYLES["Section"]))
        elif line.startswith("```"):
            code = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.extend(textwrap.wrap(lines[i], 91, replace_whitespace=False, drop_whitespace=False) or [""])
                i += 1
            i += 1
            flow.append(Preformatted("\n".join(code), STYLES["CodeGuide"]))
        elif line.startswith("| "):
            rows = [line]
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            data = [[Paragraph(markup(c.strip()), STYLES["Cell"]) for c in row.strip("|").split("|")]
                    for row in rows if not re.fullmatch(r"[| :\-]+", row)]
            cols = len(data[0])
            widths = [155, 350] if cols == 2 else [505 / cols] * cols
            table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcecf0")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#d6e1e7"))]))
            flow.extend([table, Spacer(1, 10)])
        else:
            paragraph = [line]
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "```", "| ", "- ")):
                paragraph.append(lines[i].strip())
                i += 1
            text = " ".join(paragraph)
            if text.startswith("- "):
                text = "• " + text[2:]
            flow.append(Paragraph(markup(text), STYLES["BodyGuide"]))
    return flow


output = ROOT / "codex-claude-local-configuration-guide-pl.pdf"
doc = Guide(str(output), pagesize=A4, leftMargin=45, rightMargin=45, topMargin=48, bottomMargin=60,
            title="Codex i Claude Code - lokalna konfiguracja od podstaw", author="Agentic AI")
doc.addPageTemplates(PageTemplate(id="guide", frames=[Frame(45, 60, 505, A4[1] - 108, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=footer))
story = [Spacer(1, 75), Paragraph("Codex i Claude Code", STYLES["Chapter"]),
         Paragraph("Lokalna konfiguracja od podstaw", ParagraphStyle("Cover", parent=STYLES["Chapter"], fontSize=30, leading=37)),
         Spacer(1, 20), Paragraph("Instrukcje. Skills. Subagenci. Hooks. MCP. Uprawnienia.", STYLES["Section"]),
         Paragraph("Praktyczny podręcznik na podstawie branchów agents/codex i agents/claude w repozytorium Agentic AI. Z przykładami pól, przepływem zgody i sposobem sprawdzania działania.", STYLES["BodyGuide"]),
         Spacer(1, 30), Paragraph("Stan dokumentacji: 7 listopada 2026. Konfiguracja jest wersjonowana; katalogi producentów pozostają źródłem informacji o nowych polach. Poradnik odróżnia konfigurację zapisaną od aktywnej oraz testy lokalne od testów interfejsu hosta.", STYLES["BodyGuide"]), PageBreak(), Paragraph("Spis treści", STYLES["Chapter"])]
toc = TableOfContents()
toc.levelStyles = [ParagraphStyle("Contents", fontName="Guide", fontSize=9.5, leading=13, spaceBefore=0)]
story.append(toc)
story.extend(parse((ROOT / "guide-pl.md").read_text(encoding="utf-8")))
for host in ("codex", "claude"):
    checkout = ROOT.parents[2] / f"agentic_ai-{host}"
    files = ([".codex/config.toml", ".codex/hooks.json"] if host == "codex" else [".claude/settings.json", ".mcp.json"])
    files += [str(p.relative_to(checkout)).replace("\\", "/") for p in sorted((checkout / f".{host}/agents").glob("*")) if p.is_file()]
    skills = ".agents" if host == "codex" else ".claude"
    files += [str(p.relative_to(checkout)).replace("\\", "/") for p in sorted((checkout / skills / "skills").glob("*/SKILL.md"))]
    story.extend([PageBreak(), Paragraph(f"Aneks: pliki {host}", STYLES["Chapter"]),
                  Paragraph("Pełne definicje z przygotowanego checkoutu. Długie wiersze są zawijane wyłącznie na potrzeby wydruku; gotowy plik kopiuj z repo. To migawka konfiguracji, nie zapis osobistych sekretów ani uprawnień użytkownika.", STYLES["BodyGuide"])])
    for path in files:
        story.append(Paragraph(markup(path), STYLES["Section"]))
        code = []
        for line in (checkout / path).read_text(encoding="utf-8").splitlines():
            code.extend(textwrap.wrap(line, 91, replace_whitespace=False, drop_whitespace=False) or [""])
        # Small chunks allow long definitions to flow across pages without clipping.
        for start in range(0, len(code), 30):
            story.append(Preformatted("\n".join(code[start:start + 30]), STYLES["CodeGuide"]))
doc.multiBuild(story)
print(output)
