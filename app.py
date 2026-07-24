import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import traceback
from datetime import datetime
import os
import base64
import sys

try:
    from fpdf import FPDF
    FPDF2_AVAILABLE = True
except Exception:
    FPDF = None
    FPDF2_AVAILABLE = False

from database_setup import Weld, Base
from pdf_parser import parse_nde_report

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")

DATABASE_URL = "sqlite:///weld_log.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Admin password management (persisted to file) ---
ADMIN_PASSWORD_FILE = os.path.join(BASE_DIR, "admin_password.txt")
DEFAULT_ADMIN_PASSWORD = "admin"

def load_admin_password():
    try:
        if os.path.exists(ADMIN_PASSWORD_FILE):
            with open(ADMIN_PASSWORD_FILE, "r", encoding="utf-8") as f:
                pwd = f.read().strip()
                if pwd:
                    return pwd
    except Exception:
        pass
    return DEFAULT_ADMIN_PASSWORD

def save_admin_password(new_password: str):
    with open(ADMIN_PASSWORD_FILE, "w", encoding="utf-8") as f:
        f.write(new_password.strip())

ADMIN_PASSWORD = load_admin_password()

st.set_page_config(layout="wide", page_title="Pipeline Weld Log Dashboard")
if 'logo_saved' not in st.session_state: st.session_state.logo_saved = False

