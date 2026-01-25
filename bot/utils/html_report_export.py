"""HTML report generation for financial statistics."""

import logging
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Color definitions (dark theme + income/expense separation)
COLOR_BODY_BG = "#121212"
COLOR_CONTAINER_BG = "#1e1e1e"
COLOR_CARD_BG = "#2a2a2a"
COLOR_TEXT = "#e0e0e0"          # off-white
COLOR_TEXT_MUTED = "#9e9e9e"

COLOR_BORDER = "rgba(255, 255, 255, 0.10)"
COLOR_DIVIDER = "rgba(255, 255, 255, 0.08)"
COLOR_SHADOW = "rgba(0, 0, 0, 0.55)"
COLOR_GLOW = "rgba(255, 255, 255, 0.03)"

# Income (green)
COLOR_INCOME_ACCENT = "#81C784"
COLOR_INCOME_SECTION = "#E8F5E9"  # used as subtle tint in dark theme
COLOR_INCOME_BAR_FROM = "#6B9B7A"
COLOR_INCOME_BAR_TO = "#A8D5BA"

# Expense (soft red/orange)
COLOR_EXPENSE_ACCENT = "#E57373"
COLOR_EXPENSE_SECTION = "#FFEBEE"  # used as subtle tint in dark theme
COLOR_EXPENSE_BAR_FROM = "#D07676"
COLOR_EXPENSE_BAR_TO = "#E89A8C"


def generate_html_report(
    family_name: str,
    period_name: str,
    stats: Dict,
    budget: Optional[Decimal] = None,
    report_type: str = "monthly"
) -> BytesIO:
    """Generate HTML report for financial statistics.
    
    Args:
        family_name: Name of the family
        period_name: Period name (e.g., "Январь 2024")
        stats: Statistics data with categories
        budget: Optional budget amount
        report_type: Type of report ("monthly" or "yearly")
        
    Returns:
        BytesIO object containing HTML data
    """
    try:
        html = _create_html_structure(family_name, period_name, stats, budget, report_type)
        
        # Convert to BytesIO
        byte_buffer = BytesIO()
        byte_buffer.write(html.encode('utf-8'))
        byte_buffer.seek(0)
        
        logger.info(f"Generated HTML report: {period_name}")
        return byte_buffer
        
    except Exception as e:
        logger.error(f"Error generating HTML report: {e}", exc_info=True)
        raise


def _create_html_structure(
    family_name: str,
    period_name: str,
    stats: Dict,
    budget: Optional[Decimal],
    report_type: str
) -> str:
    """Create HTML structure for the report."""
    
    expense_total = stats.get('expense_total', stats.get('total', Decimal('0')))
    income_total = stats.get('income_total', Decimal('0'))
    balance = stats.get('balance', income_total - expense_total)
    expense_categories = stats.get('expense_by_category', stats.get('by_category', []))
    income_categories = stats.get('income_by_category', [])
    
    # Calculate statistics
    remaining = budget - expense_total if budget else None
    percentage = (expense_total / budget * 100) if budget and budget > 0 else 0
    savings_percentage = ((budget - expense_total) / budget * 100) if budget and budget > 0 else 0

    report_title = _get_report_title(period_name)
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title} - {family_name}</title>
    <style>
        {_get_css_styles()}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-section">
            <div class="header-left">
                <p>Семья: {family_name}</p>
                <p>Период: {period_name}</p>
            </div>
            <h1 class="main-title">{report_title}</h1>
            <div class="header-right">
                <p class="header-metric header-metric--income">Доходы: {income_total:,.0f} ₽</p>
                <p class="header-metric header-metric--expense">Расходы: {expense_total:,.0f} ₽</p>
                <p class="header-metric">Баланс: {balance:,.0f} ₽</p>
            </div>
        </div>

        {_create_budget_info(budget) if budget else ''}
        
        {_create_statistics_section(expense_total, budget, remaining, savings_percentage) if budget else ''}

        {_create_charts_row(expense_categories, expense_total, income_categories, income_total)}
        
        <div class="section">
            <h2 class="section-title">Детальные расходы по категориям</h2>
            {_create_detailed_categories(expense_categories, "expense")}
        </div>
        
        <div class="section">
            <h2 class="section-title">Детальные доходы по категориям</h2>
            {_create_detailed_categories(income_categories, "income")}
        </div>
        
        <div class="footer">
            <p>Отчет создан {datetime.now().strftime('%d.%m.%Y в %H:%M')}</p>
            <p>Family Finance Bot</p>
        </div>
    </div>
    <script>
        {_get_pie_interaction_script()}
    </script>
