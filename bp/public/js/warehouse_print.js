// Shared by the BP Warehouse Print list and form (HT-171). Loaded with
// frappe.require so it is only fetched where the warehouse queue is used.
frappe.provide("bp.warehouse_print");

bp.warehouse_print.print = function (name, done) {
	// Open the tab now, inside the click, so the browser does not block it as a
	// popup; point it at the PDF only after the server confirms the row is still
	// unprinted (a blocked reprint then shows as a normal message here).
	var tab = window.open("", "_blank");
	frappe
		.xcall("bp.warehouse_print.check_print", { name: name })
		.then(function () {
			var url = "/api/method/bp.warehouse_print.print_pdf?name=" + encodeURIComponent(name);
			if (tab) {
				tab.location = url;
			} else {
				window.open(url, "_blank");
			}
			// The PDF request marks the row Printed; refresh once it has had time to run.
			setTimeout(done, 3000);
		})
		.catch(function () {
			if (tab) tab.close();
			done();
		});
};

bp.warehouse_print.reset = function (name, done) {
	frappe.prompt(
		[{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 }],
		function (values) {
			frappe
				.xcall("bp.warehouse_print.reset", { name: name, reason: values.reason })
				.then(function () {
					frappe.show_alert({
						message: __("{0} can be printed once more.", [name]),
						indicator: "orange",
					});
					done();
				});
		},
		__("Reset Print"),
		__("Reset")
	);
};
