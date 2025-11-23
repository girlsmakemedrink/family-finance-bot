"""Export utilities for generating CSV files from expense data."""

import csv
import logging
from datetime import datetime
from io import BytesIO, StringIO
from typing import Dict, List

logger = logging.getLogger(__name__)


def format_csv_row(expense, include_user: bool = False) -> Dict[str, str]:
    """Format expense data as CSV row.
    
    Args:
        expense: Expense object from database
        include_user: Whether to include user name in the row
        
    Returns:
        Dictionary with formatted CSV fields
    """
    row = {
        'Дата': expense.date.strftime('%d.%m.%Y %H:%M'),
        'Категория': expense.category.name,
        'Сумма': f"{float(expense.amount):.2f}",
        'Описание': expense.description or '-'
    }
    
    if include_user:
        row['Участник'] = expense.user.name
    
    return row


def generate_csv(expenses: List, include_user: bool = False) -> BytesIO:
    """Generate CSV file from expenses list.
    
    Args:
        expenses: List of Expense objects
        include_user: Whether to include user column (for family expenses)
        
    Returns:
        BytesIO object containing CSV data
    """
    try:
        # Create StringIO for CSV writing
        string_buffer = StringIO()
        
        # Define fieldnames based on include_user flag
        if include_user:
            fieldnames = ['Дата', 'Категория', 'Сумма', 'Описание', 'Участник']
        else:
            fieldnames = ['Дата', 'Категория', 'Сумма', 'Описание']
        
        # Create CSV writer
        writer = csv.DictWriter(string_buffer, fieldnames=fieldnames)
        writer.writeheader()
        
        # Write expense rows
        for expense in expenses:
            row = format_csv_row(expense, include_user=include_user)
            writer.writerow(row)
        
        # Convert to BytesIO
        byte_buffer = BytesIO()
        byte_buffer.write(string_buffer.getvalue().encode('utf-8-sig'))  # UTF-8 with BOM for Excel compatibility
        byte_buffer.seek(0)
        
        logger.info(f"Generated CSV with {len(expenses)} expenses")
        
        return byte_buffer
        
    except Exception as e:
        logger.error(f"Error generating CSV: {e}")
        raise


def generate_csv_filename(family_name: str = None, is_personal: bool = False) -> str:
    """Generate filename for CSV export.
    
    Args:
        family_name: Name of the family (optional)
        is_personal: Whether this is personal expenses export
        
    Returns:
        Formatted filename string
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if is_personal:
        return f"my_expenses_{timestamp}.csv"
    elif family_name:
        # Replace spaces and special characters
        safe_name = "".join(c for c in family_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        return f"family_{safe_name}_{timestamp}.csv"
    else:
        return f"expenses_{timestamp}.csv"

