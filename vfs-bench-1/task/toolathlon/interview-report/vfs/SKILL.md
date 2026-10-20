---
name: workspace-commands
description: The shell commands and task tools available in this workspace.
---

# Available commands

Python (`python` or `python3`), Perl, JavaScript/Node.js, and TypeScript
runtimes are unavailable. Use the shell commands and task CLIs documented
below; do not probe for or attempt to install other runtimes. Use `word` for
Word documents.

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## word

Use `word <command> '<JSON arguments>'`. Run `word <command> --help` to get
more information.

| Command | Arguments | Description |
|---|---|---|
| `word create-document` | `{filename: str, title?: str = null, author?: str = null}` | Create a new Word document with optional metadata. |
| `word copy-document` | `{source_filename: str, destination_filename?: str = null}` | Create a copy of a Word document. |
| `word get-document-info` | `{filename: str}` | Get information about a Word document. |
| `word get-document-text` | `{filename: str}` | Extract all text from a Word document. |
| `word get-document-outline` | `{filename: str}` | Get the structure of a Word document. |
| `word list-available-documents` | `{directory?: str = "."}` | List all .docx files in the specified directory. |
| `word get-document-xml` | `{filename: str}` | Get the raw XML structure of a Word document. |
| `word insert-header-near-text` | `{filename: str, target_text?: str = null, header_title?: str = null, position?: str = "after", header_style?: str = "Heading 1", target_paragraph_index?: int = null}` | Insert a header (with specified style) before or after the target paragraph. Specify by text or paragraph index. Args: filename (str), target_text (str, optional), header_title (str), position ('before' or 'after'), header_style (str, default 'Heading 1'), target_paragraph_index (int, optional). |
| `word insert-line-or-paragraph-near-text` | `{filename: str, target_text?: str = null, line_text?: str = null, position?: str = "after", line_style?: str = null, target_paragraph_index?: int = null}` | Insert a new line or paragraph (with specified or matched style) before or after the target paragraph. Specify by text or paragraph index. Args: filename (str), target_text (str, optional), line_text (str), position ('before' or 'after'), line_style (str, optional), target_paragraph_index (int, optional). |
| `word insert-numbered-list-near-text` | `{filename: str, target_text?: str = null, list_items?: list[str] = null, position?: str = "after", target_paragraph_index?: int = null, bullet_type?: str = "bullet"}` | Insert a bulleted or numbered list before or after the target paragraph. Specify by text or paragraph index. Args: filename (str), target_text (str, optional), list_items (list of str), position ('before' or 'after'), target_paragraph_index (int, optional), bullet_type ('bullet' for bullets or 'number' for numbered lists, default: 'bullet'). |
| `word add-paragraph` | `{filename: str, text: str, style?: str = null, font_name?: str = null, font_size?: int = null, bold?: bool = null, italic?: bool = null, color?: str = null}` | Add a paragraph to a Word document with optional formatting. Args: filename: Path to Word document text: Paragraph text content style: Optional paragraph style name font_name: Font family (e.g., 'Helvetica', 'Times New Roman') font_size: Font size in points (e.g., 14, 36) bold: Make text bold italic: Make text italic color: Text color as hex RGB (e.g., '000000') |
| `word add-heading` | `{filename: str, text: str, level?: int = 1, font_name?: str = null, font_size?: int = null, bold?: bool = null, italic?: bool = null, border_bottom?: bool = false}` | Add a heading to a Word document with optional formatting. Args: filename: Path to Word document text: Heading text level: Heading level (1-9) font_name: Font family (e.g., 'Helvetica') font_size: Font size in points (e.g., 14) bold: Make heading bold italic: Make heading italic border_bottom: Add bottom border (for section headers) |
| `word add-picture` | `{filename: str, image_path: str, width?: number = null}` | Add an image to a Word document. |
| `word add-table` | `{filename: str, rows: int, cols: int, data?: list[list[str]] = null}` | Add a table to a Word document. |
| `word add-page-break` | `{filename: str}` | Add a page break to the document. |
| `word delete-paragraph` | `{filename: str, paragraph_index: int}` | Delete a paragraph from a document. |
| `word search-and-replace` | `{filename: str, find_text: str, replace_text: str}` | Search for text and replace all occurrences. |
| `word create-custom-style` | `{filename: str, style_name: str, bold?: bool = null, italic?: bool = null, font_size?: int = null, font_name?: str = null, color?: str = null, base_style?: str = null}` | Create a custom style in the document. |
| `word format-text` | `{filename: str, paragraph_index: int, start_pos: int, end_pos: int, bold?: bool = null, italic?: bool = null, underline?: bool = null, color?: str = null, font_size?: int = null, font_name?: str = null}` | Format a specific range of text within a paragraph. |
| `word format-table` | `{filename: str, table_index: int, has_header_row?: bool = null, border_style?: str = null, shading?: list[str] = null}` | Format a table with borders, shading, and structure. |
| `word set-table-cell-shading` | `{filename: str, table_index: int, row_index: int, col_index: int, fill_color: str, pattern?: str = "clear"}` | Apply shading/filling to a specific table cell. |
| `word apply-table-alternating-rows` | `{filename: str, table_index: int, color1?: str = "FFFFFF", color2?: str = "F2F2F2"}` | Apply alternating row colors to a table for better readability. |
| `word highlight-table-header` | `{filename: str, table_index: int, header_color?: str = "4472C4", text_color?: str = "FFFFFF"}` | Apply special highlighting to table header row. |
| `word merge-table-cells` | `{filename: str, table_index: int, start_row: int, start_col: int, end_row: int, end_col: int}` | Merge cells in a rectangular area of a table. |
| `word merge-table-cells-horizontal` | `{filename: str, table_index: int, row_index: int, start_col: int, end_col: int}` | Merge cells horizontally in a single row. |
| `word merge-table-cells-vertical` | `{filename: str, table_index: int, col_index: int, start_row: int, end_row: int}` | Merge cells vertically in a single column. |
| `word set-table-cell-alignment` | `{filename: str, table_index: int, row_index: int, col_index: int, horizontal?: str = "left", vertical?: str = "top"}` | Set text alignment for a specific table cell. |
| `word set-table-alignment-all` | `{filename: str, table_index: int, horizontal?: str = "left", vertical?: str = "top"}` | Set text alignment for all cells in a table. |
| `word protect-document` | `{filename: str, password: str}` | Add password protection to a Word document. |
| `word unprotect-document` | `{filename: str, password: str}` | Remove password protection from a Word document. |
| `word add-footnote-to-document` | `{filename: str, paragraph_index: int, footnote_text: str}` | Add a footnote to a specific paragraph in a Word document. |
| `word add-footnote-after-text` | `{filename: str, search_text: str, footnote_text: str, output_filename?: str = null}` | Add a footnote after specific text with proper superscript formatting. This enhanced function ensures footnotes display correctly as superscript. |
| `word add-footnote-before-text` | `{filename: str, search_text: str, footnote_text: str, output_filename?: str = null}` | Add a footnote before specific text with proper superscript formatting. This enhanced function ensures footnotes display correctly as superscript. |
| `word add-footnote-enhanced` | `{filename: str, paragraph_index: int, footnote_text: str, output_filename?: str = null}` | Enhanced footnote addition with guaranteed superscript formatting. Adds footnote at the end of a specific paragraph with proper style handling. |
| `word add-endnote-to-document` | `{filename: str, paragraph_index: int, endnote_text: str}` | Add an endnote to a specific paragraph in a Word document. |
| `word customize-footnote-style` | `{filename: str, numbering_format?: str = "1, 2, 3", start_number?: int = 1, font_name?: str = null, font_size?: int = null}` | Customize footnote numbering and formatting in a Word document. |
| `word delete-footnote-from-document` | `{filename: str, footnote_id?: int = null, search_text?: str = null, output_filename?: str = null}` | Delete a footnote from a Word document. Identify the footnote either by ID (1, 2, 3, etc.) or by searching for text near it. |
| `word add-footnote-robust` | `{filename: str, search_text?: str = null, paragraph_index?: int = null, footnote_text?: str = "", validate_location?: bool = true, auto_repair?: bool = false}` | Add footnote with robust validation and Word compliance. This is the production-ready version with comprehensive error handling. |
| `word validate-document-footnotes` | `{filename: str}` | Validate all footnotes in document for coherence and compliance. Returns detailed report on ID conflicts, orphaned content, missing styles, etc. |
| `word delete-footnote-robust` | `{filename: str, footnote_id?: int = null, search_text?: str = null, clean_orphans?: bool = true}` | Delete footnote with comprehensive cleanup and orphan removal. Ensures complete removal from document.xml, footnotes.xml, and relationships. |
| `word get-paragraph-text-from-document` | `{filename: str, paragraph_index: int}` | Get text from a specific paragraph in a Word document. |
| `word find-text-in-document` | `{filename: str, text_to_find: str, match_case?: bool = true, whole_word?: bool = false}` | Find occurrences of specific text in a Word document. |
| `word convert-to-pdf` | `{filename: str, output_filename?: str = null}` | Convert a Word document to PDF format. |
| `word replace-paragraph-block-below-header` | `{filename: str, header_text: str, new_paragraphs: list[str], detect_block_end_fn?: str = null}` | Reemplaza el bloque de párrafos debajo de un encabezado, evitando modificar TOC. |
| `word replace-block-between-manual-anchors` | `{filename: str, start_anchor_text: str, new_paragraphs: list[str], end_anchor_text?: str = null, match_fn?: str = null, new_paragraph_style?: str = null}` | Replace all content between start_anchor_text and end_anchor_text (or next logical header if not provided). |
| `word get-all-comments` | `{filename: str}` | Extract all comments from a Word document. |
| `word get-comments-by-author` | `{filename: str, author: str}` | Extract comments from a specific author in a Word document. |
| `word get-comments-for-paragraph` | `{filename: str, paragraph_index: int}` | Extract comments for a specific paragraph in a Word document. |
| `word set-table-column-width` | `{filename: str, table_index: int, col_index: int, width: number, width_type?: str = "points"}` | Set the width of a specific table column. |
| `word set-table-column-widths` | `{filename: str, table_index: int, widths: list[number], width_type?: str = "points"}` | Set the widths of multiple table columns. |
| `word set-table-width` | `{filename: str, table_index: int, width: number, width_type?: str = "points"}` | Set the overall width of a table. |
| `word auto-fit-table-columns` | `{filename: str, table_index: int}` | Set table columns to auto-fit based on content. |
| `word format-table-cell-text` | `{filename: str, table_index: int, row_index: int, col_index: int, text_content?: str = null, bold?: bool = null, italic?: bool = null, underline?: bool = null, color?: str = null, font_size?: int = null, font_name?: str = null}` | Format text within a specific table cell. |
| `word set-table-cell-padding` | `{filename: str, table_index: int, row_index: int, col_index: int, top?: number = null, bottom?: number = null, left?: number = null, right?: number = null, unit?: str = "points"}` | Set padding/margins for a specific table cell. |
