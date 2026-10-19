"""Split invoice lines over 9.5 x 5.5 in continuous-form pages (Sales Invoice
and Delivery Order prints, Bry 2026-10-17).

The legacy Access print repeated the full header on every half page and put
the totals and signatures after the last line. Chrome does not repeat a table
header that tall, so the template draws one sheet per page itself and asks
`bp_paginate` which lines go on which sheet.

Heights are estimates in CSS px: each line row is `row_pad_px` plus
`line_px` per text line of its description (an HTML description counts its
<p>/<br> parts, a plain one its newlines; every part wraps after
`chars_per_line` characters). The template passes the space left for lines on a
full page (`page_px`) and on the last page, which also holds the totals and
signatures (`last_page_px`). An underestimate only spills a line onto an extra
sheet; nothing is cut.

Client request (Bry 2026-10-17): every line prints on one row. `bp_item_line`
joins the description parts (item name, then the legacy brand/code line) and
drops the legacy placeholders ("====", "- -"); the CSS cuts what does not fit.
With `one_line=True` bp_paginate counts every row as a single text line.

Payment Note (A4) builds its own line dicts in Jinja and gives each one its
height in px as `bp_px`; bp_paginate then uses that height as is.

Registered as Jinja methods in hooks.py:
	{% set pages = bp_paginate(doc.items, page_px=285, last_page_px=130, one_line=True) %}
	{{ bp_item_line(row.description or row.item_name) }}
"""

import math
import re

_PART_BREAK = re.compile(r"<br\s*/?>|</p>|</div>|</li>|\n", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_PLACEHOLDER = re.compile(r"^[-=]+$")


def _parts(text):
	for part in _PART_BREAK.split(text or ""):
		part = _TAG.sub("", part).replace("&nbsp;", " ").strip()
		if part:
			yield part


def bp_item_line(text):
	"""Description on one line: its parts joined with a space, without the legacy
	placeholder words made only of "-" or "=" ("==== A-06" -> "A-06", "- -" -> "")."""
	words = [w for part in _parts(text) for w in part.split() if not _PLACEHOLDER.match(w)]
	return " ".join(words)


def description_lines(text, chars_per_line):
	"""Printed lines of a description: one per part, wrapped at chars_per_line."""
	lines = sum(max(1, math.ceil(len(part) / chars_per_line)) for part in _parts(text))
	return max(lines, 1)


def row_height(row, chars_per_line, line_px, row_pad_px, one_line=False):
	# A row that knows its own height (Payment Note lines built in Jinja) passes it as bp_px.
	if row.get("bp_px"):
		return row["bp_px"]
	if one_line:
		return row_pad_px + line_px
	text = row.get("description") or row.get("item_name") or ""
	return row_pad_px + line_px * description_lines(text, chars_per_line)


def bp_paginate(
	items, chars_per_line=40, page_px=290, last_page_px=125, line_px=14.3, row_pad_px=5, one_line=False
):
	"""Pages of (number, row) pairs: full pages fit page_px, the last fits last_page_px."""
	rows = [
		(i, row, row_height(row, chars_per_line, line_px, row_pad_px, one_line))
		for i, row in enumerate(items or [], 1)
	]
	pages, current, used = [], [], 0
	for entry in rows:
		if current and used + entry[2] > page_px:
			pages.append(current)
			current, used = [], 0
		current.append(entry)
		used += entry[2]
	pages.append(current)

	# The last page also carries the totals: move its tail to a new page when they do not fit.
	last = pages[-1]
	if sum(e[2] for e in last) > last_page_px and len(last) > 1:
		tail, used = [], 0
		while last and (not tail or used + last[-1][2] <= last_page_px):
			used += last[-1][2]
			tail.insert(0, last.pop())
		if last:
			pages.append(tail)
		else:
			pages[-1] = tail
	# A single line too tall to share a page with the totals: totals get a sheet of their own.
	if sum(e[2] for e in pages[-1]) > last_page_px:
		pages.append([])
	return [[(i, row) for i, row, _ in page] for page in pages]
