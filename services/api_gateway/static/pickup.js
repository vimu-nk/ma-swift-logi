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

	if (!requireAuth("driver")) return;
	const currentUser = getUser();
	if (!currentUser) return;

	// ── Data Loading ──────────────────────────────────────
	async function loadPickups() {
		try {
			// Get orders where this driver is the pickup driver
			const data = await api(
				"GET",
				`/api/orders?driver_id_any=${encodeURIComponent(currentUser.username)}&limit=200`,
			);

			const allOrders = data.orders || [];
			const pickupStatuses = [
				"WMS_RECEIVED",
				"ROUTE_OPTIMIZED",
				"READY",
				"PICKUP_ASSIGNED",
				"PICKING_UP",
				"PICKED_UP",
			];
			const myPickups = allOrders.filter(
				(o) =>
					o.pickup_driver_id === currentUser.username &&
					pickupStatuses.includes(o.status),
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
				const packageDetails =
					typeof order.package_details === "string"
						? JSON.parse(order.package_details)
						: order.package_details || {};
				const details = packageDetails.weight
					? `${packageDetails.weight}kg (${packageDetails.dimensions || "N/A"})`
					: "-";

				return `
        <tr>
		  <td><span class="order-id clickable" data-action="view-order" data-order-id="${order.id}">${order.display_id || shortId(order.id)}</span></td>
          <td><span class="status-badge status-${order.status}">${formatStatus(order.status)}</span></td>
          <td>
			<div style="font-size:0.85em; opacity:0.8">${truncate(order.sender_name, 30)}</div>
			<div><strong>${truncate(order.pickup_address, 30)}</strong></div>
			<div class="text-sm text-muted">${details}</div>
		  </td>
          <td>
            <div style="font-size:0.85em; opacity:0.8">${truncate(order.receiver_name, 30)}</div>
            ${truncate(order.delivery_address, 30)}
          </td>
          <td class="cell-actions">${actions}</td>
        </tr>
      `;
			})
			.join("");
	}

	function getPickupActions(order) {
		if (order.status === "PICKUP_ASSIGNED") {
			return `<div class="table-action-group"><button class="btn btn-sm btn-action-start" data-action="pickup-status" data-order-id="${order.id}" data-status="PICKING_UP"><i class="ph ph-rocket-launch"></i> Start Pickup</button></div>`;
		}
		if (order.status === "PICKING_UP") {
			return `<div class="table-action-group"><button class="btn btn-sm btn-action-confirm" data-action="pickup-status" data-order-id="${order.id}" data-status="PICKED_UP"><i class="ph ph-package"></i> Confirm Pickup</button></div>`;
		}
		if (order.status === "PICKED_UP") {
			return `<div class="table-action-group"><button class="btn btn-sm btn-action-handover" data-action="pickup-status" data-order-id="${order.id}" data-status="AT_WAREHOUSE"><i class="ph ph-buildings"></i> Drop at Warehouse</button></div>`;
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
				`Order updated to ${formatStatus(newStatus)}`,
			);
			await loadPickups();
		} catch (e) {
			showToast("error", "Update Failed", e.message);
		}
	}
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
		loadPickups();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
