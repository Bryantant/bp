from datetime import datetime

import frappe
from frappe.tests import IntegrationTestCase

from bp.utils.import_legacy_masters import (
	PRICE_LIST_BY_CUST_TYPE,
	_payment_terms,
	build_customer,
	build_item,
	build_supplier,
	item_description,
)


class FakeContext:
	"""Only what the builders read; no legacy connection, no inserts."""

	company = "PT. Bestindo Persada"
	default_warehouse = "A - BP"

	def __init__(self, sales_persons=None, uoms=None):
		self.sales_person_by_code = sales_persons or {}
		self.uoms_by_item = uoms or {}


def customer_row(**kw):
	row = {
		"CustCode": "A0700",
		"CustName": "TOKO ABC",
		"CustType": 2,
		"CashFlag": 0,
		"CredTerm": 30,
		"CredLimi": 5000000,
		"CustSinc": datetime(2026, 6, 1),
		"CustND": None,
		"SaleCode": "LEM",
		"BillAdd1": "Komp Nagoya Point Blok D No. 12",
		"BillAdd2": None,
		"BillCity": "Batam",
		"BillZipC": None,
		"BillTelp": "0778 4081611",
		"BillFaxx": None,
		"BillAttn": None,
		"ContPers": "BU YANI",
	}
	row.update(kw)
	return row


def item_row(**kw):
	row = {
		"ItemCode": "ABK-09999",
		"ItemDesc": "KIN DEZZERT MILK CHOCO ALMOND",
		"Size": "80 GR",
		"Model": "411292",
		"MaPartNo": "-",
		"GrouCode": "ABK",
		"BranCode": "TRS",
		"Unit1000": "PCS",
		"ActiveFlag": -1,
	}
	row.update(kw)
	return row


def supplier_row(**kw):
	row = {
		"SuppCode": "B0026",
		"SuppName": "SUPPLIER BARU PT",
		"CredTerm": 0,
		"SuppAdd1": "Jl. Raya No. 1",
		"SuppAdd2": None,
		"SuppCity": "Jakarta",
		"SuppZipC": None,
		"SuppTelp": "021 555 1234",
		"SuppFaxx": None,
		"SuppAttn": "PAK BUDI",
		"AcctAttn": None,
	}
	row.update(kw)
	return row


