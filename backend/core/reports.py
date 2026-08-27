"""Geração de relatórios em Excel/PDF a partir de listas de dicts já
filtradas pelo controller. openpyxl e reportlab são puro-Python — sem
dependência de binário externo (wkhtmltopdf) ou libs nativas pesadas
(Cairo/Pango via weasyprint), importante na VM de produção com pouca RAM.
"""
import io

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet


def gerar_excel(titulo: str, colunas: list, linhas: list) -> io.BytesIO:
    """colunas: [(chave, rótulo), ...]. linhas: lista de dicts."""
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]  # limite do Excel pro nome da aba

    for col_idx, (_, rotulo) in enumerate(colunas, start=1):
        cell = ws.cell(row=1, column=col_idx, value=rotulo)
        cell.font = Font(bold=True)

    for row_idx, linha in enumerate(linhas, start=2):
        for col_idx, (chave, _) in enumerate(colunas, start=1):
            ws.cell(row=row_idx, column=col_idx, value=linha.get(chave, ''))

    for col_idx, (chave, rotulo) in enumerate(colunas, start=1):
        largura = max(len(rotulo), *(len(str(linha.get(chave, ''))) for linha in linhas)) if linhas else len(rotulo)
        ws.column_dimensions[chr(64 + col_idx) if col_idx <= 26 else 'A'].width = min(largura + 2, 50)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def gerar_pdf(titulo: str, colunas: list, linhas: list) -> io.BytesIO:
    """colunas: [(chave, rótulo), ...]. linhas: lista de dicts."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            leftMargin=1.5 * cm, rightMargin=1.5 * cm)
    styles = getSampleStyleSheet()

    dados = [[rotulo for _, rotulo in colunas]]
    for linha in linhas:
        dados.append([str(linha.get(chave, '')) for chave, _ in colunas])

    tabela = Table(dados, repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    doc.build([Paragraph(titulo, styles['Title']), tabela])
    buffer.seek(0)
    return buffer
