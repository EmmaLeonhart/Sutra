"""
Generate PDF of the FOL Discovery paper with embedded figures.

Uses fpdf2 to convert paper.md to a styled PDF with figures inserted
at appropriate locations.

Output: papers/fol-discovery/paper.pdf
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

# Map figure references to files and where to insert them
FIGURE_INSERTIONS = {
    "### 4.2 Prediction Accuracy": [
        ("fig1_alignment_vs_mrr.png", "Figure 1: Displacement consistency (alignment) vs prediction accuracy (MRR). "
         "Each point is a discovered operation. Color indicates alignment strength. "
         "Point size indicates number of triples. r = 0.861, 95% CI [0.773, 0.926]."),
    ],
    "### 4.1 Operation Discovery": [
        ("fig2_operation_distribution.png", "Figure 2: Distribution of predicate consistency scores. "
         "Left: histogram of alignment values. Right: category breakdown "
         "(32 strong, 54 moderate, 109 weak out of 159 analyzed)."),
    ],
    "### 5.3 Three Regimes": [
        ("fig4_three_zones.png", "Figure 3: The three regimes of embedding space with empirical evidence. "
         "Undersymbolic: 147,687 collisions from [UNK] token collapse. "
         "Isosymbolic: 86 discovered operations. Oversymbolic: saturated resolution."),
        ("fig3_collision_breakdown.png", "Figure 4: Collision type breakdown. 90% of 164,084 cross-entity "
         "collisions are genuine semantic (different text, near-identical embedding)."),
    ],
    "### 5.5 Limitations": [
        ("fig6_ablation.png", "Figure 5: Ablation study. Discovery count and quality metrics "
         "vs minimum triple threshold. Results stable across thresholds 5-20."),
        ("fig7_bootstrap_distribution.png", "Figure 6: Bootstrap distribution of alignment-MRR correlation "
         "(10,000 resamples). 95% CI [0.773, 0.926], entirely above zero."),
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


class PaperPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 5, 'Leonhart (2026) - Discovering FOL in Arbitrary Embedding Spaces', align='C')
            self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def add_title(self, text):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 8, text, align='C')
        self.ln(3)

    def add_author(self, text):
        self.set_font('Helvetica', '', 12)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, text, align='C', new_x="LMARGIN", new_y="NEXT")
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

        # Check if we need a new page for the figure
        if self.get_y() > 180:
            self.add_page()

        # Add image centered, width = page width - margins
        img_w = self.w - 30
        self.image(str(img_path), x=15, w=img_w)
        self.ln(3)

        # Caption
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 3.5, caption)
        self.ln(4)


def strip_markdown(text):
    """Strip markdown formatting for plain text rendering."""
    # Remove bold/italic markers
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Remove links
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    # Remove inline code
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Remove math (just show raw)
    text = re.sub(r'\$\$(.+?)\$\$', r'[\1]', text, flags=re.DOTALL)
    text = re.sub(r'\$(.+?)\$', r'\1', text)
    # Replace Unicode characters with ASCII equivalents for PDF compatibility
    text = text.replace('\u2014', '--')   # em dash
    text = text.replace('\u2013', '-')    # en dash
    text = text.replace('\u2018', "'")    # left single quote
    text = text.replace('\u2019', "'")    # right single quote
    text = text.replace('\u201c', '"')    # left double quote
    text = text.replace('\u201d', '"')    # right double quote
    text = text.replace('\u2265', '>=')   # >=
    text = text.replace('\u2264', '<=')   # <=
    text = text.replace('\u2248', '~=')   # approx
    text = text.replace('\u2192', '->')   # right arrow
    text = text.replace('\u2190', '<-')   # left arrow
    text = text.replace('\u00d7', 'x')    # multiplication
    text = text.replace('\u2022', '*')    # bullet
    text = text.replace('\u00e9', 'e')    # e-acute
    text = text.replace('\u00f6', 'o')    # o-umlaut
    text = text.replace('\u00fc', 'u')    # u-umlaut
    text = text.replace('\u00e4', 'a')    # a-umlaut
    text = text.replace('\u00c9', 'E')    # E-acute
    text = text.replace('\u014d', 'o')    # o-macron
    text = text.replace('\u0101', 'a')    # a-macron
    text = text.replace('\u012b', 'i')    # i-macron
    text = text.replace('\u1e6d', 't')    # t-underdot
    text = text.replace('\u1e24', 'H')    # H-underdot
    # Catch remaining non-latin-1 chars
    text = text.encode('latin-1', errors='replace').decode('latin-1')
    return text.strip()


def main():
    print("Generating PDF...")

    with open(str(PAPER_MD), 'r', encoding='utf-8') as f:
        lines = f.readlines()

    pdf = PaperPDF()
    pdf.add_page()

    in_table = False
    current_section = ""

    for line in lines:
        line = line.rstrip('\n')

        # Title (# heading)
        if line.startswith('# ') and not line.startswith('## '):
            pdf.add_title(line[2:])
            continue

        # Author
        if line.startswith('**Emma Leonhart**') or line.startswith('**Immanuelle'):
            pdf.add_author('Emma Leonhart')
            continue

        # Section headings
        if line.startswith('### '):
            current_section = line
            # Check if figures should be inserted BEFORE this section
            for trigger, figs in FIGURE_INSERTIONS.items():
                if trigger in line:
                    for fig_name, caption in figs:
                        fig_path = FIG_DIR / fig_name
                        pdf.add_figure(fig_path, caption)
            pdf.add_heading(line[4:], level=3)
            continue

        if line.startswith('## '):
            current_section = line
            pdf.add_heading(line[3:], level=2)
            continue

        # Table lines
        if '|' in line and line.strip().startswith('|'):
            if '---' in line:
                continue  # Skip separator
            if not in_table:
                in_table = True
                pdf.ln(2)
            pdf.add_table_line(line)
            continue
        else:
            if in_table:
                in_table = False
                pdf.ln(2)

        # Empty lines
        if not line.strip():
            continue

        # List items
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            text = strip_markdown(line.strip()[2:])
            pdf.add_paragraph(f"  \u2022 {text}")
            continue

        if re.match(r'^\d+\. ', line.strip()):
            text = strip_markdown(line.strip())
            pdf.add_paragraph(f"  {text}")
            continue

        # Regular paragraph
        text = strip_markdown(line)
        if text:
            pdf.add_paragraph(text)

    pdf.output(str(OUTPUT_PDF))
    print(f"PDF saved to: {OUTPUT_PDF}")
    print(f"Pages: {pdf.page_no()}")


if __name__ == "__main__":
    main()
