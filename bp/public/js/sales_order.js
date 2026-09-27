// Four-step cascading discount (Discount 1 %, Discount 1 Amount, Discount 2 %,
// Discount 2 Amount), see bp.discounts in discount_utils.bundle.js. The
// authoritative recompute runs on every save in
// bp.overrides.sales_order.recalculate_cascading_discount.
bp.discounts.bindItemGrid("Sales Order Item");