# --- Modern design system (light + dark) ---
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<style>
    /* ========== LIGHT THEME — Cloud-hardened ========== */
    :root {
        --bg: #F1F5F9;
        --surface: #FFFFFF;
        --surface-2: #F8FAFC;
        --border: #E2E8F0;
        --text: #0F172A;
        --text-muted: #64748B;
        --accent: #2563EB;
        --accent-hover: #1D4ED8;
        --success: #059669;
        --warning: #D97706;
        --error: #DC2626;
        --card-shadow: 0 1px 3px rgba(15, 23, 42, 0.06), 0 4px 14px rgba(15, 23, 42, 0.04);
        --radius: 14px;
    }

    /* Force light surfaces across Streamlit shell */
    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewBlockContainer"],
    .main,
    section.main {
        background-color: var(--bg) !important;
        color: var(--text) !important;
    }

    .stApp {
        background:
            radial-gradient(ellipse 90% 55% at 8% -15%, rgba(37, 99, 235, 0.07), transparent),
            radial-gradient(ellipse 70% 45% at 95% 0%, rgba(14, 165, 233, 0.05), transparent),
            var(--bg) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--text) !important;
    }

    /* Header / toolbar */
    [data-testid="stHeader"],
    header[data-testid="stHeader"] {
        background: rgba(241, 245, 249, 0.85) !important;
        backdrop-filter: blur(8px);
    }

    /* Main block padding */
    .block-container {
        padding-top: 1.25rem !important;
        color: var(--text) !important;
    }

    h1, h2, h3, h4, h5, h6,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Space Grotesk', 'Inter', sans-serif !important;
        font-weight: 600 !important;
        color: #0F172A !important;
        letter-spacing: -0.025em;
    }

    p, span, label, .stMarkdown, .stText {
        color: #0F172A !important;
    }

    /* Metrics */
    [data-testid="stMetric"],
    .stMetric {
        background: transparent !important;
    }
    .stMetric > label,
    [data-testid="stMetricLabel"] {
        color: var(--accent) !important;
        font-weight: 600 !important;
        font-size: 0.78rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    .stMetric [data-testid="stMetricValue"] {
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.75rem !important;
        color: #0F172A !important;
        letter-spacing: -0.03em;
    }
    [data-testid="stMetricDelta"] {
        color: var(--text-muted) !important;
    }

    /* Alerts */
    div[data-testid="stAlert"] {
        border-radius: var(--radius) !important;
    }
    .stWarning, div[data-baseweb="notification"] {
        border-radius: var(--radius) !important;
    }

    /* Custom cards */
    .metric-container, .section-card {
        background: #FFFFFF !important;
        padding: 1.25rem 1.5rem !important;
        border-radius: var(--radius) !important;
        border: 1px solid #E2E8F0 !important;
        box-shadow: var(--card-shadow) !important;
        margin-bottom: 1rem !important;
        color: #0F172A !important;
    }
    .metric-container {
        border-left: 4px solid #2563EB !important;
    }
    .section-card {
        border-top: 3px solid #2563EB !important;
    }
    .metric-container:hover, .section-card:hover {
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08) !important;
        border-color: rgba(37, 99, 235, 0.25) !important;
    }

    /* Dataframes / tables */
    .dataframe th {
        background: #F1F5F9 !important;
        color: #475569 !important;
        font-weight: 600 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        border-bottom: 2px solid #E2E8F0 !important;
    }
    .dataframe td {
        border-color: #F1F5F9 !important;
        color: #0F172A !important;
        font-size: 0.875rem !important;
    }
    .dataframe tr:hover td {
        background: #F8FAFC !important;
    }
    div[data-testid="stDataFrame"],
    div[data-testid="stDataFrame"] > div {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: var(--radius) !important;
        overflow: hidden;
    }

    /* Buttons — pure white label on blue for contrast */
    .stButton > button,
    .stDownloadButton > button,
    button[kind="primary"],
    button[data-testid="baseButton-primary"],
    button[data-testid="baseButton-secondary"] {
        background: linear-gradient(135deg, #1D4ED8, #2563EB) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 9px !important;
        font-weight: 700 !important;
        font-family: 'Inter', sans-serif !important;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.28) !important;
        text-shadow: none !important;
    }
    .stButton > button *,
    .stDownloadButton > button *,
    button[kind="primary"] *,
    button[data-testid="baseButton-primary"] *,
    button[data-testid="baseButton-secondary"] * {
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
    }
    .stButton > button:hover,
    .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #1E40AF, #1D4ED8) !important;
        color: #FFFFFF !important;
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4) !important;
    }
    .stButton > button:hover *,
    .stDownloadButton > button:hover * {
        color: #FFFFFF !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"],
    section[data-testid="stSidebar"],
    [data-testid="stSidebar"] > div {
        background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%) !important;
        border-right: 1px solid #E2E8F0 !important;
    }
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #0F172A !important;
    }
    /* Sidebar buttons must stay white-on-blue (override sidebar text color) */
    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] .stDownloadButton > button {
        background: linear-gradient(135deg, #1D4ED8, #2563EB) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    [data-testid="stSidebar"] .stButton > button *,
    [data-testid="stSidebar"] .stDownloadButton > button * {
        color: #FFFFFF !important;
    }

    /* Inputs */
    .stTextInput input, .stNumberInput input,
    [data-baseweb="input"] input,
    .stDateInput input,
    [data-baseweb="select"] > div {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 9px !important;
        color: #0F172A !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"],
    [data-testid="stFileUploader"] section {
        background: #F8FAFC !important;
        border: 1.5px dashed #CBD5E1 !important;
        border-radius: var(--radius) !important;
        color: #0F172A !important;
    }

    /* Radio / toggle */
    [data-testid="stRadio"] label,
    [data-testid="stCheckbox"] label {
        color: #0F172A !important;
    }

    /* Expander */
    [data-testid="stExpander"],
    .streamlit-expanderHeader {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        color: #0F172A !important;
    }

    /* Divider */
    hr, [data-testid="stHorizontalBlock"] hr {
        border-color: #E2E8F0 !important;
        opacity: 0.9;
    }

    /* Caption */
    .stCaption, [data-testid="stCaptionContainer"], small {
        color: #64748B !important;
    }

    /* Plotly chart container */
    [data-testid="stPlotlyChart"] {
        background: #FFFFFF !important;
        border-radius: var(--radius) !important;
    }

    /* App logo — prevent top/side clipping */
    .app-logo-wrap {
        display: flex !important;
        align-items: center !important;
        justify-content: flex-end !important;
        padding-top: 0.35rem !important;
        overflow: visible !important;
        min-height: 72px !important;
    }
    .app-logo-wrap img,
    [data-testid="stImage"] img,
    div[data-testid="stImage"] img {
        object-fit: contain !important;
        object-position: center center !important;
        max-height: 88px !important;
        width: auto !important;
        height: auto !important;
        overflow: visible !important;
    }
    div[data-testid="stImage"] {
        overflow: visible !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
</style>
""", unsafe_allow_html=True)

def image_to_base64(path):
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except FileNotFoundError:
        return None

def _pdf_safe(text):
    """Strip characters Helvetica/core fonts cannot encode (keep PDF generation robust)."""
    if text is None:
        return ''
    try:
        if pd.isna(text):
            return ''
    except Exception:
        pass
    s = str(text)
    for a, b in (
        ('\u2013', '-'), ('\u2014', '-'), ('\u2018', "'"), ('\u2019', "'"),
        ('\u201c', '"'), ('\u201d', '"'), ('\u2026', '...'), ('\u00a0', ' '),
        ('\u2022', '*'), ('\u00b7', '-'), ('\u2212', '-'),
    ):
        s = s.replace(a, b)
    return s.encode('latin-1', errors='replace').decode('latin-1')


def _logo_fit_size(max_h=12, max_w=40):
    """Return (w_mm, h_mm) that fits the logo inside max_w x max_h, preserving aspect ratio."""
    if not os.path.exists(LOGO_PATH):
        return 0, 0
    try:
        from PIL import Image
        with Image.open(LOGO_PATH) as im:
            px_w, px_h = im.size
        if px_w <= 0 or px_h <= 0:
            return 0, 0
        # Start from max height, scale width; if too wide, scale down to max_w
        h = float(max_h)
        w = h * (px_w / px_h)
        if w > max_w:
            w = float(max_w)
            h = w * (px_h / px_w)
        return w, h
    except Exception:
        # Fallback without PIL: assume roughly square-ish logo
        return min(max_w, max_h * 2.2), float(max_h)


def _draw_pdf_logo(pdf, x, y, max_h=12, max_w=40):
    """Place company logo scaled to fit. Returns rendered width in mm (0 if none)."""
    w, h = _logo_fit_size(max_h=max_h, max_w=max_w)
    if w <= 0 or h <= 0:
        return 0
    try:
        pdf.image(LOGO_PATH, x=x, y=y, w=w, h=h)
        return w
    except Exception:
        return 0


def generate_pdf(dataframe):
    """Repair backlog PDF - landscape, single page when possible (fpdf2)."""
    if not FPDF2_AVAILABLE:
        raise RuntimeError("PDF engine (fpdf2) is not available in this environment.")

    df_copy = dataframe.copy()
    if 'Diameter' not in df_copy.columns and 'diameter' in df_copy.columns:
        df_copy['Diameter'] = df_copy['diameter']
    if 'Diameter' in df_copy.columns:
        df_copy['Diameter'] = df_copy['Diameter'].apply(
            lambda x: f"{float(x):.3f}" if pd.notnull(x) and x != '' else ''
        )

    preferred = ['Date', 'Report ID', 'Diameter', 'WT', 'Station', 'Weld ID',
                 'Defect Type', 'Start', 'Length', 'Depth', 'Height']
    cols = [c for c in preferred if c in df_copy.columns]
    if not cols:
        cols = [c for c in df_copy.columns if c not in ('_sa_instance_state',)]

    # Landscape letter: 279.4 x 215.9 mm
    pdf = FPDF(orientation='L', unit='mm', format='Letter')
    pdf.set_margins(8, 8, 8)
    pdf.set_auto_page_break(auto=False)  # stay on one page unless many rows
    pdf.add_page()
    page_w = 279.4
    usable = page_w - 16  # left+right margins

    # Modern letterhead header — soft band + accent rule
    header_h = 18
    pdf.set_fill_color(248, 250, 252)  # soft slate
    pdf.rect(0, 0, page_w, header_h, 'F')
    # Accent line under header
    pdf.set_fill_color(37, 99, 235)
    pdf.rect(0, header_h - 1.2, page_w, 1.2, 'F')

    pad = 4
    logo_w, logo_h = _logo_fit_size(max_h=header_h - 6, max_w=50)
    cursor_x = 8
    if logo_w > 0:
        logo_y = (header_h - 1.2 - logo_h) / 2
        _draw_pdf_logo(pdf, x=cursor_x, y=logo_y, max_h=header_h - 6, max_w=50)
        cursor_x += logo_w + 5

    pdf.set_text_color(15, 23, 42)
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_xy(cursor_x, 4)
    pdf.cell(140, 6, 'Weld Repair Backlog')
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.set_xy(cursor_x, 10.5)
    pdf.cell(140, 4, 'Pipeline Weld Log & NDE Analytics')

    pdf.set_text_color(100, 116, 139)
    pdf.set_font('Helvetica', '', 8)
    pdf.set_xy(page_w - 78, 6.5)
    pdf.cell(70, 4, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", align='R')

    y = header_h + 5
    pdf.set_text_color(15, 23, 42)

    if df_copy.empty or not cols:
        pdf.set_xy(8, y)
        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, 'No outstanding repairs.')
        pdf.set_y(205)
        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(0, 4, 'Confidential - Project use only  |  Pipeline Weld Log & NDE Analytics', align='C')
        return bytes(pdf.output())

    # Column widths
    weights = []
    for c in cols:
        if c in ('Weld ID', 'Defect Type', 'Report ID'):
            weights.append(1.35)
        elif c in ('Station', 'Date'):
            weights.append(1.15)
        else:
            weights.append(0.95)
    total_w = sum(weights)
    col_w = [usable * w / total_w for w in weights]

    # Fit as many rows as possible on one page (header ~16, footer ~8 => ~190mm)
    row_h = 5.2
    header_h = 6
    max_rows_one_page = int((200 - y - header_h) / row_h)

    def draw_table_header(yy):
        pdf.set_xy(8, yy)
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_fill_color(241, 245, 249)
        pdf.set_text_color(71, 85, 105)
        for i, c in enumerate(cols):
            pdf.cell(col_w[i], header_h, _pdf_safe(c)[:16], border=1, fill=True, align='C')
        return yy + header_h

    def draw_rows(start_idx, end_idx, yy):
        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(15, 23, 42)
        fill = False
        for idx in range(start_idx, end_idx):
            row = df_copy.iloc[idx]
            if fill:
                pdf.set_fill_color(248, 250, 252)
            else:
                pdf.set_fill_color(255, 255, 255)
            pdf.set_xy(8, yy)
            for i, c in enumerate(cols):
                val = row.get(c, '')
                text = _pdf_safe(val)
                max_chars = max(5, int(col_w[i] / 1.6))
                if len(text) > max_chars:
                    text = text[: max_chars - 1] + '...'
                align = 'R' if c in ('Diameter', 'Start', 'Length', 'Depth', 'Height', 'WT') else 'L'
                pdf.cell(col_w[i], row_h, text, border=1, fill=True, align=align)
            yy += row_h
            fill = not fill
        return yy

    n_rows = len(df_copy)
    # First page
    y = draw_table_header(y)
    first_end = min(n_rows, max_rows_one_page)
    y = draw_rows(0, first_end, y)

    # Extra pages only if necessary
    idx = first_end
    while idx < n_rows:
        pdf.add_page()
        # mini continued header — matches modern letterhead
        pdf.set_fill_color(248, 250, 252)
        pdf.rect(0, 0, page_w, 10, 'F')
        pdf.set_fill_color(37, 99, 235)
        pdf.rect(0, 8.8, page_w, 1.2, 'F')
        pdf.set_text_color(15, 23, 42)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_xy(8, 2.5)
        pdf.cell(0, 5, 'Weld Repair Backlog (continued)')
        y = 14
        y = draw_table_header(y)
        page_max = int((200 - y) / row_h)
        end = min(n_rows, idx + page_max)
        y = draw_rows(idx, end, y)
        idx = end

    # Footer on last page
    pdf.set_xy(8, 208)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(usable, 4, 'Confidential - Project use only  |  Pipeline Weld Log & NDE Analytics', align='C')

    return bytes(pdf.output())


def generate_summary_report_pdf(report_type, period_label, metrics, weld_type_summary, backlog_count, critical_count, aging_buckets, top_rejects=None, project_metrics=None):
    """One-page Daily/Weekly quality summary PDF (fpdf2) - tight, clean layout."""
    if not FPDF2_AVAILABLE:
        raise RuntimeError("PDF engine (fpdf2) is not available in this environment.")

    generated = datetime.now().strftime("%b %d, %Y %H:%M")

    # Portrait letter: 215.9 x 279.4 mm
    pdf = FPDF(orientation='P', unit='mm', format='Letter')
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    W = 215.9
    left = 10
    right = W - 10
    usable = right - left  # ~195.9

    # ===== Modern letterhead header — soft band + accent rule =====
    header_h = 20
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(0, 0, W, header_h, 'F')
    pdf.set_fill_color(37, 99, 235)
    pdf.rect(0, header_h - 1.2, W, 1.2, 'F')

    logo_w, logo_h = _logo_fit_size(max_h=header_h - 7, max_w=40)
    cursor_x = left
    if logo_w > 0:
        logo_y = (header_h - 1.2 - logo_h) / 2
        _draw_pdf_logo(pdf, x=cursor_x, y=logo_y, max_h=header_h - 7, max_w=40)
        cursor_x += logo_w + 4

    pdf.set_text_color(15, 23, 42)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_xy(cursor_x, 3.5)
    pdf.cell(95, 5, 'Project Weld Log & NDE Analytics')
    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(100, 116, 139)
    pdf.set_xy(cursor_x, 10)
    pdf.cell(95, 4, 'Construction Quality Summary - AQI Ltd.')

    # Right side meta — subtle badge + details
    badge_w = 42
    badge_x = W - 10 - badge_w
    pdf.set_fill_color(37, 99, 235)
    pdf.rect(badge_x, 3, badge_w, 5.5, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_xy(badge_x, 3.5)
    pdf.cell(badge_w, 4, _pdf_safe(report_type), align='C')
    pdf.set_text_color(71, 85, 105)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_xy(badge_x - 28, 10)
    pdf.cell(badge_w + 28, 3.5, _pdf_safe(period_label), align='R')
    pdf.set_text_color(148, 163, 184)
    pdf.set_xy(badge_x - 28, 13.5)
    pdf.cell(badge_w + 28, 3.5, f'Generated {generated}', align='R')

    y = header_h + 4

    # ===== KPIs: Period + Project =====
    def _draw_kpi_row(pdf, y, title, kpis, left, right, usable):
        pdf.set_text_color(37, 99, 235)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_xy(left, y)
        pdf.cell(usable, 4, title)
        y += 4.5
        pdf.set_draw_color(203, 213, 225)
        pdf.line(left, y, right, y)
        y += 2
        n_kpi = len(kpis)
        gap = 2
        box_w = (usable - gap * (n_kpi - 1)) / n_kpi
        box_h = 13
        for i, (label, value) in enumerate(kpis):
            x = left + i * (box_w + gap)
            pdf.set_fill_color(248, 250, 252)
            pdf.set_draw_color(226, 232, 240)
            pdf.rect(x, y, box_w, box_h, 'DF')
            pdf.set_xy(x, y + 1.2)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(box_w, 5, value, align='C')
            pdf.set_xy(x, y + 7.5)
            pdf.set_font('Helvetica', '', 5.5)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(box_w, 4, label.upper(), align='C')
        return y + box_h + 3.5

    period_kpis = [
        ("Welds Inspected", f"{metrics['total_welds']:,}"),
        ("Reject Rate", f"{metrics['reject_rate']:.2f}%"),
        ("Prod. Rejects", f"{metrics['rejects']:,}"),
        ("Cut-outs", f"{metrics['cutouts']:,}"),
        ("Open Backlog", f"{backlog_count:,}"),
        ("Critical", f"{critical_count:,}"),
    ]
    y = _draw_kpi_row(pdf, y, 'THIS PERIOD', period_kpis, left, right, usable)

    if project_metrics:
        project_kpis = [
            ("Total Welds", f"{project_metrics['total_welds']:,}"),
            ("Reject Rate", f"{project_metrics['reject_rate']:.2f}%"),
            ("Total Rejects", f"{project_metrics['rejects']:,}"),
            ("Total Cut-outs", f"{project_metrics['cutouts']:,}"),
        ]
        y = _draw_kpi_row(pdf, y, 'PROJECT TO DATE', project_kpis, left, right, usable)

    # ===== TWO COLUMNS =====
    mid_gap = 6
    col_w = (usable - mid_gap) / 2
    left_x = left
    right_x = left + col_w + mid_gap
    section_y = y

    # Left title
    pdf.set_text_color(37, 99, 235)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_xy(left_x, section_y)
    pdf.cell(col_w, 4, 'SUMMARY BY WELD TYPE')
    # Right title
    pdf.set_xy(right_x, section_y)
    pdf.cell(col_w, 4, 'OPEN REPAIR BACKLOG AGING')
    section_y += 4.5
    pdf.set_draw_color(203, 213, 225)
    pdf.line(left_x, section_y, left_x + col_w, section_y)
    pdf.line(right_x, section_y, right_x + col_w, section_y)
    section_y += 2.5
    body_top = section_y

    # --- Left: weld type table ---
    wt_w = [col_w * 0.32, col_w * 0.17, col_w * 0.17, col_w * 0.17, col_w * 0.17]
    pdf.set_xy(left_x, body_top)
    pdf.set_font('Helvetica', 'B', 6.5)
    pdf.set_fill_color(241, 245, 249)
    pdf.set_text_color(71, 85, 105)
    for name, w in zip(['Type', 'Insp', 'Acc', 'Rej', 'Rej%'], wt_w):
        pdf.cell(w, 5, name, border=1, fill=True, align='C')
    ly = body_top + 5

    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(15, 23, 42)
    if weld_type_summary is not None and len(weld_type_summary) > 0:
        for _, row in weld_type_summary.head(8).iterrows():
            pdf.set_xy(left_x, ly)
            pdf.cell(wt_w[0], 5, _pdf_safe(row.get('Weld Type', ''))[:12], border=1)
            pdf.cell(wt_w[1], 5, f"{int(row.get('Total Inspected', 0))}", border=1, align='R')
            pdf.cell(wt_w[2], 5, f"{int(row.get('Accepted', 0))}", border=1, align='R')
            pdf.cell(wt_w[3], 5, f"{int(row.get('Rejected', 0))}", border=1, align='R')
            pdf.cell(wt_w[4], 5, f"{float(row.get('Reject Rate (%)', 0)):.1f}%", border=1, align='R')
            ly += 5
    else:
        pdf.set_xy(left_x, ly)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(col_w, 5, 'No weld type data', border=1, align='C')
        ly += 5

    # --- Right: aging boxes ---
    aging_items = list(aging_buckets.items()) if aging_buckets else []
    n_age = max(len(aging_items), 1)
    age_gap = 2
    age_w = (col_w - age_gap * (n_age - 1)) / n_age if n_age else col_w
    age_h = 13
    for i, (label, count) in enumerate(aging_items):
        ax = right_x + i * (age_w + age_gap)
        pdf.set_fill_color(248, 250, 252)
        pdf.set_draw_color(226, 232, 240)
        pdf.rect(ax, body_top, age_w, age_h, 'DF')
        pdf.set_xy(ax, body_top + 1.5)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(age_w, 5, str(count), align='C')
        pdf.set_xy(ax, body_top + 7.5)
        pdf.set_font('Helvetica', '', 5)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(age_w, 4, _pdf_safe(label), align='C')

    # Backlog / critical counts under aging
    ry = body_top + age_h + 3
    pdf.set_xy(right_x, ry)
    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(28, 4, 'Open backlog:')
    pdf.set_font('Helvetica', 'B', 7.5)
    if backlog_count > 0:
        pdf.set_text_color(220, 38, 38)
    else:
        pdf.set_text_color(5, 150, 105)
    pdf.cell(12, 4, str(backlog_count))
    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(28, 4, 'Critical items:')
    pdf.set_font('Helvetica', 'B', 7.5)
    if critical_count > 0:
        pdf.set_text_color(220, 38, 38)
    else:
        pdf.set_text_color(5, 150, 105)
    pdf.cell(12, 4, str(critical_count))

    y = max(ly, ry + 6) + 4

    # ===== OPEN REJECTS =====
    pdf.set_text_color(37, 99, 235)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_xy(left, y)
    pdf.cell(usable, 4, 'OPEN REJECTS (OLDEST FIRST)')
    y += 4.5
    pdf.set_draw_color(203, 213, 225)
    pdf.line(left, y, right, y)
    y += 2

    rej_w = [usable * 0.24, usable * 0.26, usable * 0.34, usable * 0.16]
    pdf.set_xy(left, y)
    pdf.set_font('Helvetica', 'B', 6.5)
    pdf.set_fill_color(241, 245, 249)
    pdf.set_text_color(71, 85, 105)
    for name, w in zip(['Weld ID', 'Station', 'Defect', 'Days Open'], rej_w):
        pdf.cell(w, 5, name, border=1, fill=True, align='C')
    y += 5

    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(15, 23, 42)
    max_y = 265
    if top_rejects is not None and len(top_rejects) > 0:
        for _, r in top_rejects.head(12).iterrows():
            if y + 5 > max_y:
                break
            pdf.set_xy(left, y)
            pdf.cell(rej_w[0], 5, _pdf_safe(r.get('weld_id', ''))[:18], border=1)
            pdf.cell(rej_w[1], 5, _pdf_safe(r.get('stationing', '') or '')[:20], border=1)
            pdf.cell(rej_w[2], 5, _pdf_safe(r.get('defect_type', '') or '-')[:28], border=1)
            pdf.cell(rej_w[3], 5, _pdf_safe(r.get('days_open', '')), border=1, align='R')
            y += 5
    else:
        pdf.set_xy(left, y)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(usable, 5, 'No open rejects', border=1, align='C')

    # ===== FOOTER =====
    pdf.set_draw_color(203, 213, 225)
    pdf.line(left, 272, right, 272)
    pdf.set_xy(left, 273)
    pdf.set_font('Helvetica', '', 6.5)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(usable / 2, 4, 'Confidential - For project use only')
    pdf.cell(usable / 2, 4, 'Pipeline Construction Quality Report', align='R')

    return bytes(pdf.output())



title_col, logo_col = st.columns([3.2, 1.2], gap="medium")
with title_col:
    st.title("Project Weld Log & NDE Analytics")
    st.caption("Developed by AQI ltd.")
with logo_col:
    if os.path.exists(LOGO_PATH):
        # use_container_width keeps full logo visible (no top/side crop)
        st.markdown(
            '<div class="app-logo-wrap">',
            unsafe_allow_html=True,
        )
        st.image(LOGO_PATH, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

def get_db_session(): return SessionLocal()
def load_data_from_db():
    try:
        db = get_db_session()
        query = db.query(Weld).all()
        df = pd.DataFrame([w.__dict__ for w in query])
        if '_sa_instance_state' in df.columns: df = df.drop(columns=['_sa_instance_state'])
        return df
    finally: db.close()

st.sidebar.header("Controls")
dark_mode = st.sidebar.toggle("Dark Mode", value=False, key="dark_mode_toggle")

if dark_mode:
    st.markdown("""
    <style>
        /* ========== DARK THEME — Cloud-hardened ========== */
        :root {
            --bg: #070B14 !important;
            --surface: #0F1623 !important;
            --surface-2: #151E2E !important;
            --border: #1E2A3A !important;
            --text: #E8EEF7 !important;
            --text-muted: #8B9CB3 !important;
            --accent: #38BDF8 !important;
            --radius: 14px !important;
        }

        /* Force dark shell across Streamlit Cloud */
        html, body, .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewBlockContainer"],
        .main, section.main,
        .block-container {
            background-color: #070B14 !important;
            color: #E8EEF7 !important;
        }

        .stApp {
            background:
                radial-gradient(ellipse 80% 50% at 20% -10%, rgba(56, 189, 248, 0.08), transparent),
                radial-gradient(ellipse 60% 40% at 90% 10%, rgba(99, 102, 241, 0.06), transparent),
                #070B14 !important;
            color: #E8EEF7 !important;
        }

        /* Header / toolbar */
        [data-testid="stHeader"],
        header[data-testid="stHeader"] {
            background: rgba(7, 11, 20, 0.9) !important;
            backdrop-filter: blur(8px);
        }

        /* Typography */
        h1, h2, h3, h4, h5, h6,
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
            color: #F8FAFC !important;
            font-family: 'Space Grotesk', 'Inter', sans-serif !important;
        }
        .stMarkdown, .stText, p, label, span {
            color: #E8EEF7 !important;
        }
        .stCaption, [data-testid="stCaptionContainer"], small {
            color: #8B9CB3 !important;
        }

        /* Sidebar */
        [data-testid="stSidebar"],
        section[data-testid="stSidebar"],
        [data-testid="stSidebar"] > div {
            background: linear-gradient(180deg, #0B1220 0%, #0A101C 100%) !important;
            border-right: 1px solid #1E2A3A !important;
        }
        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #E8EEF7 !important;
        }

        /* Metrics */
        [data-testid="stMetric"], .stMetric {
            background: transparent !important;
        }
        .stMetric > label,
        [data-testid="stMetricLabel"] {
            color: #38BDF8 !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
        }
        .stMetric [data-testid="stMetricValue"] {
            color: #F8FAFC !important;
            font-family: 'Space Grotesk', sans-serif !important;
            font-weight: 700 !important;
        }
        [data-testid="stMetricDelta"] {
            color: #8B9CB3 !important;
        }

        /* Cards */
        .metric-container, .section-card {
            background: linear-gradient(145deg, #161E2E, #0F1623) !important;
            border: 1px solid rgba(56, 189, 248, 0.14) !important;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.45) !important;
            color: #E8EEF7 !important;
            border-radius: 14px !important;
            padding: 1.25rem 1.5rem !important;
            margin-bottom: 1rem !important;
        }
        .metric-container {
            border-left: 4px solid #38BDF8 !important;
        }
        .section-card {
            border-top: 3px solid #38BDF8 !important;
        }

        /* Dataframes */
        .dataframe th {
            background: #1A2436 !important;
            color: #94A3B8 !important;
            border-color: #1E2A3A !important;
        }
        .dataframe td {
            background: rgba(15, 22, 35, 0.85) !important;
            color: #E8EEF7 !important;
            border-color: #1E2A3A !important;
        }
        .dataframe tr:hover td {
            background: rgba(56, 189, 248, 0.08) !important;
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stDataFrame"] > div,
        [data-testid="stTable"] {
            background: #0F1623 !important;
            border: 1px solid #1E2A3A !important;
            border-radius: 14px !important;
        }

        /* Buttons */
        .stButton > button,
        .stDownloadButton > button,
        button[kind="primary"] {
            background: linear-gradient(135deg, #0EA5E9, #38BDF8) !important;
            color: #0B0F19 !important;
            border: none !important;
            border-radius: 9px !important;
            font-weight: 600 !important;
            box-shadow: 0 2px 12px rgba(14, 165, 233, 0.35) !important;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: linear-gradient(135deg, #0284C7, #0EA5E9) !important;
            color: #0B0F19 !important;
        }
        /* Keep sidebar action buttons readable */
        [data-testid="stSidebar"] .stButton > button {
            color: #0B0F19 !important;
        }

        /* Alerts */
        .stWarning, div[data-testid="stAlert"] [data-baseweb="notification"] {
            border-radius: 14px !important;
        }
        .stWarning {
            background: rgba(251, 191, 36, 0.12) !important;
            border-left: 4px solid #FBBF24 !important;
            color: #FDE68A !important;
        }
        .stError {
            background: rgba(248, 113, 113, 0.12) !important;
            border-left: 4px solid #F87171 !important;
            color: #FECACA !important;
        }
        .stSuccess {
            background: rgba(52, 211, 153, 0.12) !important;
            border-left: 4px solid #34D399 !important;
            color: #A7F3D0 !important;
        }
        .stInfo {
            background: rgba(56, 189, 248, 0.12) !important;
            border-left: 4px solid #38BDF8 !important;
            color: #BAE6FD !important;
        }

        /* Inputs */
        .stTextInput input, .stNumberInput input,
        [data-baseweb="input"] input,
        [data-baseweb="select"] > div,
        .stDateInput input {
            background: #151E2E !important;
            color: #E8EEF7 !important;
            border: 1px solid #1E2A3A !important;
            border-radius: 9px !important;
        }
        .stTextInput input:focus, .stNumberInput input:focus {
            border-color: #38BDF8 !important;
            box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.22) !important;
        }

        /* File uploader */
        [data-testid="stFileUploader"],
        [data-testid="stFileUploader"] section {
            background: #151E2E !important;
            border: 1.5px dashed rgba(56, 189, 248, 0.35) !important;
            border-radius: 14px !important;
            color: #E8EEF7 !important;
        }
        /* Browse / upload button — dark text on cyan for readability */
        [data-testid="stFileUploader"] button,
        [data-testid="stFileUploader"] [data-testid="baseButton-secondary"],
        [data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"],
        [data-testid="stFileUploaderDropzone"] button,
        section[data-testid="stFileUploaderDropzone"] button {
            background: linear-gradient(135deg, #0EA5E9, #38BDF8) !important;
            color: #0B0F19 !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
        [data-testid="stFileUploader"] button *,
        [data-testid="stFileUploaderDropzone"] button * {
            color: #0B0F19 !important;
        }
        /* Dropzone helper text */
        [data-testid="stFileUploaderDropzone"],
        [data-testid="stFileUploaderDropzone"] span,
        [data-testid="stFileUploaderDropzone"] small,
        [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"],
        [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] * {
            color: #CBD5E1 !important;
        }

        /* Radio / checkbox / toggle */
        [data-testid="stRadio"] label,
        [data-testid="stCheckbox"] label,
        .stCheckbox label, .stToggle label {
            color: #E8EEF7 !important;
        }

        /* Expander */
        [data-testid="stExpander"],
        .streamlit-expanderHeader {
            background: #0F1623 !important;
            border: 1px solid #1E2A3A !important;
            border-radius: 10px !important;
            color: #E8EEF7 !important;
        }

        /* Divider */
        hr {
            border-color: #1E2A3A !important;
            opacity: 0.7;
        }

        /* Plotly */
        [data-testid="stPlotlyChart"],
        .js-plotly-plot {
            background: transparent !important;
            border-radius: 12px;
        }

        /* App logo — keep fully visible in dark mode */
        .app-logo-wrap {
            overflow: visible !important;
        }
        .app-logo-wrap img,
        [data-testid="stImage"] img,
        div[data-testid="stImage"] img {
            object-fit: contain !important;
            object-position: center center !important;
            max-height: 88px !important;
            width: auto !important;
            height: auto !important;
        }
        div[data-testid="stImage"] {
            overflow: visible !important;
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #070B14; }
        ::-webkit-scrollbar-thumb { background: #2A3A50; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #3B4F6B; }
    </style>
    """, unsafe_allow_html=True)

df = load_data_from_db()

if df.empty:
    st.warning("No data in the weld log. Upload NDE reports to get started.")
else:
    df['inspection_date'] = pd.to_datetime(df['inspection_date'])
    accepted_repairs = df[(df['is_repair'] == True) & (df['result'] == 'Accept')]
    cleared_weld_ids = {w.rsplit('R', 1)[0] for w in accepted_repairs['weld_id'] if 'R' in w}
    failed_repairs = df[(df['is_repair'] == True) & (df['result'] == 'Reject')]
    failed_weld_ids = {w.rsplit('R', 1)[0] for w in failed_repairs['weld_id'] if 'R' in w}

    def get_cleared_status(row):
        if row['result'] == 'Reject':
            if row['weld_id'] in failed_weld_ids: return 'Fail'
            elif row['weld_id'] in cleared_weld_ids: return 'Yes'
            else: return 'No'
        return ''
    df['cleared'] = df.apply(get_cleared_status, axis=1)

    st.sidebar.markdown("---")
    st.sidebar.header("Dashboard Filters")
    min_date = df['inspection_date'].min().date()
    max_date = df['inspection_date'].max().date()
    start_date, end_date = st.sidebar.date_input("Select Date Range:", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    mask = (df['inspection_date'].dt.date >= start_date) & (df['inspection_date'].dt.date <= end_date)
    filtered_df = df.loc[mask].copy()

    original_welds_df = filtered_df[(filtered_df['is_delay_scan'] == False) & (filtered_df['is_repair'] == False)]
    calc_df = original_welds_df[original_welds_df['result'] != 'Cut-out']

    # --- MOVED: Calculations before metrics display to fix NameError ---
    total_calc_welds = len(calc_df)
    rejected_welds = (calc_df['result'] == 'Reject').sum()
    reject_rate = (rejected_welds / total_calc_welds * 100) if total_calc_welds > 0 else 0
    total_cutouts = (original_welds_df['result'] == 'Cut-out').sum()
    total_delay_scans = (filtered_df['is_delay_scan'] == True).sum()
    total_failed_repairs = len(filtered_df[(filtered_df['is_repair'] == True) & (filtered_df['result'] == 'Reject')])

    st.header("📊 Project Summary")

    # --- UPDATED: Wrapped Production Metrics in container with card styling ---
    with st.container():
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.markdown("##### 📈 Production Metrics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Original Welds Inspected", f"{total_calc_welds}", delta=None)
        with col2:
            st.metric("Reject Rate", f"{reject_rate:.2f}%", delta=None)
        with col3:
            st.metric("Total Production Rejects", f"{rejected_welds}", delta=None)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- UPDATED: Wrapped Other Weld Categories in container ---
    with st.container():
        st.markdown('<div class="metric-container">', unsafe_allow_html=True)
        st.markdown("##### ⚙️ Other Weld Metrics")
        col4, col5, col6 = st.columns(3)
        with col4:
            st.metric("Total Cut-outs", f"{total_cutouts}", delta=None)
        with col5:
            st.metric("Delay Scans", f"{total_delay_scans}", delta=None)
        with col6:
            st.metric("Failed Repairs", f"{total_failed_repairs}", delta=None)
        st.markdown('</div>', unsafe_allow_html=True)
    
    if not calc_df.empty:
        with st.container():
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.markdown("##### 🔍 Summary by Weld Type")
            summary_df = calc_df.groupby('weld_type').agg(accepted=('result', lambda x: (x == 'Accept').sum()), rejected=('result', lambda x: (x == 'Reject').sum()), total=('weld_id', 'count')).reset_index()
            summary_df['reject_rate'] = (summary_df['rejected'] / summary_df['total'] * 100)
            summary_df = summary_df.rename(columns={'weld_type':'Weld Type','accepted':'Accepted','rejected':'Rejected','total':'Total Inspected','reject_rate':'Reject Rate (%)'})
            st.dataframe(summary_df.style.format({'Reject Rate (%)': '{:.2f}'}), width='stretch')
            st.markdown('</div>', unsafe_allow_html=True)

    # ========== Daily / Weekly Auto-Report PDF ==========
    st.markdown("---")
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("📄 Quality Summary Report")
        st.caption("One-page Daily or Weekly report for field leadership and owner updates.")

        report_col1, report_col2, report_col3 = st.columns([1.2, 1.2, 2])
        with report_col1:
            report_period = st.radio(
                "Report period",
                ["Daily (latest day)", "Weekly (last 7 days)", "Current filter"],
                index=0,
                key="report_period_choice"
            )
        with report_col2:
            st.write("")  # spacer
            st.write("")

        # Build report dataset based on period choice
        max_insp = filtered_df['inspection_date'].max()
        if report_period.startswith("Daily"):
            report_df = filtered_df[filtered_df['inspection_date'] == max_insp].copy()
            period_label = max_insp.strftime("%b %d, %Y")
            report_type = "DAILY REPORT"
        elif report_period.startswith("Weekly"):
            week_start = max_insp - pd.Timedelta(days=6)
            report_df = filtered_df[filtered_df['inspection_date'] >= week_start].copy()
            period_label = f"{week_start.strftime('%b %d')} - {max_insp.strftime('%b %d, %Y')}"
            report_type = "WEEKLY REPORT"
        else:
            report_df = filtered_df.copy()
            period_label = f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
            report_type = "PERIOD REPORT"

        # Metrics for the report period
        r_original = report_df[(report_df['is_delay_scan'] == False) & (report_df['is_repair'] == False)]
        r_calc = r_original[r_original['result'] != 'Cut-out']
        r_total = len(r_calc)
        r_rejects = int((r_calc['result'] == 'Reject').sum()) if r_total > 0 else 0
        r_rate = (r_rejects / r_total * 100) if r_total > 0 else 0.0
        r_cutouts = int((r_original['result'] == 'Cut-out').sum())

        # Backlog & critical from full filtered view (current project status)
        report_repair_df = original_welds_df[(original_welds_df['result'] == 'Reject') & (original_welds_df['cleared'].isin(['No', 'Fail']))]
        report_critical_df = original_welds_df[(original_welds_df['result'] == 'Cut-out') | (original_welds_df['cleared'] == 'Fail')]
        backlog_count = len(report_repair_df)
        critical_count = len(report_critical_df)

        # Aging buckets for open backlog
        today = pd.Timestamp.now().normalize()
        aging_buckets = {"0-3 days": 0, "4-7 days": 0, "8-14 days": 0, "15+ days": 0}
        top_rejects = None
        if not report_repair_df.empty:
            tmp = report_repair_df.copy()
            tmp['days_open'] = (today - pd.to_datetime(tmp['inspection_date']).dt.normalize()).dt.days
            aging_buckets = {
                "0-3 days": int((tmp['days_open'] <= 3).sum()),
                "4-7 days": int(((tmp['days_open'] >= 4) & (tmp['days_open'] <= 7)).sum()),
                "8-14 days": int(((tmp['days_open'] >= 8) & (tmp['days_open'] <= 14)).sum()),
                "15+ days": int((tmp['days_open'] >= 15).sum()),
            }
            top_rejects = tmp.sort_values('days_open', ascending=False)

        # Weld type summary for report period
        report_summary = None
        if not r_calc.empty:
            report_summary = r_calc.groupby('weld_type').agg(
                accepted=('result', lambda x: (x == 'Accept').sum()),
                rejected=('result', lambda x: (x == 'Reject').sum()),
                total=('weld_id', 'count')
            ).reset_index()
            report_summary['reject_rate'] = (report_summary['rejected'] / report_summary['total'] * 100)
            report_summary = report_summary.rename(columns={
                'weld_type': 'Weld Type', 'accepted': 'Accepted',
                'rejected': 'Rejected', 'total': 'Total Inspected',
                'reject_rate': 'Reject Rate (%)'
            })

        metrics_dict = {
            'total_welds': r_total,
            'reject_rate': r_rate,
            'rejects': r_rejects,
            'cutouts': r_cutouts,
        }

        # Project-wide metrics (entire database, not limited to Daily/Weekly window)
        p_original = df[(df['is_delay_scan'] == False) & (df['is_repair'] == False)]
        p_calc = p_original[p_original['result'] != 'Cut-out']
        p_total = len(p_calc)
        p_rejects = int((p_calc['result'] == 'Reject').sum()) if p_total > 0 else 0
        p_rate = (p_rejects / p_total * 100) if p_total > 0 else 0.0
        p_cutouts = int((p_original['result'] == 'Cut-out').sum())
        project_metrics_dict = {
            'total_welds': p_total,
            'reject_rate': p_rate,
            'rejects': p_rejects,
            'cutouts': p_cutouts,
        }

        with report_col3:
            try:
                pdf_bytes = generate_summary_report_pdf(
                    report_type=report_type,
                    period_label=period_label,
                    metrics=metrics_dict,
                    weld_type_summary=report_summary,
                    backlog_count=backlog_count,
                    critical_count=critical_count,
                    aging_buckets=aging_buckets,
                    top_rejects=top_rejects,
                    project_metrics=project_metrics_dict,
                )
                fname = f"{report_type.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d')}.pdf"
                st.download_button(
                    label="📥 Download 1-Page Report PDF",
                    data=pdf_bytes,
                    file_name=fname,
                    mime="application/pdf",
                    key="btn_summary_report_pdf"
                )
            except Exception as e:
                st.error(f"Could not generate report: {e}")

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    # --- UPDATED: Analytics with containers and icons ---
    st.subheader("📈 Analytics & Trends (Original Welds Only, Excludes Cut-outs)")
    with st.container():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        viz_col1, viz_col2 = st.columns(2)
        with viz_col1:
            st.markdown("#### 📊 Reject Rate by Weld Type")
            if not calc_df.empty:
                weld_type_summary = calc_df.groupby('weld_type').apply(lambda x: (x['result'] == 'Reject').sum() / len(x) * 100 if len(x) > 0 else 0, include_groups=False).reset_index(name='Reject Rate')
                fig = px.bar(
                    weld_type_summary.sort_values(by='Reject Rate', ascending=False),
                    x='weld_type', y='Reject Rate', text_auto='.2f',
                    title="Reject Rate % by Weld Type",
                    color_discrete_sequence=['#38BDF8'] if dark_mode else ['#2563EB']
                )
                fig.update_traces(texttemplate='%{y:.2f}%', textposition='outside')
                if dark_mode:
                    fig.update_layout(
                        template="plotly_dark",
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#E8EEF7', family='Inter'),
                        title_font=dict(color='#F8FAFC', size=16),
                        xaxis=dict(gridcolor='rgba(255,255,255,0.06)', zerolinecolor='rgba(255,255,255,0.1)'),
                        yaxis=dict(gridcolor='rgba(255,255,255,0.06)', zerolinecolor='rgba(255,255,255,0.1)'),
                        margin=dict(t=50, b=40, l=40, r=20)
                    )
                else:
                    fig.update_layout(margin=dict(t=50, b=40, l=40, r=20))
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No weld type data to display.")
        with viz_col2:
            st.markdown("#### 📉 Reject Rate Trend")
            if not calc_df.empty:
                daily_summary = calc_df.groupby('inspection_date').agg(total_welds=('weld_id', 'count'), rejected_welds=('result', lambda x: (x == 'Reject').sum())).reset_index()
                daily_summary['Daily Reject Rate'] = (daily_summary['rejected_welds'] / daily_summary['total_welds']) * 100
                daily_summary['Cumulative Welds'] = daily_summary['total_welds'].cumsum()
                daily_summary['Cumulative Rejects'] = daily_summary['rejected_welds'].cumsum()
                daily_summary['Cumulative Reject Rate'] = (daily_summary['Cumulative Rejects'] / daily_summary['Cumulative Welds']) * 100
                fig = go.Figure()
                bar_color = 'rgba(56, 189, 248, 0.55)' if dark_mode else 'rgba(37, 99, 235, 0.6)'
                line_color = '#FBBF24' if dark_mode else '#D97706'
                fig.add_trace(go.Bar(x=daily_summary['inspection_date'], y=daily_summary['Daily Reject Rate'], name='Daily Reject Rate %', marker_color=bar_color))
                fig.add_trace(go.Scatter(x=daily_summary['inspection_date'], y=daily_summary['Cumulative Reject Rate'], name='Cumulative Reject Rate %', line=dict(color=line_color, width=2.5)))
                layout_kwargs = dict(
                    title='Daily & Cumulative Reject Rate Trend',
                    yaxis_title='Reject Rate (%)',
                    margin=dict(t=50, b=40, l=40, r=20),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )
                if dark_mode:
                    layout_kwargs.update(dict(
                        template="plotly_dark",
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#E8EEF7', family='Inter'),
                        title_font=dict(color='#F8FAFC', size=16),
                        xaxis=dict(gridcolor='rgba(255,255,255,0.06)'),
                        yaxis=dict(gridcolor='rgba(255,255,255,0.06)')
                    ))
                fig.update_layout(**layout_kwargs)
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No trend data to display.")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    # --- UPDATED: Repair Backlog in section card ---
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("🚨 Repair Backlog")
    repair_df = original_welds_df[(original_welds_df['result'] == 'Reject') & (original_welds_df['cleared'].isin(['No', 'Fail']))]
    if repair_df.empty:
        st.success("No outstanding repairs.")
    else:
        st.warning(f"There are {len(repair_df)} welds requiring repair.")
        backlog_display_cols = ['inspection_date', 'report_number', 'diameter', 'wall_thickness', 'stationing', 'weld_id', 'defect_type', 'defect_start', 'defect_length', 'defect_depth', 'defect_height']
        backlog_rename_map = {'inspection_date':'Date','report_number':'Report ID','diameter':'Diameter','wall_thickness':'WT','stationing':'Station','weld_id':'Weld ID','defect_type':'Defect Type','defect_start':'Start','defect_length':'Length','defect_depth':'Depth','defect_height':'Height'}
        cols_to_display_backlog = [col for col in backlog_display_cols if col in repair_df.columns]
        display_df_backlog = repair_df[cols_to_display_backlog].rename(columns=backlog_rename_map)
        if 'Report ID' in display_df_backlog.columns:
            cols = display_df_backlog.columns.tolist()
            report_id_idx = cols.index('Report ID')
            if 'Diameter' in cols and cols.index('Diameter') != report_id_idx + 1:
                cols.remove('Diameter')
                cols.insert(report_id_idx + 1, 'Diameter')
            if 'WT' in cols and cols.index('WT') != report_id_idx + 2:
                cols.remove('WT')
                cols.insert(report_id_idx + 2, 'WT')
            display_df_backlog = display_df_backlog[cols]
        display_df_backlog['Date'] = pd.to_datetime(display_df_backlog['Date']).dt.date
        if 'Diameter' in display_df_backlog.columns:
            display_df_backlog['Diameter'] = display_df_backlog['Diameter'].apply(lambda x: f"{float(x):.3f}" if pd.notnull(x) and x != '' else '')
        st.dataframe(display_df_backlog, width='stretch')
        pdf_data = generate_pdf(display_df_backlog)
        st.download_button(label="📥 Download Backlog as PDF", data=pdf_data, file_name=f"Repair_Backlog_{datetime.now().strftime('%Y-%m-%d')}.pdf", mime="application/pdf")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    # --- UPDATED: Critical Issues in section card ---
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.header("✂️ Critical Issues")
    critical_df = original_welds_df[(original_welds_df['result'] == 'Cut-out') | (original_welds_df['cleared'] == 'Fail')]
    if critical_df.empty:
        st.info("No cut-outs or failed repairs.")
    else:
        st.error(f"There are {len(critical_df)} critical items requiring attention.")
        critical_display_cols = ['inspection_date', 'report_number', 'stationing', 'weld_id', 'suffix', 'result', 'cleared', 'comments', 'diameter']
        critical_rename_map = {'inspection_date':'Date','report_number':'Report ID','stationing':'Station','weld_id':'Weld ID','suffix':'Suffix','result':'Status','cleared':'Repair Status','comments':'Comments','diameter':'Diameter'}
        cols_to_display_critical = [col for col in critical_display_cols if col in critical_df.columns]
        display_df_critical = critical_df[cols_to_display_critical].rename(columns=critical_rename_map)
        if 'Weld ID' in display_df_critical.columns and 'Suffix' in display_df_critical.columns:
            cols = display_df_critical.columns.tolist()
            weld_id_idx = cols.index('Weld ID')
            if 'Suffix' in cols and cols.index('Suffix') != weld_id_idx + 1:
                cols.remove('Suffix')
                cols.insert(weld_id_idx + 1, 'Suffix')
            if 'Height' in cols:
                height_idx = cols.index('Height')
                if 'Comments' in cols and cols.index('Comments') != height_idx + 1:
                    cols.remove('Comments')
                    cols.insert(height_idx + 1, 'Comments')
            else:
                if 'Comments' in cols:
                    cols.remove('Comments')
                    cols.append('Comments')
            display_df_critical = display_df_critical[cols]
        display_df_critical['Date'] = pd.to_datetime(display_df_critical['Date']).dt.date
        if 'Diameter' in display_df_critical.columns:
            display_df_critical['Diameter'] = display_df_critical['Diameter'].apply(lambda x: f"{float(x):.3f}" if pd.notnull(x) and x != '' else '')
        st.dataframe(display_df_critical, width='stretch')
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    # --- UPDATED: Full Weld Log in section card ---
    with st.expander("📖 View Full Project Weld Log (All Scans)"):
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        DEFAULT_DISPLAY_COLS = [
            'inspection_date', 'report_number', 'nde_method', 'rig_id', 'weld_type', 
            'diameter', 'wall_thickness', 'stationing', 'weld_id', 'suffix', 'result', 'cleared', 
            'welder_ids', 'defect_type', 'defect_start', 'defect_length', 'defect_depth', 'defect_height', 'comments'
        ]
        DEFAULT_RENAME_MAP = {
            'inspection_date':'Inspection Date','report_number':'Report #','nde_method':'NDE Method',
            'rig_id':'Rig','weld_type':'Weld Type','diameter':'Diameter','wall_thickness':'WT',
            'stationing':'Station','weld_id':'Weld ID','suffix':'Suffix','result':'Result','cleared':'Cleared',
            'welder_ids':'Welder IDs','defect_type':'Defect Type','defect_start':'Defect Start',
            'defect_length':'Length','defect_depth':'Depth','defect_height':'Height','comments':'Comments'
        }
        cols_to_display_full = [col for col in DEFAULT_DISPLAY_COLS if col in df.columns]
        display_df_full = df[cols_to_display_full].rename(columns=DEFAULT_RENAME_MAP)
        if 'Weld ID' in display_df_full.columns and 'Suffix' in display_df_full.columns:
            cols = display_df_full.columns.tolist()
            weld_id_idx = cols.index('Weld ID')
            if 'Suffix' in cols and cols.index('Suffix') != weld_id_idx + 1:
                cols.remove('Suffix')
                cols.insert(weld_id_idx + 1, 'Suffix')
            if 'Comments' in cols and 'Height' in cols:
                height_idx = cols.index('Height')
                if cols.index('Comments') != height_idx + 1:
                    cols.remove('Comments')
                    cols.insert(height_idx + 1, 'Comments')
            display_df_full = display_df_full[cols]
        display_df_full['Inspection Date'] = pd.to_datetime(display_df_full['Inspection Date']).dt.date
        if 'Diameter' in display_df_full.columns:
            display_df_full['Diameter'] = display_df_full['Diameter'].apply(lambda x: f"{float(x):.3f}" if pd.notnull(x) and x != '' else '')
        st.dataframe(display_df_full, width='stretch')
        st.markdown('</div>', unsafe_allow_html=True)
# --- Password-protected Admin menu (always last in the sidebar) ---
st.sidebar.markdown("---")
st.sidebar.header("🔒 Admin")

# Track authentication in session state
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# Login form (only shown when not authenticated)
if not st.session_state.admin_authenticated:
    admin_pwd = st.sidebar.text_input("Enter admin password", type="password", key="admin_pwd_input")
    if st.sidebar.button("Log in", key="btn_admin_login"):
        if admin_pwd == ADMIN_PASSWORD:
            st.session_state.admin_authenticated = True
            st.rerun()
        else:
            st.sidebar.error("Incorrect password")
else:
    # --- Authenticated Admin controls ---
    st.sidebar.success("Access granted")

    if st.sidebar.button("🚪 Log out", key="btn_admin_logout"):
        st.session_state.admin_authenticated = False
        st.rerun()

    # Upload NDE reports (admin only)
    st.sidebar.markdown("---")
    st.sidebar.subheader("Upload NDE Reports")
    if "nde_uploader_key" not in st.session_state:
        st.session_state.nde_uploader_key = 0

    uploaded_files = st.sidebar.file_uploader(
        "Select NDE PDF reports",
        type="pdf",
        accept_multiple_files=True,
        key=f"nde_uploader_{st.session_state.nde_uploader_key}"
    )
    if st.sidebar.button("Process Uploaded Reports", key="btn_process_nde"):
        if uploaded_files:
            with st.status("Processing reports...", expanded=True) as status:
                db = get_db_session()
                existing_ids = {id_tuple[0] for id_tuple in db.query(Weld.weld_id).all()}
                success_count = 0
                error_files = []
                for uploaded_file in uploaded_files:
                    try:
                        status.update(label=f"Processing {uploaded_file.name}...")
                        list_of_welds = parse_nde_report(uploaded_file)
                        for weld_data in list_of_welds:
                            weld_id = weld_data['weld_id']
                            if weld_id in existing_ids:
                                continue
                            new_weld = Weld(**weld_data)
                            db.add(new_weld)
                            existing_ids.add(weld_id)
                            success_count += 1
                    except Exception as e:
                        error_files.append(uploaded_file.name)
                        st.sidebar.error(f"Error parsing {uploaded_file.name}")
                        with st.sidebar.expander("See error details"):
                            st.code(traceback.format_exc())
                db.commit()
                db.close()
                status.update(
                    label=f"Processing complete. Added {success_count} new weld records.",
                    state="complete",
                    expanded=False
                )
            if error_files:
                st.sidebar.error(f"Failed to process: {', '.join(error_files)}")
            st.session_state.nde_uploader_key += 1
            st.rerun()
        else:
            st.sidebar.warning("No files uploaded.")

    # Clear all weld entries
    st.sidebar.markdown("---")
    confirm_clear_data = st.sidebar.checkbox(
        "I understand this will permanently delete ALL weld records",
        key="confirm_clear_data"
    )
    if st.sidebar.button("🗑️ Clear All Weld Entries", disabled=not confirm_clear_data, key="btn_clear_data"):
        db = get_db_session()
        try:
            deleted_count = db.query(Weld).delete()
            db.commit()
            st.sidebar.success(f"Successfully deleted {deleted_count} weld record(s).")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error clearing database: {e}")
        finally:
            db.close()

    # Clear logo image
    if st.sidebar.button("🖼️ Clear Company Logo", key="btn_clear_logo"):
        if os.path.exists(LOGO_PATH):
            try:
                os.remove(LOGO_PATH)
                st.session_state.logo_saved = False
                if "logo_uploader_key" in st.session_state:
                    st.session_state.logo_uploader_key += 1
                st.sidebar.success("Company logo removed successfully.")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error removing logo: {e}")
        else:
            st.sidebar.info("No logo file found to clear.")

    # Upload / replace company logo
    st.sidebar.markdown("---")
    st.sidebar.subheader("Company Logo")
    if "logo_uploader_key" not in st.session_state:
        st.session_state.logo_uploader_key = 0

    logo_file = st.sidebar.file_uploader(
        "Upload your company logo (PNG)",
        type=["png"],
        key=f"logo_uploader_{st.session_state.logo_uploader_key}"
    )
    if logo_file is not None:
        try:
            if not os.path.exists(ASSETS_DIR):
                os.makedirs(ASSETS_DIR)
            with open(LOGO_PATH, "wb") as f:
                f.write(logo_file.getbuffer())
            st.session_state.logo_saved = True
            st.session_state.logo_uploader_key += 1
            st.sidebar.success("Logo uploaded and saved permanently.")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Failed to save logo: {e}")

    # Change admin password
    st.sidebar.markdown("---")
    st.sidebar.subheader("Change Admin Password")
    with st.sidebar.form("change_password_form", clear_on_submit=True):
        new_pwd = st.text_input("New password", type="password", key="new_admin_pwd")
        confirm_pwd = st.text_input("Confirm new password", type="password", key="confirm_admin_pwd")
        submitted = st.form_submit_button("💾 Save New Password")

        if submitted:
            if not new_pwd or not new_pwd.strip():
                st.error("New password cannot be empty.")
            elif new_pwd != confirm_pwd:
                st.error("Passwords do not match.")
            elif len(new_pwd.strip()) < 4:
                st.error("Password must be at least 4 characters.")
            else:
                try:
                    save_admin_password(new_pwd.strip())
                    st.success("Password changed successfully! Please log in again with the new password.")
                    st.session_state.admin_authenticated = False  # force re-login
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to save password: {e}")
