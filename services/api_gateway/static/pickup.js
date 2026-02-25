/* ═══════════════════════════════════════════════════════════
   SwiftTrack — Pickup Dashboard Script
   ═══════════════════════════════════════════════════════════ */

(() => {
	"use strict";

	const ST = window.SwiftTrack;
	const {
		$,
		api,
		requireAuth,
		showToast,
		shortId,
		truncate,
		formatStatus,
		initShell,
		setOrderUpdateCallback,
		getUser,
	} = ST;

	let pollingInterval = null;

	if (!requireAuth("driver")) return;
	const currentUser = getUser();
	if (!currentUser) return;

	// ── Data Loading ──────────────────────────────────────
	async function loadPickups() {
		try {
			// Get orders where this driver is the pickup driver
			const data = await api("GET", `/api/orders?driver_id=${currentUser.username}&limit=200`);
			// The backend driver_id query field currently filters by `driver_id` in order_service list_orders Wait, no, we updated the gateway to proxy `driver_id` as `driver_id` and order_service uses `pickup_driver_id == driver_id OR delivery_driver_id == driver_id`.
			// So this will get both. We will filter client-side anyway.
			
			const allOrders = data.orders || [];
			const myPickups = allOrders.filter(
				(o) => o.pickup_driver_id === currentUser.username && 
				["PICKUP_ASSIGNED", "PICKING_UP", "PICKED_UP"].includes(o.status)
			);

			renderPickups(myPickups);
		} catch (e) {
			console.error("Failed to load pickups:", e);
		}
	}

	function renderPickups(orderList) {
		const tbody = $("#pickup-tbody");
		const empty = $("#pickup-empty");

		if (!orderList.length) {
			tbody.innerHTML = "";
			empty.classList.remove("hidden");
			return;
		}

		empty.classList.add("hidden");
		tbody.innerHTML = orderList
			.map((order) => {
				const actions = getPickupActions(order);
				const packageDetails = order.package_details ? JSON.parse(order.package_details) : {};
				const details = packageDetails.weight ? `${packageDetails.weight}kg (${packageDetails.dimensions || 'N/A'})` : '-';

				return `
        <tr>
          <td><span class="order-id" style="cursor: pointer; text-decoration: underline;" data-action="view-order" data-order-id="${order.id}">${shortId(order.id)}</span></td>
          <td><span class="status-badge status-${order.status}">${formatStatus(order.status)}</span></td>
          <td>
			<div><strong>${truncate(order.pickup_address, 30)}</strong></div>
			<div class="text-sm text-muted">${details}</div>
		  </td>
          <td>${truncate(order.delivery_address, 30)}</td>
          <td class="cell-actions">${actions}</td>
        </tr>
      `;
			})
			.join("");
	}

	function getPickupActions(order) {
		if (order.status === "PICKUP_ASSIGNED") {
			return `<button class="btn btn-sm btn-primary" data-action="pickup-status" data-order-id="${order.id}" data-status="PICKING_UP">🚀 Start Pickup</button>`;
		}
		if (order.status === "PICKING_UP") {
			return `<button class="btn btn-sm btn-success" data-action="pickup-status" data-order-id="${order.id}" data-status="PICKED_UP">📦 Confirm Pickup</button>`;
		}
		if (order.status === "PICKED_UP") {
			return `<button class="btn btn-sm btn-amber" data-action="pickup-status" data-order-id="${order.id}" data-status="AT_WAREHOUSE">🏢 Drop at Warehouse</button>`;
		}
		return `<span class="text-muted text-sm">${formatStatus(order.status)}</span>`;
	}

	async function pickupAction(orderId, newStatus) {
		try {
			const payload = { status: newStatus };
			await api("PATCH", `/api/orders/${orderId}/status`, payload);
			showToast(
				"success",
				"Status Updated",
				`Order → ${formatStatus(newStatus)}`,
			);
			await loadPickups();
		} catch (e) {
			showToast("error", "Update Failed", e.message);
		}
	}

	// ── Init ──────────────────────────────────────────────
	function init() {
		initShell();

		$("#refresh-pickup-btn").addEventListener("click", () => loadPickups());

		document.addEventListener("click", (e) => {
			const actionEl = e.target.closest('[data-action="pickup-status"]');
			if (actionEl) {
				const orderId = actionEl.dataset.orderId;
				const status = actionEl.dataset.status;
				if (orderId && status) pickupAction(orderId, status);
			}
		});

		setOrderUpdateCallback(() => loadPickups());
		pollingInterval = setInterval(() => loadPickups(), 10000);
		loadPickups();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