</body>
</html>"""
    
    return html


def _get_css_styles() -> str:
    """Get CSS styles for the report."""
    return f"""
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
            color: {COLOR_TEXT};
            background: {COLOR_BODY_BG};
            padding: 20px;
        }}
        
        .container {{
            max-width: 1040px;
            margin: 0 auto;
            background: {COLOR_CONTAINER_BG};
            padding: 28px;
            border-radius: 16px;
            box-shadow: 0 12px 32px {COLOR_SHADOW}, 0 0 0 1px {COLOR_GLOW};
            border: 1px solid {COLOR_BORDER};
        }}
        
        .header-section {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
            margin-bottom: 14px;
            padding-bottom: 10px;
            border-bottom: 1px solid {COLOR_DIVIDER};
        }}

        .header-left,
        .header-right {{
            font-size: 14px;
            line-height: 1.6;
            color: {COLOR_TEXT_MUTED};
        }}

        .header-left p,
        .header-right p {{
            margin: 4px 0;
        }}

        .main-title {{
            color: {COLOR_TEXT};
            font-size: 28px;
            font-weight: 750;
            letter-spacing: -0.01em;
            margin: 0;
            padding: 0;
            border: 0;
            flex: 1;
            display: flex;
            justify-content: center;
        }}

        .header-metric {{
            color: {COLOR_TEXT};
        }}

        .header-metric--income {{
            color: {COLOR_INCOME_ACCENT};
        }}

        .header-metric--expense {{
            color: {COLOR_EXPENSE_ACCENT};
        }}

        .budget-info {{
            text-align: right;
            font-size: 16px;
            color: {COLOR_TEXT};
            margin-bottom: 14px;
            padding: 10px 12px;
            background: {COLOR_CARD_BG};
            border-radius: 14px;
            border: 1px solid {COLOR_BORDER};
            box-shadow: 0 8px 18px {COLOR_SHADOW}, 0 0 0 1px {COLOR_GLOW};
        }}
        
        .statistics {{
            margin: 16px 0;
            padding: 16px;
            background: {COLOR_CARD_BG};
            color: {COLOR_TEXT};
            border-radius: 16px;
            border: 1px solid {COLOR_BORDER};
            box-shadow: 0 10px 26px {COLOR_SHADOW}, 0 0 0 1px {COLOR_GLOW};
        }}
        
        .stat-row {{
            display: flex;
            justify-content: space-between;
            margin: 6px 0;
            gap: 16px;
            padding: 10px 12px;
            background: #242424;
            border-radius: 14px;
            border: 1px solid {COLOR_DIVIDER};
        }}

        .stat-row span {{
            color: {COLOR_TEXT_MUTED};
        }}

        .stat-row strong {{
            color: {COLOR_TEXT};
        }}
        
        .section {{
            margin: 24px 0;
        }}
        
        .section-title {{
            color: {COLOR_TEXT};
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 0;
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 1px solid {COLOR_DIVIDER};
        }}
        
        .chart {{
            margin: 12px 0;
            padding: 14px;
            background: {COLOR_CARD_BG};
            border-radius: 16px;
            border: 1px solid {COLOR_BORDER};
            box-shadow: 0 10px 26px {COLOR_SHADOW}, 0 0 0 1px {COLOR_GLOW};
            transition: transform 160ms ease, box-shadow 160ms ease;
        }}
        
        .chart:hover {{
            transform: translateY(-2px);
            box-shadow: 0 12px 32px {COLOR_SHADOW}, 0 0 0 1px {COLOR_GLOW};
            filter: brightness(1.05);
        }}

        /* Section-specific tint (dark theme friendly). Uses provided light tints with low opacity. */
        .chart--income {{
            background-image: linear-gradient(0deg, rgba(232, 245, 233, 0.07), rgba(232, 245, 233, 0.07));
        }}

        .chart--expense {{
            background-image: linear-gradient(0deg, rgba(255, 235, 238, 0.07), rgba(255, 235, 238, 0.07));
        }}

        .charts-row {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin: 16px 0;
            align-items: stretch; /* make both cards equal height (match the tallest) */
        }}

        .charts-row .chart {{
            width: 100%;
            max-width: none;
            margin: 0;
        }}

        .chart-title {{
            font-size: 16px;
            font-weight: 750;
            margin-bottom: 10px;
            color: {COLOR_TEXT};
            text-align: center;
        }}

        .pie-chart-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .pie-chart {{
            width: 220px;
            height: 220px;
            display: block;
        }}

        .pie-segment {{
            cursor: pointer;
            transition: filter 0.3s ease, opacity 0.3s ease;
            pointer-events: visibleStroke;
        }}

        .pie-segment:hover {{
            filter: brightness(1.15);
        }}

        .pie-segment.is-dimmed {{
            opacity: 0.3;
        }}

        .pie-segment.is-highlighted {{
            opacity: 1;
            filter: brightness(1.25);
        }}

        .pie-separator {{
            opacity: 0.30;
        }}

        .pie-legend {{
            margin-top: 16px;
            width: max-content;
            max-width: 100%;
            margin-left: auto;
            margin-right: auto;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            justify-content: flex-start;
            gap: 8px;
            margin: 6px 0;
            color: {COLOR_TEXT_MUTED};
            transition: filter 140ms ease, opacity 140ms ease, background-color 140ms ease, border-color 140ms ease, transform 140ms ease;
        }}

        .legend-item.is-dimmed {{
            opacity: 0.45;
        }}

        .legend-item.is-highlighted {{
            color: {COLOR_TEXT};
        }}

        .legend-color {{
            width: 12px;
            height: 12px;
            border-radius: 2px;
            flex: 0 0 auto;
        }}

        .legend-label {{
            font-size: 13px;
            line-height: 1.5;
            color: {COLOR_TEXT_MUTED};
            display: inline-block;
            padding: 6px 8px;
            border-radius: 10px;
            border: 1px solid transparent;
            transition: filter 140ms ease, background-color 140ms ease, border-color 140ms ease, transform 140ms ease;
            text-align: left;
        }}

        .legend-label:hover {{
            filter: brightness(1.08);
        }}

        .legend-item.is-highlighted .legend-label {{
            color: {COLOR_TEXT};
            font-weight: 650;
            background: rgba(255, 255, 255, 0.06);
            border-color: {COLOR_BORDER};
            transform: translateX(2px);
        }}
        
        .expenses-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            overflow: hidden;
            border-radius: 14px;
            border: 1px solid {COLOR_BORDER};
        }}
        
        .expenses-table th {{
            background: #242424;
            color: {COLOR_TEXT};
            padding: 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 1px solid {COLOR_DIVIDER};
        }}
        
        .expenses-table td {{
            padding: 12px;
            border-bottom: 1px solid {COLOR_DIVIDER};
            color: {COLOR_TEXT};
            background: {COLOR_CARD_BG};
        }}
        
        .expenses-table tr:nth-child(even) td {{
            background: #272727;
        }}
        
        .expenses-table tr:hover {{
            filter: brightness(1.05);
        }}
        
        .category-detail {{
            margin: 0;
            padding: 14px;
            border: 1px solid {COLOR_BORDER};
            background: {COLOR_CARD_BG};
            border-radius: 16px;
            box-shadow: 0 9px 22px {COLOR_SHADOW}, 0 0 0 1px {COLOR_GLOW};
            transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
        }}

        .category-detail:hover {{
            transform: translateY(-2px);
            box-shadow: 0 12px 32px {COLOR_SHADOW}, 0 0 0 1px {COLOR_GLOW};
            filter: brightness(1.05);
        }}

        .category-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
        }}

        @media (max-width: 820px) {{
            .category-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .category-header {{
            font-size: 16px;
            font-weight: 750;
            color: {COLOR_TEXT};
            margin-bottom: 8px;
            letter-spacing: 0;
        }}
        
        .category-amount {{
            font-size: 16px;
            color: {COLOR_TEXT};
            margin-bottom: 6px;
            font-variant-numeric: tabular-nums;
        }}

        .category-amount strong {{
            color: {COLOR_INCOME_ACCENT};
        }}

        .category-grid--expense .category-amount strong {{
            color: {COLOR_EXPENSE_ACCENT};
        }}
        
        .category-percentage {{
            font-size: 14px;
            color: {COLOR_TEXT_MUTED};
        }}
        
        .expenses-list {{
            margin-top: 10px;
            border-top: 1px solid {COLOR_DIVIDER};
            padding-top: 10px;
        }}
        
        .expenses-list-title {{
            font-size: 14px;
            font-weight: bold;
            color: {COLOR_TEXT_MUTED};
            margin-bottom: 10px;
        }}
        
        .expense-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            padding: 8px 10px;
            margin: 4px 0;
            background: #242424;
            border-radius: 14px;
            border: 1px solid {COLOR_DIVIDER};
            font-size: 13px;
            transition: transform 140ms ease, box-shadow 140ms ease;
        }}

        .expense-item:nth-child(even) {{
            background: #272727;
        }}

        .expense-item:hover {{
            transform: translateY(-1px);
            box-shadow: 0 10px 22px {COLOR_SHADOW}, 0 0 0 1px {COLOR_GLOW};
            filter: brightness(1.05);
        }}
        
        .expense-date {{
            font-size: 13px;
            color: {COLOR_TEXT_MUTED};
            min-width: 90px;
        }}
        
        .expense-description {{
            flex: 1;
            font-size: 13px;
            color: {COLOR_TEXT};
            margin: 0;
        }}
        
        .expense-amount {{
            font-size: 13px;
            font-weight: bold;
            color: {COLOR_INCOME_ACCENT};
            min-width: 100px;
            text-align: right;
            font-variant-numeric: tabular-nums;
        }}

        .category-grid--expense .expense-amount {{
            color: {COLOR_EXPENSE_ACCENT};
        }}

        /* Kind-specific hover tint */
        .category-grid--income .expense-item:hover {{
            background: rgba(232, 245, 233, 0.10);
        }}

        .category-grid--expense .expense-item:hover {{
            background: rgba(255, 235, 238, 0.10);
        }}

        .chart--income:hover {{
            box-shadow: 0 12px 32px {COLOR_SHADOW}, 0 0 0 1px rgba(129, 199, 132, 0.18);
        }}

        .chart--expense:hover {{
            box-shadow: 0 12px 32px {COLOR_SHADOW}, 0 0 0 1px rgba(229, 115, 115, 0.18);
        }}
        
        .footer {{
            margin-top: 32px;
            padding-top: 14px;
            border-top: 1px solid {COLOR_DIVIDER};
            text-align: center;
            color: {COLOR_TEXT_MUTED};
            font-size: 14px;
        }}
        
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                padding: 20px;
            }}
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 14px;
            }}
            .container {{
                padding: 16px;
            }}
            .main-title {{
                font-size: 24px;
            }}
            .section-title {{
                font-size: 17px;
            }}
            .chart {{
                padding: 12px;
            }}
            .category-detail {{
                padding: 12px;
            }}

            .header-section {{
                flex-direction: column;
                align-items: center;
                text-align: center;
            }}

            .header-left,
            .header-right {{
                text-align: center;
            }}

            .main-title {{
                justify-content: center;
            }}

            .charts-row {{
                grid-template-columns: 1fr;
            }}

            .pie-chart {{
                width: 200px;
                height: 200px;
            }}
        }}
    """


def _create_budget_info(budget: Decimal) -> str:
    """Create budget information section."""
    return f"""
        <div class="budget-info">
            <strong>Начальная сумма:</strong> {budget:,.0f} ₽
        </div>
    """


def _create_statistics_section(
    total: Decimal,
    budget: Decimal,
    remaining: Optional[Decimal],
    savings_percentage: float
) -> str:
    """Create statistics section."""
    return f"""
        <div class="statistics">
            <div class="stat-row">
                <span>Остаток на конец периода:</span>
                <strong>{remaining:,.0f} ₽</strong>
            </div>
            <div class="stat-row">
                <span>На столько увеличились общие сбережения:</span>
                <strong>{savings_percentage:+.1f}%</strong>
            </div>
            <div class="stat-row">
                <span>Сэкономлено в этом месяце:</span>
                <strong>{remaining:,.0f} ₽</strong>
            </div>
        </div>
    """



def _create_charts_row(
    expense_categories: List[Dict],
    expense_total: Decimal,
    income_categories: List[Dict],
    income_total: Decimal
) -> str:
    """Render expense + income charts side-by-side (responsive)."""
    expense_chart = _create_chart_section(expense_categories, expense_total, "Расходы")
    income_chart = _create_chart_section(income_categories, income_total, "Доходы")

    if not expense_chart and not income_chart:
        return ""

    return f"""
        <div class="charts-row">
            {expense_chart}
            {income_chart}
        </div>
    """


def _get_report_title(period_name: str) -> str:
    """Dynamic report title based on the period string.

    Examples:
    - "2025 год" -> "Отчет за 2025 год"
    - "Январь 2026" -> "Отчет за январь 2026"
    """
    period_lc = (period_name or "").strip().lower()
    if not period_lc:
        return "Отчет"
    return f"Отчет за {period_lc}"


def _get_pie_interaction_script() -> str:
    """Inline JS: bidirectional hover between pie segments and legend items."""
    return r"""
