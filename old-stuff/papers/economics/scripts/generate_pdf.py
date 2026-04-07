"""
Generate PDF of the Economics paper with embedded figures.

Output: papers/economics/paper.pdf
"""

import io
import sys
import re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from fpdf import FPDF

PAPER_DIR = Path(__file__).resolve().parent.parent
PAPER_MD = PAPER_DIR / "paper.md"
FIG_DIR = PAPER_DIR / "figures"
OUTPUT_PDF = PAPER_DIR / "paper.pdf"

FIGURE_INSERTIONS = {
    "## 5. Structural Comparison": [
        ("fig1_structural_heatmap.png", "Figure 1: Structural bubble feature comparison. "
         "X = Present, ~ = Partial, - = Absent. Historical bubbles average 5.62/6.0. "
         "AI investment scores 0.5/6.0. Scores computed from retrieved data using explicit thresholds."),
        ("fig2_market_metrics.png", "Figure 2: Market performance comparison. "
         "Historical bubbles show 57-80% peak-to-trough declines. "
         "AI infrastructure companies show +38.5% average 2-year returns."),
    ],
}


def sanitize(text):
    """Replace Unicode characters with Latin-1 safe equivalents."""
    text = text.replace('\u2014', '--')
    text = text.replace('\u2013', '-')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2265', '>=').replace('\u2264', '<=')
    text = text.replace('\u2248', '~=')
    text = text.replace('\u2192', '->').replace('\u2190', '<-')
    text = text.replace('\u00d7', 'x')
    text = text.replace('\u2022', '*')
    return text.encode('latin-1', errors='replace').decode('latin-1')


def strip_markdown(text):
    """Strip markdown formatting for plain text rendering."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\$\$(.+?)\$\$', r'[\1]', text, flags=re.DOTALL)
    text = re.sub(r'\$(.+?)\$', r'\1', text)
    return sanitize(text.strip())


class PaperPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 5, 'Leonhart (2026) - The AI Investment Bubble', align='C')
            self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def add_title(self, text):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 8, sanitize(text), align='C')
        self.ln(3)

    def add_author(self, text):
        self.set_font('Helvetica', '', 12)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, sanitize(text), align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def add_heading(self, text, level=2):
        sizes = {1: 14, 2: 12, 3: 11}
        self.set_font('Helvetica', 'B', sizes.get(level, 11))
        self.set_text_color(0, 0, 0)
        self.ln(4)
        self.multi_cell(0, 6, sanitize(text))
        self.ln(2)

    def add_paragraph(self, text):
        self.set_font('Helvetica', '', 9.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 4.5, sanitize(text))
        self.ln(2)

    def add_table_line(self, text):
        self.set_font('Courier', '', 7.5)
        self.set_text_color(30, 30, 30)
        self.cell(0, 3.5, sanitize(text[:120]), new_x="LMARGIN", new_y="NEXT")

    def add_figure(self, img_path, caption):
        if not img_path.exists():
            self.add_paragraph(f"[Figure not found: {img_path.name}]")
            return
        if self.get_y() > 180:
            self.add_page()
        img_w = self.w - 30
        self.image(str(img_path), x=15, w=img_w)
        self.ln(3)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 3.5, sanitize(caption))
        self.ln(4)


def main():
    print("Generating PDF...")

    with open(str(PAPER_MD), 'r', encoding='utf-8') as f:
        lines = f.readlines()

    pdf = PaperPDF()
    pdf.add_page()

    in_table = False

    for line in lines:
        line = line.rstrip('\n')

        if line.startswith('# ') and not line.startswith('## '):
            pdf.add_title(line[2:])
            continue

        if line.startswith('**Emma Leonhart**'):
            pdf.add_author('Emma Leonhart')
            continue

        if line.startswith('### '):
            pdf.add_heading(line[4:], level=3)
            continue

        if line.startswith('## '):
            # Check for figure insertions
            for trigger, figs in FIGURE_INSERTIONS.items():
                if trigger in line:
                    for fig_name, caption in figs:
                        fig_path = FIG_DIR / fig_name
                        pdf.add_figure(fig_path, caption)
            pdf.add_heading(line[3:], level=2)
            continue

        if '|' in line and line.strip().startswith('|'):
            if '---' in line:
                continue
            if not in_table:
                in_table = True
                pdf.ln(2)
            pdf.add_table_line(line)
            continue
        else:
            if in_table:
                in_table = False
                pdf.ln(2)

        if not line.strip():
            continue

        if line.strip().startswith('- ') or line.strip().startswith('* '):
            text = strip_markdown(line.strip()[2:])
            pdf.add_paragraph(f"  * {text}")
            continue

        if re.match(r'^\d+\. ', line.strip()):
            text = strip_markdown(line.strip())
            pdf.add_paragraph(f"  {text}")
            continue

        text = strip_markdown(line)
        if text:
            pdf.add_paragraph(text)

    pdf.output(str(OUTPUT_PDF))
    print(f"PDF saved to: {OUTPUT_PDF}")
    print(f"Pages: {pdf.page_no()}")


if __name__ == "__main__":
    main()
