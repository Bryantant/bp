"""Role permission dialog on the User form (click a role name): hide DocTypes where the role only has Select.

Select alone lets the role pick the document in a link field; it grants no access to the document, and the
standard dialog lists hundreds of such rows (Batch, Sales Partner, Tax templates...), burying the real
permissions. get_perm_info is the standard method behind the dialog, replaced through
override_whitelisted_methods; it returns the rows sorted by number of rights (main documents first). Its view argument is the dialog's toggle
(bp_desk_overrides.bundle.js): only rows that can write (default), without Select-only rows, or standard.
Custom permission types of a DocType count as rights. Nothing else changes: the Role Permission Manager and
the stored permissions are untouched.
"""

import frappe
from frappe.core.doctype.user.user import get_perm_info as standard_get_perm_info
from frappe.permissions import get_doctype_ptype_map, std_rights

RIGHTS_BESIDES_SELECT = tuple(r for r in std_rights if r != "select")


WRITE_LEVEL_RIGHTS = ("write", "create", "delete", "submit", "cancel", "amend")
VIEWS = ("no_select", "standard", "write")


def _rights_count(perm, ptype_map):
	"""How many rights the row grants (Select not counted, custom permission types are)."""
	custom = ptype_map.get(perm.get("parent"), [])
	return sum(1 for r in (*RIGHTS_BESIDES_SELECT, *custom) if perm.get(r))


@frappe.whitelist()
def get_perm_info(role: str, view: str = "write"):
	"""Rows of the role permission dialog, the role's main documents first (most rights granted).

	view: "write" (default) keeps only rows that can change documents (Write, Create, Delete, Submit, Cancel or
	Amend); "no_select" leaves out rows whose only right is Select; "standard" keeps every row (Select-only rows
	come last). Ties go alphabetically by DocType, then permission level.
	"""
	view = view if view in VIEWS else "write"
	ptype_map = get_doctype_ptype_map()
	rows = standard_get_perm_info(role)
	if view == "no_select":
		rows = [perm for perm in rows if _rights_count(perm, ptype_map)]
	elif view == "write":
		rows = [perm for perm in rows if any(perm.get(r) for r in WRITE_LEVEL_RIGHTS)]
	return sorted(
		rows,
		key=lambda perm: (
			-_rights_count(perm, ptype_map),
			perm.get("parent") or "",
			perm.get("permlevel") or 0,
		),
	)
