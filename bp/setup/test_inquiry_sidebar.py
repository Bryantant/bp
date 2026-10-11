import json

import frappe
from frappe.tests import IntegrationTestCase

from bp.bp.page.inquiry.inquiry import can_view_purchase, get_purchase
from bp.setup.inquiry_sidebar import INQUIRY_PAGE, ITEM_DOCTYPE, add_inquiry_link


def _sidebar_rows(sidebar):
	return frappe.get_all(
		ITEM_DOCTYPE,
		filters={"parent": sidebar, "parenttype": "Workspace Sidebar"},
		fields=["name", "idx", "link_to", "route_options"],
		order_by="idx asc",
	)


class TestInquirySidebar(IntegrationTestCase):
	def test_link_inserted_once_after_sales_invoice(self):
		add_inquiry_link("Selling", "sales", "Sales Invoice")
		add_inquiry_link("Selling", "sales", "Sales Invoice")

		rows = _sidebar_rows("Selling")
		inquiry = [r for r in rows if r.link_to == INQUIRY_PAGE]
		self.assertEqual(len(inquiry), 1)
		self.assertEqual(json.loads(inquiry[0].route_options), {"tab": "sales"})

		links = [r.link_to for r in rows]
		self.assertEqual(links.index(INQUIRY_PAGE), links.index("Sales Invoice") + 1)
		self.assertEqual([r.idx for r in rows], list(range(1, len(rows) + 1)))

	def test_existing_link_route_is_corrected(self):
		add_inquiry_link("Buying", "purchase", "Purchase Invoice")
		name = next(r.name for r in _sidebar_rows("Buying") if r.link_to == INQUIRY_PAGE)
		frappe.db.set_value(ITEM_DOCTYPE, name, "route_options", json.dumps({"tab": "balance"}))

		self.assertTrue(add_inquiry_link("Buying", "purchase", "Purchase Invoice"))
		self.assertEqual(
			json.loads(frappe.db.get_value(ITEM_DOCTYPE, name, "route_options")), {"tab": "purchase"}
		)


class TestInquiryPurchaseAccess(IntegrationTestCase):
	def setUp(self):
		self.settings = frappe.get_single("BP Settings")
		self.saved_roles = [r.role for r in self.settings.inquiry_purchase_roles]
		self.settings.set("inquiry_purchase_roles", [{"role": "Purchase User"}])
		self.settings.save(ignore_permissions=True)

		self.sales_user = self._user("inquiry-sales@example.com", ["Sales User"])
		self.purchase_user = self._user("inquiry-purchase@example.com", ["Purchase User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		self.settings.reload()
		self.settings.set("inquiry_purchase_roles", [{"role": r} for r in self.saved_roles])
		self.settings.save(ignore_permissions=True)

	def _user(self, email, roles):
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
			).insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)
		user.set("roles", [])
		user.add_roles(*roles)
		return email

	def test_listed_role_sees_purchase(self):
		self.assertTrue(can_view_purchase(self.purchase_user))

	def test_unlisted_role_is_refused(self):
		self.assertFalse(can_view_purchase(self.sales_user))
		frappe.set_user(self.sales_user)
		with self.assertRaises(frappe.PermissionError):
			get_purchase("{}")

	def test_system_manager_always_sees_purchase(self):
		self.assertTrue(can_view_purchase("Administrator"))

	def test_adding_sales_user_opens_the_tab(self):
		self.settings.append("inquiry_purchase_roles", {"role": "Sales User"})
		self.settings.save(ignore_permissions=True)
		self.assertTrue(can_view_purchase(self.sales_user))
