"""Utility helpers for terminal output

This module provides a reusable table formatting function so other parts
of the project can print aligned tables to the terminal with consistent
column widths and optional truncation.

No emojis or non-ASCII symbols are used in strings to keep cross-platform
compatibility and avoid encoding issues.
"""

from typing import List, Sequence, Optional
import re


def _looks_like_number(s: str) -> bool:
    """Rudimentary check whether a string looks numeric (allows commas, dots, optional unit)."""
    if not s:
        return False
    s = s.strip()
    # allow things like "29.4", "1,234", "4.3 MB", "0.2 KB"
    # We treat trailing unit (KB, MB, GB) as still numeric-looking
    s = re.sub(r"\s*(KB|MB|GB|B)$", "", s, flags=re.IGNORECASE)
    s = s.replace(',', '')
    return bool(re.match(r"^-?\d+(?:\.\d+)?$", s))


def format_table(
    rows: Sequence[Sequence],
    headers: Optional[Sequence[str]] = None,
    padding: int = 2,
    align: Optional[Sequence[str]] = None,
    max_widths: Optional[Sequence[int]] = None,
    truncate: bool = True,
    wrap: Optional[Sequence[bool]] = None,
    header_separator: str = "-",
) -> str:
    """Format rows into an aligned table string.

    Args:
        rows: Sequence of rows, each row is a sequence of cell values (will be str()'d).
        headers: Optional sequence of header names. If provided, a header line and
                 a separator will be added at the top.
        padding: Number of spaces between columns.
        align: Optional list of 'left'|'right'|'center' or None for auto detection per column.
        max_widths: Optional sequence of maximum widths per column (columns beyond
                    that width will be truncated when `truncate` is True or wrapped when wrap is True).
        truncate: If True, cell text longer than column width is trimmed with an ellipsis.
        wrap: Optional list of booleans indicating which columns should wrap to multiple lines
              instead of truncating. Takes precedence over truncate for specified columns.
        header_separator: Character used to build the header separator line.

    Returns:
        A string containing the formatted table suitable for printing.
    """
    # Normalize rows to list of lists of strings
    rows = [list(map(lambda v: "" if v is None else str(v), row)) for row in rows]

    num_cols = 0
    if headers:
        num_cols = max(num_cols, len(headers))
    for r in rows:
        num_cols = max(num_cols, len(r))

    # Ensure all rows have same length
    for r in rows:
        if len(r) < num_cols:
            r.extend([""] * (num_cols - len(r)))

    header_list = list(headers) if headers is not None else None
    if header_list and len(header_list) < num_cols:
        header_list.extend([""] * (num_cols - len(header_list)))

    # Compute natural widths from data and headers
    col_widths: List[int] = [0] * num_cols
    for i in range(num_cols):
        maxw = 0
        if header_list:
            maxw = max(maxw, len(str(header_list[i])))
        for r in rows:
            maxw = max(maxw, len(r[i]))
        col_widths[i] = maxw

    # Apply max_widths if provided
    if max_widths:
        for i, mw in enumerate(max_widths):
            if mw is None:
                continue
            if i < len(col_widths) and mw > 0:
                col_widths[i] = min(col_widths[i], mw)

    # Decide alignment per column
    aligns: List[str] = []
    for i in range(num_cols):
        if align and i < len(align) and align[i] in ("left", "right", "center"):
            aligns.append(align[i])
        else:
            # Try auto-detect: right align if column looks like numbers
            col_vals = [r[i] for r in rows]
            if all(_looks_like_number(str(v)) for v in col_vals if v != ""):
                aligns.append("right")
            else:
                aligns.append("left")

    # Determine which columns should wrap
    wrap_cols: List[bool] = []
    for i in range(num_cols):
        if wrap and i < len(wrap) and wrap[i]:
            wrap_cols.append(True)
        else:
            wrap_cols.append(False)

    # Prepare formatter function for each column
    pad = ' ' * padding

    def _wrap_text(text: str, width: int) -> List[str]:
        """Wrap text to multiple lines if it exceeds width."""
        if len(text) <= width or width <= 0:
            return [text]
        
        lines = []
        while len(text) > width:
            # Try to break at a path separator or space
            break_at = width
            for sep in ['\\', '/', ' ', '-', '_']:
                last_sep = text[:width].rfind(sep)
                if last_sep > width // 2:  # Only break if separator is in latter half
                    break_at = last_sep + 1
                    break
            
            lines.append(text[:break_at])
            text = text[break_at:]
        
        if text:
            lines.append(text)
        
        return lines

    def _truncate(text: str, width: int) -> str:
        if len(text) <= width:
            return text
        if not truncate or width <= 0:
            return text[:width]
        if width <= 3:
            return text[:width]
        return text[: width - 3] + '...'

    def _format_cell(text: str, width: int, alignment: str) -> str:
        text = _truncate(text, width)
        if alignment == 'right':
            return text.rjust(width)
        elif alignment == 'center':
            return text.center(width)
        else:
            return text.ljust(width)

    lines: List[str] = []

    # Header line
    if header_list:
        header_cells = [_format_cell(str(header_list[i]), col_widths[i], 'left') for i in range(num_cols)]
        lines.append(pad.join(header_cells))
        sep_cells = [header_separator * col_widths[i] for i in range(num_cols)]
        lines.append(pad.join(sep_cells))

    # Data rows with wrapping support
    for r in rows:
        # Check if any cell needs wrapping
        wrapped_cells = []
        max_lines = 1
        
        for i in range(num_cols):
            if wrap_cols[i] and len(r[i]) > col_widths[i]:
                cell_lines = _wrap_text(r[i], col_widths[i])
                wrapped_cells.append(cell_lines)
                max_lines = max(max_lines, len(cell_lines))
            else:
                wrapped_cells.append([_format_cell(r[i], col_widths[i], aligns[i])])
        
        # Output each line of this row
        for line_idx in range(max_lines):
            row_parts = []
            for col_idx in range(num_cols):
                if line_idx < len(wrapped_cells[col_idx]):
                    cell_text = wrapped_cells[col_idx][line_idx]
                    # Format if not already formatted (wrapped cells aren't formatted yet)
                    if wrap_cols[col_idx]:
                        cell_text = _format_cell(cell_text, col_widths[col_idx], aligns[col_idx])
                    row_parts.append(cell_text)
                else:
                    # Empty cell for continuation lines
                    row_parts.append(' ' * col_widths[col_idx])
            
            lines.append(pad.join(row_parts))

    return '\n'.join(lines)


def print_table(*args, **kwargs) -> None:
    """Convenience wrapper that prints the result of `format_table`."""
    print(format_table(*args, **kwargs))


if __name__ == '__main__':
    # Quick demonstration for manual verification
    sample_rows = [
        (".venv/Lib/cli/__p...", "29.4 KB", "13.6 KB", "20 -27 05:44"),
        (".venv/Lib/site-packages/pip/_internal/cli/__p...", "1.9 KB", "1.1 KB", "2025-12-27 05:44"),
    ]
    headers = ["Path", "Size", "Compressed", "Modified"]
    print(format_table(sample_rows, headers=headers, padding=3))
