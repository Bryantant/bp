import frappe


def execute():
	# Try different grouping keys to identify duplicates
	for label, fields in [
		("item_code + price_list", "item_code, price_list"),
		("item_code + price_list + uom", "item_code, price_list, uom"),
		("item_code + price_list + uom + currency", "item_code, price_list, uom, currency"),
	]:
		rows_to_delete = frappe.db.sql(f"""
			SELECT COALESCE(SUM(cnt - 1), 0) as total FROM (
				SELECT COUNT(*) as cnt
				FROM `tabItem Price`
				GROUP BY {fields}
				HAVING COUNT(*) > 1
			) t
		""")[0][0]
		print(f"GROUP BY ({label}) → {int(rows_to_delete)} rows to delete")

	# Show a sample of duplicates by item_code + price_list
	samples = frappe.db.sql("""
		SELECT item_code, price_list, uom, currency, price_list_rate, COUNT(*) as cnt
		FROM `tabItem Price`
		GROUP BY item_code, price_list, uom, currency, price_list_rate
		HAVING COUNT(*) > 1
		ORDER BY cnt DESC
		LIMIT 10
	""", as_dict=True)

	print("\nSample duplicates (item_code + price_list + uom + currency + price_list_rate):")
	for r in samples:
		print(f"  {r.item_code} | {r.price_list} | {r.uom} | rate={r.price_list_rate} → {r.cnt} copies")
