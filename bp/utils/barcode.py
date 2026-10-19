"""Code 128 barcode as an SVG data URI, for the Jinja print formats (HT-42).

The Sales Invoice and Delivery Order prints carry the invoice name as a Code 128
barcode, scanned back in on the Invoice Kembali form. Code 128 (not QR) because
the scanner is not chosen yet: a 1D USB scanner, a 2D scanner and a phone camera
all read it. Written here instead of adding python-barcode, which is not in the
bench env, so production needs no extra pip install.

Code set B (ASCII 32-126) for letters, set C (two digits per symbol) for runs
of digits, so SINV-A26100001 is about a quarter shorter. That matters on BP's
dot-matrix printers (continuous form): bars must be whole printer dots wide,
which pushes the module up to 1/60 inch and the barcode gets wide.

Registered as a Jinja method in hooks.py:
	<img class="bp-barcode" src="{{ code128_svg(doc.name) }}">
"""

import base64

# Bar/space widths (in modules) of Code 128 symbol values 0-106; 103-105 are the
# start codes A/B/C, 106 the stop pattern (with its final 2-module bar).
PATTERNS = (
	"212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
	"221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
	"221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
	"212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
	"231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
	"231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
	"314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
	"112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
	"111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
	"214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
	"114131", "311141", "411131", "211412", "211214", "211232", "2331112",
)
START_B = 104
START_C = 105
CODE_B = 100  # switch to set B, sent while in set C
CODE_C = 99  # switch to set C, sent while in set B
STOP = 106
QUIET = 10  # modules of white space on each side
DOT_MODULE_MM = 25.4 / 60  # 1/60 inch: 2, 3 and 6 dots at 120, 180 and 360 dpi


def _segments(value):
	"""Split into (set, text) parts: digit runs go to set C where that is shorter
	(at least 4 digits at the start or end, 6 in the middle, or all digits);
	an odd run leaves its first digit in set B."""
	parts, i, n = [], 0, len(value)
	while i < n:
		j = i
		while j < n and value[j].isdigit():
			j += 1
		run = j - i
		at_edge = i == 0 or j == n
		if run and (run == n or run >= (4 if at_edge else 6)):
			if run % 2:
				parts.append(["B", value[i]])
				i += 1
			parts.append(["C", value[i:j]])
			i = j
		else:
			k = max(j, i + 1)
			parts.append(["B", value[i:k]])
			i = k
	merged = []
	for code_set, text in parts:
		if merged and merged[-1][0] == code_set:
			merged[-1][1] += text
		else:
			merged.append([code_set, text])
	return merged


def code128_values(value):
	"""Symbol values for `value`: start, data (sets B and C), checksum, stop."""
	value = str(value or "")
	if not value:
		raise ValueError("Code 128: empty value")
	for ch in value:
		if ord(ch) < 32 or ord(ch) > 126:
			raise ValueError(f"Code 128 set B cannot encode {ch!r}")
	symbols = []
	for n, (code_set, text) in enumerate(_segments(value)):
		if n == 0:
			symbols.append(START_C if code_set == "C" else START_B)
		else:
			symbols.append(CODE_C if code_set == "C" else CODE_B)
		if code_set == "C":
			symbols += [int(text[k : k + 2]) for k in range(0, len(text), 2)]
		else:
			symbols += [ord(ch) - 32 for ch in text]
	checksum = (symbols[0] + sum(i * v for i, v in enumerate(symbols[1:], start=1))) % 103
	return [*symbols, checksum, STOP]


def code128_modules(value):
	"""Widths of the alternating bars and spaces (bar first), in modules."""
	return [int(w) for v in code128_values(value) for w in PATTERNS[v]]


def code128_svg(value, module_mm=0.26, height_mm=9):
	"""SVG data URI of `value` as Code 128, `module_mm` per narrowest bar
	(DOT_MODULE_MM for dot-matrix printers). Width = (11 x symbols + 2 + 2 x QUIET) modules."""
	widths = code128_modules(value)
	total = sum(widths) + 2 * QUIET
	rects = []
	x = QUIET
	for i, w in enumerate(widths):
		if i % 2 == 0:
			rects.append(f'<rect x="{x}" y="0" width="{w}" height="1"/>')
		x += w
	svg = (
		f'<svg xmlns="http://www.w3.org/2000/svg" width="{total * module_mm:.2f}mm" height="{height_mm}mm" '
		f'viewBox="0 0 {total} 1" preserveAspectRatio="none" shape-rendering="crispEdges">'
		f'<rect width="{total}" height="1" fill="#fff"/><g fill="#000">{"".join(rects)}</g></svg>'
	)
	return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