(() => {
  const containers = document.querySelectorAll('.pie-chart-container');
  containers.forEach((container) => {
    const slices = Array.from(container.querySelectorAll('.pie-segment[data-idx]'));
    const items = Array.from(container.querySelectorAll('.legend-item[data-idx]'));
    const labels = Array.from(container.querySelectorAll('.legend-item[data-idx] .legend-label'));

    const clear = () => {
      slices.forEach((s) => s.classList.remove('is-highlighted', 'is-dimmed'));
      items.forEach((i) => i.classList.remove('is-highlighted', 'is-dimmed'));
    };

    const highlight = (idx) => {
      slices.forEach((s) => s.classList.add('is-dimmed'));
      items.forEach((i) => i.classList.add('is-dimmed'));

      const targetSlice = container.querySelector(`.pie-segment[data-idx="${idx}"]`);
      if (targetSlice) {
        targetSlice.classList.remove('is-dimmed');
        targetSlice.classList.add('is-highlighted');
      }

      const targetItem = container.querySelector(`.legend-item[data-idx="${idx}"]`);
      if (targetItem) {
        targetItem.classList.remove('is-dimmed');
        targetItem.classList.add('is-highlighted');
      }
    };

    // Legend item hover
    labels.forEach((label) => {
      const item = label.closest('.legend-item[data-idx]');
      if (!item) return;
      const idx = item.getAttribute('data-idx');
      if (idx == null) return;
      label.addEventListener('mouseenter', () => highlight(idx));
      label.addEventListener('mouseleave', clear);
    });

    // Pie segment hover (NEW)
    slices.forEach((slice) => {
      const idx = slice.getAttribute('data-idx');
      if (idx == null) return;
      slice.addEventListener('mouseenter', () => highlight(idx));
      slice.addEventListener('mouseleave', clear);
    });

    container.addEventListener('mouseleave', clear);
  });
})();
""".strip()


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert HSL to hex color (#RRGGBB)."""
    h = h % 360.0
    s = 0.0 if s < 0 else 1.0 if s > 1 else s
    l = 0.0 if l < 0 else 1.0 if l > 1 else l

    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs(((h / 60.0) % 2) - 1))
    m = l - c / 2

    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    R = round((r + m) * 255)
    G = round((g + m) * 255)
    B = round((b + m) * 255)
    return f"#{R:02X}{G:02X}{B:02X}"


