"""Read-only connection to the legacy Access/MySQL trading database (`bpol-trd`).

Credentials come from BP Settings (Old System Import section, password stored
encrypted) and fall back to the LEGACY_DB_* environment variables so the
one-off `bench execute` scripts keep working on a site whose settings are
empty. Never hardcode legacy credentials in source.

Only SELECTs are ever issued against the legacy server: during the migration
week it is still the system of record the client's staff are typing into.
"""

import os

import frappe
from frappe import _

DEFAULT_DATABASE = "bpol-trd"
DEFAULT_PORT = 3306


def get_legacy_config():
	settings = frappe.get_single("BP Settings")
	password = None
	if settings.get("legacy_db_password"):
		password = settings.get_password("legacy_db_password", raise_exception=False)

	return {
		"host": settings.get("legacy_db_host") or os.environ.get("LEGACY_DB_HOST"),
		"port": settings.get("legacy_db_port") or int(os.environ.get("LEGACY_DB_PORT") or DEFAULT_PORT),
		"user": settings.get("legacy_db_user") or os.environ.get("LEGACY_DB_USER"),
		"password": password or os.environ.get("LEGACY_DB_PASSWORD"),
		"database": settings.get("legacy_db_name") or os.environ.get("LEGACY_DB_NAME") or DEFAULT_DATABASE,
	}


def get_legacy_connection():
	import pymysql

	config = get_legacy_config()
	if not (config["host"] and config["user"] and config["password"]):
		frappe.throw(
			_(
				"Old system connection is not configured. Fill in Host, User and Password in "
				"BP Settings (Old System Import section)."
			)
		)

	return pymysql.connect(
		host=config["host"],
		port=int(config["port"]),
		user=config["user"],
		password=config["password"],
		database=config["database"],
		# The legacy server is MariaDB 5.1 -- utf8mb4 didn't exist yet there,
		# so pymysql's default charset fails with "Unknown character set:
		# 'utf8mb4'". Plain "utf8" is what that server actually speaks.
		charset="utf8",
		connect_timeout=10,
		read_timeout=300,
		cursorclass=pymysql.cursors.DictCursor,
	)


def fetch_all(conn, sql, params=None):
	with conn.cursor() as cursor:
		cursor.execute(sql, params or ())
		return cursor.fetchall()


@frappe.whitelist()
def test_legacy_connection():
	frappe.only_for(("System Manager", "Accounts Manager"))
	conn = get_legacy_connection()
	try:
		version = fetch_all(conn, "SELECT VERSION() AS v")[0]["v"]
		last_do = fetch_all(conn, "SELECT MAX(DODatesx) AS d FROM deliorde")[0]["d"]
		last_rec = fetch_all(conn, "SELECT MAX(RecDOrDt) AS d FROM pcrecdor")[0]["d"]
	finally:
		conn.close()

	return {
		"version": version,
		"last_do_date": str(last_do) if last_do else None,
		"last_receiving_date": str(last_rec.date()) if last_rec else None,
	}
