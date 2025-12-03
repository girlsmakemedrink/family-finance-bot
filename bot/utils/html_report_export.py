"""HTML report generation for expenses."""

import logging
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Color definitions
COLOR_ORANGE = "#FF6633"
COLOR_DARK_BLUE = "#2C3E50"
COLOR_LIGHT_GRAY = "#F5F5F5"
COLOR_WHITE = "#FFFFFF"
COLOR_BLACK = "#000000"
COLOR_BORDER = "#DDDDDD"


def generate_html_report(
    family_name: str,
    period_name: str,
    stats: Dict,
    budget: Optional[Decimal] = None,
    report_type: str = "monthly"
) -> BytesIO:
    """Generate HTML report for expenses.
    
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
    
    total = stats.get('total', Decimal('0'))
    categories = stats.get('by_category', [])
    
    # Calculate statistics
    remaining = budget - total if budget else None
    percentage = (total / budget * 100) if budget and budget > 0 else 0
    savings_percentage = ((budget - total) / budget * 100) if budget and budget > 0 else 0
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{'Месячный' if report_type == 'monthly' else 'Годовой'} бюджет - {family_name}</title>
    <style>
        {_get_css_styles()}
    </style>
</head>
<body>
    <div class="container">
        <h1 class="main-title">{'Месячный' if report_type == 'monthly' else 'Годовой'} бюджет</h1>
        
        {_create_budget_info(budget) if budget else ''}
        
        <div class="info-section">
            <p><strong>Семья:</strong> {family_name}</p>
            <p><strong>Период:</strong> {period_name}</p>
            <p class="total-amount"><strong>Общая сумма расходов:</strong> {total:,.0f} ₽</p>
        </div>
        
        {_create_statistics_section(total, budget, remaining, savings_percentage) if budget else ''}
        
        {_create_chart_section(categories, total)}
        
        <div class="section">
            <h2 class="section-title">Детальные расходы по категориям</h2>
            {_create_detailed_categories(categories)}
        </div>
        
        <div class="footer">
            <p>Отчет создан {datetime.now().strftime('%d.%m.%Y в %H:%M')}</p>
            <p>Family Finance Bot</p>
        </div>
    </div>
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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: {COLOR_BLACK};
            background: {COLOR_LIGHT_GRAY};
            padding: 20px;
        }}
        
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: {COLOR_WHITE};
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .main-title {{
            color: {COLOR_ORANGE};
            font-size: 32px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid {COLOR_ORANGE};
        }}
        
        .budget-info {{
            text-align: right;
            font-size: 18px;
            color: {COLOR_DARK_BLUE};
            margin-bottom: 20px;
            padding: 15px;
            background: {COLOR_LIGHT_GRAY};
            border-radius: 5px;
        }}
        
        .info-section {{
            margin: 30px 0;
            padding: 20px;
            background: {COLOR_LIGHT_GRAY};
            border-radius: 5px;
        }}
        
        .info-section p {{
            margin: 10px 0;
            font-size: 16px;
        }}
        
        .total-amount {{
            font-size: 20px;
            color: {COLOR_ORANGE};
            margin-top: 15px;
            padding-top: 15px;
            border-top: 2px solid {COLOR_BORDER};
        }}
        
        .statistics {{
            margin: 20px 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
        }}
        
        .stat-row {{
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 10px;
            background: rgba(255,255,255,0.1);
            border-radius: 5px;
        }}
        
        .section {{
            margin: 40px 0;
        }}
        
        .section-title {{
            color: {COLOR_ORANGE};
            font-size: 24px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid {COLOR_ORANGE};
        }}
        
        .chart {{
            margin: 20px 0;
            padding: 20px;
            background: {COLOR_LIGHT_GRAY};
            border-radius: 5px;
        }}
        
        .chart-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            color: {COLOR_DARK_BLUE};
        }}
        
        .chart-bar {{
            margin: 15px 0;
        }}
        
        .chart-label {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            font-size: 14px;
        }}
        
        .chart-bar-container {{
            width: 100%;
            height: 30px;
            background: {COLOR_WHITE};
            border-radius: 15px;
            overflow: hidden;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .chart-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, {COLOR_ORANGE} 0%, #FF8C66 100%);
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 10px;
            color: white;
            font-weight: bold;
            font-size: 12px;
            transition: width 0.3s ease;
        }}
        
        .expenses-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        
        .expenses-table th {{
            background: {COLOR_DARK_BLUE};
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        
        .expenses-table td {{
            padding: 12px;
            border-bottom: 1px solid {COLOR_BORDER};
        }}
        
        .expenses-table tr:hover {{
            background: {COLOR_LIGHT_GRAY};
        }}
        
        .category-detail {{
            margin: 25px 0;
            padding: 20px;
            border-left: 4px solid {COLOR_ORANGE};
            background: {COLOR_LIGHT_GRAY};
            border-radius: 5px;
        }}
        
        .category-header {{
            font-size: 18px;
            font-weight: bold;
            color: {COLOR_DARK_BLUE};
            margin-bottom: 10px;
        }}
        
        .category-amount {{
            font-size: 16px;
            color: {COLOR_ORANGE};
            margin-bottom: 5px;
        }}
        
        .category-percentage {{
            font-size: 14px;
            color: #666;
        }}
        
        .expenses-list {{
            margin-top: 15px;
            border-top: 1px solid {COLOR_BORDER};
            padding-top: 15px;
        }}
        
        .expenses-list-title {{
            font-size: 14px;
            font-weight: bold;
            color: #666;
            margin-bottom: 10px;
        }}
        
        .expense-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            margin: 5px 0;
            background: {COLOR_WHITE};
            border-radius: 3px;
            border-left: 3px solid {COLOR_ORANGE};
        }}
        
        .expense-date {{
            font-size: 13px;
            color: #666;
            min-width: 90px;
        }}
        
        .expense-description {{
            flex: 1;
            font-size: 14px;
            color: {COLOR_BLACK};
            margin: 0 15px;
        }}
        
        .expense-amount {{
            font-size: 14px;
            font-weight: bold;
            color: {COLOR_ORANGE};
            min-width: 100px;
            text-align: right;
        }}
        
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid {COLOR_BORDER};
            text-align: center;
            color: #666;
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
            .container {{
                padding: 20px;
            }}
            .main-title {{
                font-size: 24px;
            }}
            .section-title {{
                font-size: 20px;
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


def _create_chart_section(categories: List[Dict], max_amount: Decimal) -> str:
    """Create chart section with bar visualization."""
    if not categories:
        return ""
    
    html = """
        <div class="section">
            <div class="chart">
                <div class="chart-title">Расходы</div>
    """
    
    for cat in categories:
        amount = cat['amount']
        percentage = cat['percentage']
        icon = cat['category_icon']
        name = cat['category_name']
        
        # Calculate bar width
        width = (amount / max_amount * 100) if max_amount > 0 else 0
        
        html += f"""
                <div class="chart-bar">
                    <div class="chart-label">
                        <span>{icon} {name}</span>
                        <span>{amount:,.0f} ₽ ({percentage:.1f}%)</span>
                    </div>
                    <div class="chart-bar-container">
                        <div class="chart-bar-fill" style="width: {width}%;">
                            {percentage:.1f}%
                        </div>
                    </div>
                </div>
        """
    
    html += """
            </div>
        </div>
    """
    
    return html


def _create_detailed_categories(categories: List[Dict]) -> str:
    """Create detailed categories section."""
    if not categories:
        return "<p>Нет расходов за этот период</p>"
    
    html = ""
    
    for cat in categories:
        html += f"""
            <div class="category-detail">
                <div class="category-header">
                    {cat['category_icon']} {cat['category_name']}
                </div>
                <div class="category-amount">
                    Сумма: {cat['amount']:,.0f} ₽
                </div>
                <div class="category-percentage">
                    {cat['percentage']:.1f}% от общих расходов ({cat['count']} {_get_expense_word(cat['count'])})
                </div>
        """
        
        # Add individual expenses if available
        expenses = cat.get('expenses', [])
        if expenses:
            html += """
                <div class="expenses-list">
                    <div class="expenses-list-title">Детализация расходов:</div>
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
    
    return html


def _get_expense_word(count: int) -> str:
    """Get correct Russian word form for 'expense' based on count.
    
    Args:
        count: Number of expenses
        
    Returns:
        Correct word form
    """
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

