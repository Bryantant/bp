"""Reports a role can open, for the role permission dialog on the User form (bp_desk_overrides.bundle.js).

Frappe's dialog only lists DocType permissions. A report has two gates: its role list and Report permission
on its ref_doctype. The role list of a report is its own roles, unless a Custom Role exists for the report:
then the Custom Role replaces them (Report.is_permitted / get_custom_allowed_roles).
"""

import frappe


@frappe.whitelist()
def get_role_reports(role: str) -> list[dict]:
	frappe.only_for(("System Manager", "User Manager"))

	custom = {
		c.name: c.report
		for c in frappe.get_all("Custom Role", filters={"report": ["is", "set"]}, fields=["name", "report"])
	}
	has_custom = set(custom.values())
	listed = set()
	for row in frappe.get_all(
		"Has Role",
		filters={"role": role, "parenttype": ["in", ["Report", "Custom Role"]]},
		fields=["parent", "parenttype"],
	):
		if row.parenttype == "Custom Role" and row.parent in custom:
			listed.add(custom[row.parent])
		elif row.parenttype == "Report" and row.parent not in has_custom:
			listed.add(row.parent)
	if not listed:
		return []

	reports = frappe.get_all(
		"Report",
		filters={"name": ["in", list(listed)], "disabled": 0},
		fields=["name", "module", "ref_doctype", "report_type"],
		order_by="module asc, name asc",
	)
	can_report = {dt: _role_can_report(role, dt) for dt in {r.ref_doctype for r in reports if r.ref_doctype}}
	return [
		{
			"report": r.name,
			"module": r.module,
			"ref_doctype": r.ref_doctype,
			"report_type": r.report_type,
			"can_open": bool(r.ref_doctype and can_report.get(r.ref_doctype)),
		}
		for r in reports
	]


def _role_can_report(role: str, doctype: str) -> bool:
	"""Report right on level 0, from Custom DocPerm when the doctype has any, else from the standard DocPerm."""
	source = "Custom DocPerm" if frappe.db.exists("Custom DocPerm", {"parent": doctype}) else "DocPerm"
	return bool(frappe.db.exists(source, {"parent": doctype, "role": role, "permlevel": 0, "report": 1}))