def _spread_colors(colors: List[str]) -> List[str]:
    """Reorder colors to maximize adjacent contrast (helps pie readability)."""
    n = len(colors)
    if n <= 2:
        return colors
    left = 0
    right = (n + 1) // 2
    out: List[str] = []
    while left < (n + 1) // 2 or right < n:
        if left < (n + 1) // 2:
            out.append(colors[left])
            left += 1
        if right < n:
            out.append(colors[right])
            right += 1
    return out[:n]


def _interpolate_hex_color(start_hex: str, end_hex: str, t: float) -> str:
    """Linear interpolate between two hex colors (#RRGGBB)."""
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    s = start_hex.lstrip("#")
    e = end_hex.lstrip("#")
    sr, sg, sb = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    er, eg, eb = int(e[0:2], 16), int(e[2:4], 16), int(e[4:6], 16)
    r = round(sr + (er - sr) * t)
    g = round(sg + (eg - sg) * t)
    b = round(sb + (eb - sb) * t)
    return f"#{r:02X}{g:02X}{b:02X}"


def _get_pie_palette(kind: str, n: int) -> List[str]:
    """Build a high-contrast palette for income/expense pie segments."""
    if n <= 0:
        return []

    # Expense: fixed contrasting (muted) colors
    expense_base = [
        "#E57373",  # soft red
        "#FFB74D",  # orange
        "#9575CD",  # purple
        "#4FC3F7",  # light blue
        "#81C784",  # green
        "#F06292",  # pink
        "#FFD54F",  # yellow
        "#64B5F6",  # blue
        "#AED581",  # light green
        "#FF8A65",  # coral
    ]

    # Income: green-centric but still distinct
    income_base = [
        "#81C784",  # primary green
        "#66BB6A",  # darker green
        "#4DB6AC",  # teal
        "#26A69A",  # sea
        "#9CCC65",  # lime
        "#8BC34A",  # green-ish
        "#80CBC4",  # soft teal
        "#A5D6A7",  # soft green
        "#C5E1A5",  # pale lime
        "#43A047",  # deep green
    ]

    base = expense_base if kind == "expense" else income_base
    colors = base[: min(n, len(base))].copy()

    # If more categories than predefined colors: generate additional muted distinct colors.
    if n > len(colors):
        extra_needed = n - len(colors)
        for i in range(extra_needed):
            # Golden-angle step for maximum separation of hues.
            h = (i * 137.508) % 360.0
            colors.append(_hsl_to_hex(h, 0.52, 0.62))

    return _spread_colors(colors[:n])


