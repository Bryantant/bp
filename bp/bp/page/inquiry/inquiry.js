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

// Tab-specific filters (second filter row); filters not listed here show on every tab.
const TAB_FILTERS = {
	balance: [],
	sales: ['customer', 'from_date', 'to_date'],
	purchase: ['supplier', 'from_date', 'to_date'],
	price_list: [],
};
const ALL_TAB_FILTERS = ['customer', 'supplier', 'from_date', 'to_date'];

// Tabs whose rows are invoice lines: they show the invoice remark and the party below the table.
const PARTY_LABEL = { sales: __('Customer'), purchase: __('Supplier') };

// Column widths in px, so users do not resize them every time. Description takes the
// width that is left (at least DESCRIPTION_MIN_WIDTH); unlisted columns (warehouses,
// price lists) get DEFAULT_WIDTH.
const COLUMN_WIDTHS = {
	item_code: 100,
	brand: 70,
	date: 105,
	qty: 85,
	unit: 55,
	stock_uom: 55,
	ccy: 50,
	price: 120,
	rtn: 45,
	cust: 70,
	supp: 70,
	do_no: 140,
	purchase_no: 140,
	supp_do_no: 120,
	total_qty: 90,
	hpp: 115,
};
const DEFAULT_WIDTH = 90;
const DESCRIPTION_MIN_WIDTH = 260;

