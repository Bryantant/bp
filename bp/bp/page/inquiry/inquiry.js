frappe.pages['inquiry'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Inquiry'),
		single_column: true,
	});

	wrapper.inquiry = new bp.Inquiry(page);
};

// A sidebar link can open a given tab: route_options {"tab": "sales"}.
frappe.pages['inquiry'].on_page_show = function (wrapper) {
	const tab = frappe.route_options && frappe.route_options.tab;
	if (tab && wrapper.inquiry) {
		frappe.route_options = null;
		wrapper.inquiry.show_tab(tab);
	}
};

bp = window.bp || {};

bp.Inquiry = class Inquiry {
	constructor(page) {
		this.page = page;
		this.active_tab = 'balance';
		this.tables = {};
		this.tabs = [
			{ key: 'balance', label: __('Balance'), method: 'bp.bp.page.inquiry.inquiry.get_balance' },
			{ key: 'sales', label: __('Sales'), method: 'bp.bp.page.inquiry.inquiry.get_sales' },
			{ key: 'purchase', label: __('Purchase'), method: 'bp.bp.page.inquiry.inquiry.get_purchase' },
			{ key: 'price_list', label: __('Price List'), method: 'bp.bp.page.inquiry.inquiry.get_price_list' },
		];
		this.make_filters();
		this.make_tabs();
		this.page.set_primary_action(__('Search'), () => this.run_active_tab(), 'search');
		this.apply_context();
	}

	// Hide the Purchase tab for users not listed in BP Settings > Inquiry Purchase Roles.
	apply_context() {
		frappe.call({
			method: 'bp.bp.page.inquiry.inquiry.get_context',
			callback: (r) => {
				if ((r.message || {}).show_purchase) return;
				this.tabs = this.tabs.filter((t) => t.key !== 'purchase');
				this.$tabs.find('.nav-link[data-tab="purchase"]').closest('.nav-item').remove();
				if (this.active_tab === 'purchase') this.show_tab('balance');
			},
		});
	}

	show_tab(key) {
		const $link = this.$tabs.find(`.nav-link[data-tab="${key}"]`);
		// Tab not available for this user (Purchase hidden): stay where we are.
		if (!$link.length) return;
		this.$tabs.find('.nav-link').removeClass('active');
		$link.addClass('active');
		this.active_tab = key;
		this.$detail.hide().empty();
		this.$body.empty();
	}

	make_filters() {
		this.fields = {};
		this.fields.item_group = this.page.add_field({
			fieldtype: 'MultiSelectList', fieldname: 'item_group', label: __('Item Group'),
			get_data: (txt) => frappe.db.get_link_options('Item Group', txt),
		});
		this.fields.item = this.page.add_field({
			fieldtype: 'Link', fieldname: 'item', label: __('Item'), options: 'Item',
		});
		this.fields.description = this.page.add_field({
			fieldtype: 'Data', fieldname: 'description', label: __('Description'),
		});
		this.fields.from_date = this.page.add_field({
			fieldtype: 'Date', fieldname: 'from_date', label: __('From'),
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		});
		this.fields.to_date = this.page.add_field({
			fieldtype: 'Date', fieldname: 'to_date', label: __('To'),
			default: frappe.datetime.get_today(),
		});
		this.fields.customer = this.page.add_field({
			fieldtype: 'MultiSelectList', fieldname: 'customer', label: __('Customer'),
			get_data: (txt) => frappe.db.get_link_options('Customer', txt),
		});
		this.fields.supplier = this.page.add_field({
			fieldtype: 'MultiSelectList', fieldname: 'supplier', label: __('Supplier'),
			get_data: (txt) => frappe.db.get_link_options('Supplier', txt),
		});

		// Run on Enter from any filter input.
		this.page.wrapper.on('keydown', '.page-form input', (e) => {
			if (e.which === frappe.ui.keyCode.ENTER) {
				this.run_active_tab();
			}
		});
	}

	make_tabs() {
		const nav = this.tabs
			.map((t, i) => `
				<li class="nav-item">
					<a class="nav-link ${i === 0 ? 'active' : ''}" data-tab="${t.key}" href="#">${t.label}</a>
				</li>`)
			.join('');

		const $html = $(`
			<div class="inquiry-page">
				<ul class="nav nav-tabs" style="margin-bottom: 12px;">${nav}</ul>
				<div class="inquiry-body"></div>
				<div class="inquiry-detail" style="display: none; margin-top: 18px;"></div>
			</div>
		`);
		$html.appendTo(this.page.main);

		this.$tabs = $html.find('.nav-tabs');
		this.$body = $html.find('.inquiry-body');
		this.$detail = $html.find('.inquiry-detail');

		// Row-click on any tab's table reveals the item detail subform.
		this.$body.on('click', '.dt-cell', (e) => {
			const idx = $(e.currentTarget).attr('data-row-index');
			const row = (this.current_data || [])[idx];
			if (row && row.item_code) {
				this.load_detail(row.item_code);
			}
		});
		$html.find('.nav-link').on('click', (e) => {
			e.preventDefault();
			const key = $(e.currentTarget).data('tab');
			$html.find('.nav-link').removeClass('active');
			$(e.currentTarget).addClass('active');
			this.active_tab = key;
			this.$detail.hide().empty();
			this.run_active_tab();
		});
	}

	collect_filters() {
		const f = {};
		Object.keys(this.fields).forEach((k) => {
			f[k] = this.fields[k].get_value();
		});
		return f;
	}

	run_active_tab() {
		const tab = this.tabs.find((t) => t.key === this.active_tab);
		frappe.call({
			method: tab.method,
			args: { filters: JSON.stringify(this.collect_filters()) },
			freeze: true,
			freeze_message: __('Loading...'),
			callback: (r) => this.render(r.message),
		});
	}

	render(message) {
		message = message || {};
		const columns = (message.columns || []).map((c) => this.to_datatable_column(c));
		const data = message.data || [];
		this.current_data = data;

		this.$body.empty();
		const $mount = $('<div class="inquiry-table"></div>').appendTo(this.$body);

		if (!data.length) {
			$mount.html(
				`<div class="text-muted" style="padding: 24px 4px;">${__('No records found.')}</div>`
			);
			return;
		}

		// Body as tall as the rows, at most 45% of the screen (see inquiry.css).
		const cell_height = 40;
		const body_height = Math.min(data.length * cell_height + 2, Math.round(window.innerHeight * 0.45));
		$mount.get(0).style.setProperty('--inquiry-body-height', `${body_height}px`);

		new frappe.DataTable($mount.get(0), {
			columns: columns,
			data: data,
			cellHeight: cell_height,
			layout: 'fluid',
			inlineFilters: true,
			noDataMessage: __('No records found.'),
		});
	}

	load_detail(item_code) {
		frappe.call({
			method: 'bp.bp.page.inquiry.inquiry.get_item_detail',
			args: { item_code: item_code },
			callback: (r) => this.render_detail(r.message),
		});
	}

	render_detail(detail) {
		if (!detail || !detail.item_code) {
			this.$detail.hide().empty();
			return;
		}

		const price_lists = detail.price_lists || [];
		const num = (v) => (v === null || v === undefined || v === '' ? '' : format_number(v, null, 2));
		const rows = (detail.uoms || [])
			.map((u) => {
				const cells = [
					`<td>${frappe.utils.escape_html(u.uom || '')}</td>`,
					`<td class="text-right">${num(u.pack)}</td>`,
					`<td>${frappe.utils.escape_html(u.ccy || '')}</td>`,
				].concat(price_lists.map((pl) => `<td class="text-right">${num(u[pl])}</td>`));
				return `<tr>${cells.join('')}</tr>`;
			})
			.join('');

		const img = detail.image
			? `<img src="${frappe.utils.escape_html(detail.image)}" style="max-width: 160px; max-height: 160px; border: 1px solid var(--border-color); border-radius: 4px; object-fit: contain;">`
			: `<div style="width: 160px; height: 160px; display: flex; align-items: center; justify-content: center; border: 1px dashed var(--border-color); border-radius: 4px; color: var(--text-muted);">${__('No image')}</div>`;

		const html = `
			<div class="row">
				<div class="col-md-3">${img}</div>
				<div class="col-md-9">
					<h5 style="margin-top: 0;">
						${frappe.utils.escape_html(detail.item_code)} &mdash;
						${frappe.utils.escape_html(detail.item_name || '')}
					</h5>
					<div class="text-muted" style="margin-bottom: 10px;">
						${__('Stock UOM')}: ${frappe.utils.escape_html(detail.stock_uom || '')}
						${detail.hpp !== undefined ? `&nbsp;|&nbsp; ${__('HPP')}: ${num(detail.hpp)}` : ''}
					</div>
					<table class="table table-bordered" style="max-width: 720px;">
						<thead><tr><th>Unit</th><th class="text-right">Pack</th><th>Ccy</th>
							${price_lists.map((pl) => `<th class="text-right">${frappe.utils.escape_html(pl)}</th>`).join('')}
						</tr></thead>
						<tbody>${rows || `<tr><td colspan="${3 + price_lists.length}" class="text-muted">${__('No UOM/price data.')}</td></tr>`}</tbody>
					</table>
				</div>
			</div>
		`;
		this.$detail.html(html).show();
	}

	to_datatable_column(col) {
		const numeric = ['Float', 'Currency', 'Int'].includes(col.fieldtype);
		return {
			name: col.label,
			id: col.fieldname,
			editable: false,
			align: numeric ? 'right' : 'left',
			format: (value) => this.format_value(value, col.fieldtype),
		};
	}

	format_value(value, fieldtype) {
		if (value === null || value === undefined || value === '') {
			return '';
		}
		if (fieldtype === 'Currency') {
			return format_number(value, null, 2);
		}
		if (fieldtype === 'Float') {
			return format_number(value, null, 2);
		}
		if (fieldtype === 'Int' || fieldtype === 'Check') {
			return frappe.utils.escape_html(String(value));
		}
		if (fieldtype === 'Date') {
			return frappe.datetime.str_to_user(value);
		}
		return frappe.utils.escape_html(String(value));
	}
};