def _create_chart_section(categories: List[Dict], max_amount: Decimal, title: str) -> str:
    """Create chart section with SVG pie visualization + legend."""
    if not categories:
        return ""

    kind_class = ""
    if title.strip().lower() == "доходы":
        kind_class = "chart--income"
    elif title.strip().lower() == "расходы":
        kind_class = "chart--expense"
    
    kind = "income" if "income" in kind_class else "expense" if "expense" in kind_class else "expense"
    colors = _get_pie_palette(kind, len(categories))

    # Build pie segments (normalized so total = 100)
    segments_html = ""
    legend_html = ""

    raw_pcts: List[float] = []
    for cat in categories:
        pct = float(cat.get("percentage", 0.0))
        if pct < 0:
            pct = 0.0
        raw_pcts.append(pct)

    total_pct = sum(raw_pcts)
    if total_pct <= 0:
        # fallback: compute from amounts if available
        amounts = [float(cat.get("amount", 0) or 0) for cat in categories]
        total_amount = sum(amounts)
        raw_pcts = [(a / total_amount * 100.0) if total_amount > 0 else 0.0 for a in amounts]
        total_pct = sum(raw_pcts)

    norm_pcts: List[float] = []
    if total_pct > 0:
        norm_pcts = [(p / total_pct) * 100.0 for p in raw_pcts]
    else:
        norm_pcts = [0.0 for _ in raw_pcts]

    # Force last segment to close the circle using the SAME rounding as in SVG (2 decimals)
    if norm_pcts:
        running_rounded = 0.0
        for i in range(len(norm_pcts) - 1):
            v = max(0.0, min(100.0, norm_pcts[i]))
            v = round(v, 2)
            norm_pcts[i] = v
            running_rounded += v
        norm_pcts[-1] = max(0.0, min(100.0, round(100.0 - running_rounded, 2)))

    # Donut geometry (must fit into viewBox 200x200: r + stroke_width/2 <= 100)
    ring_r = 60.0
    ring_stroke = 40.0
    hole_outline_r = ring_r - ring_stroke / 2.0  # outline should match inner black circle edge

    cumulative_pct = 0.0

    for idx, cat in enumerate(categories):
        amount = cat["amount"]
        pct = norm_pcts[idx] if idx < len(norm_pcts) else 0.0

        color = colors[idx] if idx < len(colors) else (COLOR_INCOME_BAR_FROM if kind == "income" else COLOR_EXPENSE_BAR_FROM)
        rotation = -90.0 + cumulative_pct * 3.6
        # Geometry note: keep the whole ring inside viewBox 200x200.
        # Condition: r + stroke_width/2 <= 100.
        segments_html += f"""
            <circle class="pie-segment"
                    r="{ring_r:.0f}" cx="0" cy="0"
                    fill="transparent"
                    stroke="{color}"
                    stroke-width="{ring_stroke:.0f}"
                    pathLength="100"
                    stroke-dasharray="{pct:.2f} 100"
                    transform="rotate({rotation:.2f})"
                    data-idx="{idx}" />
        """
        legend_html += f"""
            <div class="legend-item" data-idx="{idx}">
                <span class="legend-color" style="background: {color}"></span>
                <span class="legend-label">{cat['category_name']} ({amount:,.0f} ₽, {pct:.1f}%)</span>
            </div>
        """
        cumulative_pct += pct

    # One continuous inner outline (instead of per-segment separators) — matches the black hole edge
    inner_outline_html = f'''
        <circle class="pie-separator"
                r="{hole_outline_r:.0f}" cx="0" cy="0"
                fill="transparent"
                stroke="#fff"
                stroke-width="1" />
    '''

    return f"""
        <div class="chart {kind_class}">
            <div class="chart-title">{title}</div>
            <div class="pie-chart-container">
                <svg class="pie-chart" viewBox="0 0 200 200" width="200" height="200" aria-hidden="true">
                    <g transform="translate(100 100)">
                        {segments_html}
                        {inner_outline_html}
                    </g>
                </svg>
                <div class="pie-legend">
                    {legend_html}
                </div>
            </div>
        </div>
    """


