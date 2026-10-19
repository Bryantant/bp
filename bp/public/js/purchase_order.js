// Price List Rate -> % Disk 1 -> Disk 1 = Rate, the Sales Invoice mechanism
// with two steps (see bp.discounts in discount_utils.bundle.js). The
// authoritative recompute runs on every save in
// bp.utils.cascading_discount.recalculate_cascading_discount. Price List Rate
// starts from the supplier's last purchase (bp.utils.last_purchase_price).
bp.discounts.bindItemGrid("Purchase Order Item");