class IntegrationTestImportLegacyMasters(IntegrationTestCase):
	# -- customer ------------------------------------------------------------

	def test_price_list_follows_cust_type(self):
		ctx = FakeContext()
		self.assertEqual(build_customer(customer_row(CustType=1), ctx).default_price_list, "Retail")
		self.assertEqual(build_customer(customer_row(CustType=2), ctx).default_price_list, "User 1")
		self.assertEqual(PRICE_LIST_BY_CUST_TYPE, {1: "Retail", 2: "User 1"})

	def test_customer_keeps_legacy_code_as_name(self):
		for code in ("A0700", "-0001", "20004"):
			self.assertEqual(build_customer(customer_row(CustCode=code), FakeContext()).name, code)

	def test_initial_is_first_character_of_the_code(self):
		doc = build_customer(customer_row(CustCode="a0700"), FakeContext())
		self.assertEqual(doc.custom_cn_initial, "A")

	def test_credit_limit_row_only_when_legacy_has_one(self):
		ctx = FakeContext()
		self.assertEqual(len(build_customer(customer_row(), ctx).credit_limits), 1)
		self.assertEqual(build_customer(customer_row(), ctx).credit_limits[0].credit_limit, 5000000)
		self.assertEqual(build_customer(customer_row(CredLimi=0), ctx).credit_limits, [])

	def test_sales_person_fills_both_field_and_team(self):
		ctx = FakeContext(sales_persons={"LEM": "LEMON"})
		doc = build_customer(customer_row(), ctx)
		self.assertEqual(doc.bp_sales_person, "LEMON")
		self.assertEqual(len(doc.sales_team), 1)
		self.assertEqual(doc.sales_team[0].allocated_percentage, 100)

	def test_unknown_sales_code_leaves_customer_without_team(self):
		doc = build_customer(customer_row(SaleCode="ZZZ"), FakeContext(sales_persons={"LEM": "LEMON"}))
		self.assertIsNone(doc.bp_sales_person)
		self.assertEqual(doc.sales_team, [])

	# -- payment terms -------------------------------------------------------

	def test_payment_terms_blank_when_cred_term_is_zero(self):
		self.assertIsNone(_payment_terms(0))
		self.assertIsNone(_payment_terms(None))

	def test_payment_terms_uses_existing_template_only(self):
		# "30 Days" exists on this site; an absurd term has no template.
		self.assertEqual(_payment_terms(30), "30 Days")
		self.assertIsNone(_payment_terms(9999))

	# -- item ----------------------------------------------------------------

	def test_description_is_desc_plus_size_then_model(self):
		self.assertEqual(
			item_description(item_row()),
			"KIN DEZZERT MILK CHOCO ALMOND80 GR\n==== 411292",
		)

	def test_item_disabled_follows_active_flag(self):
		ctx = FakeContext()
		self.assertEqual(build_item(item_row(ActiveFlag=-1), ctx).disabled, 0)
		self.assertEqual(build_item(item_row(ActiveFlag=0), ctx).disabled, 1)

	def test_item_uoms_include_stock_uom_once(self):
		ctx = FakeContext(uoms={"ABK-09999": [{"uom": "CTN", "factor": 24}, {"uom": "PCS", "factor": 1}]})
		doc = build_item(item_row(), ctx)
		self.assertEqual([(u.uom, u.conversion_factor) for u in doc.uoms], [("CTN", 24.0), ("PCS", 1.0)])

	def test_stock_uom_row_added_when_legacy_has_none(self):
		doc = build_item(item_row(), FakeContext(uoms={"ABK-09999": [{"uom": "CTN", "factor": 24}]}))
		self.assertIn(("PCS", 1.0), [(u.uom, u.conversion_factor) for u in doc.uoms])

	def test_item_default_warehouse_row(self):
		doc = build_item(item_row(), FakeContext())
		self.assertEqual(doc.item_defaults[0].default_warehouse, "A - BP")
		self.assertEqual(doc.custom_old_item_code, "ABK-09999")
		self.assertEqual(doc.custom_external_item_code, "-")

	# -- supplier ------------------------------------------------------------

	def test_supplier_mapping(self):
		doc = build_supplier(supplier_row(), FakeContext())
		self.assertEqual(doc.name, "B0026")
		self.assertEqual(doc.custom_initial, "B")
		self.assertEqual(doc.country, "Indonesia")
		self.assertEqual(doc.supplier_type, "Company")
		self.assertIsNone(doc.payment_terms)
		self.assertIsNone(doc.supplier_group)

	# -- messy legacy phone data ----------------------------------------------

	def test_several_numbers_in_one_legacy_field_are_split(self):
		from bp.utils.import_legacy_masters import _first_phone, _split_phones

		self.assertEqual(
			_split_phones("085364024977/089629303152"), ["085364024977", "089629303152"]
		)
		self.assertEqual(_split_phones("426978 / 7100788/ 7100899"), ["426978", "7100788", "7100899"])
		self.assertEqual(_first_phone("08973508658 / 082363435530"), "08973508658")

	def test_notes_that_are_not_numbers_are_dropped(self):
		from bp.utils.import_legacy_masters import _first_phone, _split_phones

		self.assertEqual(_split_phones("- EXT: 269"), [])
		self.assertIsNone(_first_phone("-"))
		self.assertIsNone(_first_phone(None))

	# -- create-only guarantee ------------------------------------------------

	def test_dry_run_never_calls_the_committing_patch(self):
		"""seed_bp_naming_counters ends in frappe.db.commit(); calling it from a
		dry run would make the whole "nothing is written" promise a lie."""
		from bp.utils.import_legacy_masters import _Context, _reseed_naming_counters

		with self.assertRaises(RuntimeError):
			_reseed_naming_counters(_Context(dry_run=True))

	def test_existing_records_are_reported_not_changed(self):
		from bp.utils.import_legacy_masters import _Context, _import_customer

		existing = frappe.get_all("Customer", limit=1, pluck="name")
		if not existing:
			self.skipTest("no Customer on this site")
		code = existing[0]
		before = frappe.db.get_value("Customer", code, "customer_name")
		ctx = _Context(dry_run=True)
		ctx.sales_person_by_code = {}
		outcome = _import_customer(customer_row(CustCode=code, CustName="NAMA LAIN"), ctx)
		self.assertEqual(outcome, "unchanged")
		self.assertEqual(frappe.db.get_value("Customer", code, "customer_name"), before)
		self.assertTrue(any(d["field"] == "customer_name" for d in ctx.differences))