def _create_detailed_categories(categories: List[Dict], kind: str) -> str:
    """Create detailed categories section."""
    if not categories:
        return "<p>Нет операций за этот период</p>"
    
    grid_kind = "category-grid--income" if kind == "income" else "category-grid--expense"
    html = f'<div class="category-grid {grid_kind}">'
    
    for cat in categories:
        html += f"""
            <div class="category-detail">
                <div class="category-header">
                    {cat['category_name']}
                </div>
                <div class="category-amount">
                    Сумма: <strong>{cat['amount']:,.0f} ₽</strong>
                </div>
                <div class="category-percentage">
                    {cat['percentage']:.1f}% от общих {('расходов' if kind == 'expense' else 'доходов')}
                    ({cat['count']} {_get_operation_word(cat['count'], kind)})
                </div>
        """
        
        # Add individual items if available
        expenses = cat.get('expenses', [])
        if expenses:
            list_title = "Детализация доходов:" if kind == "income" else "Детализация расходов:"
            html += f"""
                <div class="expenses-list">
                    <div class="expenses-list-title">{list_title}</div>
            """
            
            for expense in expenses:
                date_str = expense['date'].strftime('%d.%m.%Y')
                description = expense.get('description')
                # Replace None or empty string with dash
                if not description:
                    description = '—'
                amount = expense['amount']
                
                html += f"""
                    <div class="expense-item">
                        <span class="expense-date">{date_str}</span>
                        <span class="expense-description">{description}</span>
                        <span class="expense-amount">{amount:,.0f} ₽</span>
                    </div>
                """
            
            html += """
                </div>
            """
        
        html += """
            </div>
        """
    
    html += "</div>"
    return html