bp.Inquiry = class Inquiry {
	constructor(page) {
		this.page = page;
		this.active_tab = 'balance';
		this.tabs = [
			{ key: 'balance', label: __('Balance'), method: 'bp.bp.page.inquiry.inquiry.get_balance' },
			{ key: 'sales', label: __('Sales'), method: 'bp.bp.page.inquiry.inquiry.get_sales' },
			{ key: 'purchase', label: __('Purchase'), method: 'bp.bp.page.inquiry.inquiry.get_purchase' },
			{ key: 'price_list', label: __('Price List'), method: 'bp.bp.page.inquiry.inquiry.get_price_list' },
		];
		this.selected = new Set();
		this.make_filters();
		this.make_tabs();
		this.bind_copy();
		this.apply_context();
		this.clear_results();
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
		this.update_filters();
		this.clear_results();
	}

	make_filters() {
		this.fields = {};
		this.fields.item_group = this.page.add_field({
			fieldtype: 'MultiSelectList', fieldname: 'item_group', label: __('Item Group'),
			get_data: (txt) => frappe.db.get_link_options('Item Group', txt),
		});
		this.fields.item = this.page.add_field({
			fieldtype: 'MultiSelectList', fieldname: 'item', label: __('Item'),
			get_data: (txt) => frappe.db.get_link_options('Item', txt),
		});
		this.fields.description = this.page.add_field({
			fieldtype: 'Data', fieldname: 'description', label: __('Description'),
		});

		// Second row: filters that only apply to some tabs (see TAB_FILTERS).
		$('<div class="inquiry-filter-break"></div>').appendTo(this.page.page_form);
		this.fields.customer = this.page.add_field({
			fieldtype: 'Link', fieldname: 'customer', label: __('Customer'), options: 'Customer',
		});
		this.fields.supplier = this.page.add_field({
			fieldtype: 'Link', fieldname: 'supplier', label: __('Supplier'), options: 'Supplier',
		});
		this.fields.from_date = this.page.add_field({
			fieldtype: 'Date', fieldname: 'from_date', label: __('From'),
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		});
		this.fields.to_date = this.page.add_field({
			fieldtype: 'Date', fieldname: 'to_date', label: __('To'),
			default: frappe.datetime.get_today(),
		});
		this.update_filters();

		// Search sits with the filters, as in the old program, instead of the page header.
		const $actions = $(`
			<div class="inquiry-actions">
				<button class="btn btn-primary" data-action="search">${__('Search')}</button>
				<button class="btn btn-default" data-action="select-all">${__('Select All')}</button>
				<button class="btn btn-default" data-action="copy">${__('Copy')}</button>
			</div>
		`).appendTo(this.page.page_form);
		$actions.on('click', '[data-action="search"]', () => this.run_active_tab());
		$actions.on('click', '[data-action="select-all"]', () => this.select_all());
		$actions.on('click', '[data-action="copy"]', () => this.copy_selected());

		// Run on Enter from any filter input.
		this.page.wrapper.on('keydown', '.page-form input', (e) => {
			if (e.which === frappe.ui.keyCode.ENTER) {
				this.run_active_tab();
			}
		});
	}

	uses_filter(fieldname) {
		return !ALL_TAB_FILTERS.includes(fieldname)
			|| (TAB_FILTERS[this.active_tab] || []).includes(fieldname);
	}

	// Show only the filters the active tab uses; the rest stay hidden and are not sent.
	update_filters() {
		Object.keys(this.fields).forEach((k) => this.fields[k].$wrapper.toggle(this.uses_filter(k)));
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
				<div class="inquiry-info">
					<div class="inquiry-remark"></div>
					<div class="inquiry-party"></div>
				</div>
				<div class="inquiry-detail" style="display: none; margin-top: 18px;"></div>
			</div>
		`);
		$html.appendTo(this.page.main);

		this.$tabs = $html.find('.nav-tabs');
		this.$body = $html.find('.inquiry-body');
		this.$info = $html.find('.inquiry-info');
		this.$detail = $html.find('.inquiry-detail');

		// Row number column = Access record selector: click selects the row, Shift+click a
		// range, Ctrl/Cmd+click adds or removes one. A click on any other cell clears it.
		this.$body.on('mousedown', '.dt-cell--col-0', (e) => {
			if (e.shiftKey) e.preventDefault(); // no text selection on Shift+click
		});
		this.$body.on('click', '.dt-cell', (e) => {
			const $cell = $(e.currentTarget);
			const idx = $cell.attr('data-row-index');
			const row = (this.current_data || [])[idx];
			if (!row) return;
			if ($cell.attr('data-col-index') === '0') {
				this.select_row(Number(idx), e);
			} else if (this.selected.size) {
				this.set_selection([]);
			}
			this.show_info(row);
			if (row.item_code) {
				this.load_detail(row.item_code);
			}
		});
		$html.find('.nav-link').on('click', (e) => {
			e.preventDefault();
			const key = $(e.currentTarget).data('tab');
			$html.find('.nav-link').removeClass('active');
			$(e.currentTarget).addClass('active');
			this.active_tab = key;
			this.update_filters();
			this.clear_results();
			this.run_active_tab();
		});
	}

	collect_filters() {
		const f = {};
		Object.keys(this.fields).forEach((k) => {
			if (this.uses_filter(k)) f[k] = this.fields[k].get_value();
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

	// Empty table area of the same height as a filled one, so the remark/party strip and
	// the item detail below never move.
	clear_results(message) {
		this.current_data = [];
		this.datatable = null;
		this.$selection_style = null;
		this.selected = new Set();
		this.anchor = undefined;
		this.$body.html(`<div class="inquiry-empty text-muted">${message || ''}</div>`);
		this.$info.toggle(!!PARTY_LABEL[this.active_tab]);
		this.show_info(null);
		this.$detail.hide().empty();
	}

	render(message) {
		message = message || {};
		const data = message.data || [];
		if (!data.length) {
			this.clear_results(__('No records found.'));
			return;
		}
		this.clear_results();
		this.current_data = data;
		this.columns = message.columns || [];

		this.$body.empty();
		const $mount = $('<div class="inquiry-table"></div>').appendTo(this.$body);

		this.datatable = new frappe.DataTable($mount.get(0), {
			columns: this.columns.map((c) => this.to_datatable_column(c, $mount.width())),
			data: data,
			cellHeight: 33,
			layout: 'fixed',
			inlineFilters: true,
			checkedRowStatus: false,
			noDataMessage: __('No records found.'),
		});
		// After the datatable: it replaces the content of its mount element.
		this.$selection_style = $('<style></style>').appendTo(this.$body);
	}

	show_info(row) {
		const label = PARTY_LABEL[this.active_tab];
		if (!label) return;
		const party = row ? row.cust || row.supp : '';
		const esc = (v) => frappe.utils.escape_html(v || '');
		this.$info.find('.inquiry-remark').html(esc(row && row.remarks));
		this.$info.find('.inquiry-party').html(
			party ? `${esc(label)} : ${esc(party)}<br>${esc(row.party_name)}` : ''
		);
	}

	// ---- Row selection and copy to Excel -------------------------------------------------

	// Row indexes in the order the table shows them (after sorting and column filters).
	visible_rows() {
		if (!this.datatable) return [];
		const dm = this.datatable.datamanager;
		const shown = new Set(dm.getFilteredRowIndices().map(Number));
		return dm.rowViewOrder.map(Number).filter((i) => shown.has(i));
	}

	select_row(idx, e) {
		const additive = e.ctrlKey || e.metaKey;
		if (e.shiftKey && this.anchor !== undefined && this.selected.size) {
			const order = this.visible_rows();
			const [a, b] = [order.indexOf(this.anchor), order.indexOf(idx)].sort((x, y) => x - y);
			const range = a < 0 ? [idx] : order.slice(a, b + 1);
			this.set_selection(additive ? [...this.selected, ...range] : range);
			return;
		}
		this.anchor = idx;
		if (additive) {
			const next = new Set(this.selected);
			next.has(idx) ? next.delete(idx) : next.add(idx);
			this.set_selection([...next]);
		} else {
			this.set_selection([idx]);
		}
	}

	select_all() {
		this.set_selection(this.visible_rows());
	}

	// Highlight with a generated style sheet: the datatable re-renders rows while
	// scrolling, so classes set on row elements would be lost.
	set_selection(indexes) {
		this.selected = new Set(indexes);
		if (!this.$selection_style) return;
		const css = [...this.selected]
			.map((i) => `.inquiry-table .dt-row-${i} .dt-cell`)
			.join(',\n');
		this.$selection_style.text(css ? `${css} { background-color: var(--inquiry-selected-bg); }` : '');
	}

	// Cmd/Ctrl+C with rows selected copies them; otherwise the datatable copies the focused
	// cell or cell range as before. Text typed or highlighted in an input is left alone.
	bind_copy() {
		this.page.wrapper.get(0).addEventListener('keydown', (e) => {
			if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'c' || !this.selected.size) return;
			if ($(e.target).is('input, textarea, [contenteditable="true"]')) return;
			e.preventDefault();
			e.stopPropagation();
			this.copy_selected();
		}, true);
	}

	// Selected rows as tab-separated text with a header line, the way Access copies a
	// datasheet: pastes straight into Excel. Numbers stay plain so Excel can sum them.
	copy_selected() {
		const rows = this.visible_rows().filter((i) => this.selected.has(i));
		if (!rows.length) {
			frappe.show_alert({ message: __('Select rows first: click the row numbers or Select All.'), indicator: 'orange' });
			return;
		}
		const types = {};
		this.columns.forEach((c) => (types[c.fieldname] = c.fieldtype));
		const cols = this.datatable.datamanager.getColumns(true).filter((c) => c.id in types);
		const clean = (v) => String(v).replace(/[\t\r\n]+/g, ' ').trim();
		const cell = (value, fieldtype) => {
			if (value === null || value === undefined || value === '') return '';
			if (fieldtype === 'Date') return frappe.datetime.str_to_user(value);
			if (['Float', 'Currency', 'Int', 'Check'].includes(fieldtype)) return String(flt(value));
			return clean(value);
		};
		const lines = [cols.map((c) => clean(c.content)).join('\t')].concat(
			rows.map((i) => cols.map((c) => cell(this.current_data[i][c.id], types[c.id])).join('\t'))
		);
		frappe.utils.copy_to_clipboard(lines.join('\n'));
	}

	// ---- Item detail ---------------------------------------------------------------------

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

	to_datatable_column(col, table_width) {
		const numeric = ['Float', 'Currency', 'Int'].includes(col.fieldtype);
		let width = COLUMN_WIDTHS[col.fieldname] || DEFAULT_WIDTH;
		if (col.fieldname === 'item_name') {
			// Whatever the other columns leave, minus the row numbers, the 1px cell borders
			// and the scrollbar.
			const others = this.columns
				.filter((c) => c.fieldname !== 'item_name')
				.reduce((sum, c) => sum + (COLUMN_WIDTHS[c.fieldname] || DEFAULT_WIDTH), 0);
			const row_no = 25 + 9 * String(this.current_data.length).length;
			const borders = this.columns.length + 1;
			width = Math.max(DESCRIPTION_MIN_WIDTH, table_width - others - row_no - borders - 15);
		}
		return {
			name: col.label,
			id: col.fieldname,
			editable: false,
			width: width,
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
