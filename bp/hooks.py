app_name = "bp"
app_title = "BP"
app_publisher = "Hicom System"
app_description = "BP Custom App"
app_email = "h1com.syst3m@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "bp",
# 		"logo": "/assets/bp/logo.png",
# 		"title": "BP",
# 		"route": "/bp",
# 		"has_permission": "bp.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = ["/assets/bp/css/custom.css"]
# The storefront assets are website-only on purpose -- custom.css is shared with
# the desk (app_include_css above), so app-shell rules must not go in it.
# They are *.bundle.* so esbuild emits content-hashed filenames: assets are
# served with max-age=43200, and a plain path would leave returning visitors on
# a 12-hour-stale copy after every deploy. Run `bench build --app bp` on change.
web_include_css = ["/assets/bp/css/custom.css", "storefront.bundle.css"]
app_include_js = ["desk_overrides.bundle.js", "discount_utils.bundle.js"]
web_include_js = ["storefront.bundle.js"]
extend_bootinfo = "bp.boot.boot_session"

# Injects the mobile app shell (fixed header + bottom tab bar) into body_include
# on every website page. See bp/storefront/app_shell.py.
update_website_context = ["bp.storefront.app_shell.update_website_context"]

# Fixtures
# --------
fixtures = ["Client Script"]

# include js, css files in header of web template
# web_include_css = "/assets/bp/css/bp.css"
# web_include_js = "/assets/bp/js/bp.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "bp/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Stock Entry": "public/js/stock_entry.js",
	"Sales Invoice": "public/js/sales_invoice.js",
	"Sales Order": "public/js/sales_order.js",
	"Customer": "public/js/customer.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "bp/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "bp.utils.jinja_methods",
# 	"filters": "bp.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "bp.install.before_install"
# after_install = "bp.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "bp.uninstall.before_uninstall"
# after_uninstall = "bp.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "bp.utils.before_app_install"
# after_app_install = "bp.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "bp.utils.before_app_uninstall"
# after_app_uninstall = "bp.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bp.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

doc_events = {
	"Sales Invoice": {
		"validate": "bp.overrides.sales_invoice.validate",
		"before_validate": "bp.overrides.sales_invoice.recalculate_cascading_discount",
		"before_submit": "bp.overrides.sales_invoice.check_active_invoice_limit",
		"before_print": "bp.overrides.sales_invoice.before_print",
	},
	"Sales Order": {
		"before_validate": "bp.overrides.sales_order.recalculate_cascading_discount",
	},
	"Payment Entry": {
		"validate": "bp.overrides.payment_entry.validate",
	},
	"Customer": {
		"autoname": "bp.overrides.naming.autoname",
	},
	"Supplier": {
		"autoname": "bp.overrides.naming.autoname",
	},
}

# Naming Series Variables
# ------------------------
# Custom tokens usable inside naming series patterns (frappe.model.naming).
override_doctype_class = {
	"Sales Invoice": "bp.overrides.sales_invoice.BPSalesInvoice",
}

naming_series_variables = {
	"invoice_type_code": ["bp.overrides.purchase_invoice.get_invoice_type_code"],
	"warehouse_name_code": ["bp.overrides.sales_invoice.get_warehouse_name_code"],
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"bp.tasks.all"
# 	],
# 	"daily": [
# 		"bp.tasks.daily"
# 	],
# 	"hourly": [
# 		"bp.tasks.hourly"
# 	],
# 	"weekly": [
# 		"bp.tasks.weekly"
# 	],
# 	"monthly": [
# 		"bp.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "bp.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "bp.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "bp.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["bp.utils.before_request"]
# after_request = ["bp.utils.after_request"]

# Job Events
# ----------
# before_job = ["bp.utils.before_job"]
# after_job = ["bp.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"bp.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