def _get_operation_word(count: int, kind: str) -> str:
    """Get correct Russian word form for income/expense based on count.
    
    Args:
        count: Number of expenses
        
    Returns:
        Correct word form
    """
    if kind == "income":
        if count % 10 == 1 and count % 100 != 11:
            return "поступление"
        if count % 10 in [2, 3, 4] and count % 100 not in [12, 13, 14]:
            return "поступления"
        return "поступлений"
    if count % 10 == 1 and count % 100 != 11:
        return "списание"
    elif count % 10 in [2, 3, 4] and count % 100 not in [12, 13, 14]:
        return "списания"
    else:
        return "списаний"


async def export_monthly_report(
    family_name: str,
    period_name: str,
    stats: Dict,
    budget: Optional[Decimal] = None
) -> BytesIO:
    """Export monthly report as HTML.
    
    Args:
        family_name: Name of the family
        period_name: Period name
        stats: Statistics data
        budget: Optional budget amount
        
    Returns:
        BytesIO with HTML content
    """
    return generate_html_report(family_name, period_name, stats, budget, "monthly")


async def export_yearly_report(
    family_name: str,
    year: int,
    stats: Dict
) -> BytesIO:
    """Export yearly report as HTML.
    
    Args:
        family_name: Name of the family
        year: Year for the report
        stats: Statistics data
        
    Returns:
        BytesIO with HTML content
    """
    period_name = f"{year} год"
    return generate_html_report(family_name, period_name, stats, None, "yearly")


def generate_report_filename(family_name: str, period_name: str, is_personal: bool = False) -> str:
    """Generate filename for report.
    
    Args:
        family_name: Name of the family
        period_name: Period name
        is_personal: Whether this is personal report
        
    Returns:
        Formatted filename string
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Replace spaces and special characters
    safe_name = "".join(c for c in family_name if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_name = safe_name.replace(' ', '_')
    
    safe_period = "".join(c for c in period_name if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_period = safe_period.replace(' ', '_')
    
    prefix = "my" if is_personal else "family"
    
    return f"{prefix}_{safe_name}_{safe_period}_{timestamp}.html"

