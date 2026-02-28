/* ═══════════════════════════════════════════════════════════
   SwiftTrack — Delivery Dashboard Script
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
	async function loadDeliveries() {
		try {
			// Get orders where this driver is involved
			const data = await api(
				"GET",
				`/api/orders?driver_id=${currentUser.username}&limit=200`,
			);
			const allOrders = data.orders || [];

			const myDeliveries = allOrders.filter(
				(o) =>
					o.delivery_driver_id === currentUser.username &&
					["OUT_FOR_DELIVERY", "DELIVERY_ATTEMPTED"].includes(
						o.status,
					),
			);

			renderDeliveries(myDeliveries);
		} catch (e) {
			console.error("Failed to load deliveries:", e);
		}
	}

	function renderDeliveries(orderList) {
		const tbody = $("#delivery-tbody");
		const empty = $("#delivery-empty");

		if (!orderList.length) {
			tbody.innerHTML = "";
			empty.classList.remove("hidden");
			return;
		}

		empty.classList.add("hidden");
		tbody.innerHTML = orderList
			.map((order) => {
				const actions = getDeliveryActions(order);
				const formatAttempts = `${order.delivery_attempts || 0} / ${order.max_delivery_attempts || 3}`;

				return `
        <tr>
		  <td><span class="order-id clickable" data-action="view-order" data-order-id="${order.id}">${order.display_id || shortId(order.id)}</span></td>
          <td><span class="status-badge status-${order.status}">${formatStatus(order.status)}</span></td>
          <td>
            <div style="font-size:0.85em; opacity:0.8">${truncate(order.receiver_name, 40)}</div>
            <strong>${truncate(order.delivery_address, 40)}</strong>
          </td>
          <td><span class="badge ${order.delivery_attempts > 0 ? "badge-amber" : ""}">${formatAttempts}</span></td>
          <td class="cell-actions">${actions}</td>
        </tr>
      `;
			})
			.join("");
	}

	function getDeliveryActions(order) {
		return `
			<div style="display: flex; gap: var(--space-xs);">
				<button class="btn btn-sm btn-success" data-action="delivery-status" data-order-id="${order.id}" data-status="DELIVERED"><i class="ph ph-check-circle"></i> Deliver</button>
				<button class="btn btn-sm btn-danger" data-action="delivery-status" data-order-id="${order.id}" data-status="DELIVERY_ATTEMPTED"><i class="ph ph-x-circle"></i> Fail Attempt</button>
			</div>
		`;
	}

	async function deliveryAction(orderId, newStatus) {
		try {
			const payload = { status: newStatus };

			// If failed attempt, maybe prompt for reason? We will keep it simple and just send.
			if (newStatus === "DELIVERY_ATTEMPTED") {
				const notes = await ST.showPromptDialog(
					"Failure Reason",
					"Enter failure reason (optional):",
					"e.g. Customer not home",
				);
				if (notes !== null && notes.trim() !== "") {
					payload.delivery_notes = notes;
				} else if (notes === null) {
					return; // Cancelled
				}
			}

			await api("PATCH", `/api/orders/${orderId}/status`, payload);
			showToast(
				"success",
				"Status Updated",
				`Order marked as ${formatStatus(newStatus)}`,
			);
			await loadDeliveries();
		} catch (e) {
			showToast("error", "Update Failed", e.message);
		}
	}

	// ── Init ──────────────────────────────────────────────
	function init() {
		initShell();

		$("#refresh-delivery-btn").addEventListener("click", () =>
			loadDeliveries(),
		);

		document.addEventListener("click", (e) => {
			const actionEl = e.target.closest(
				'[data-action="delivery-status"]',
			);
			if (actionEl) {
				const orderId = actionEl.dataset.orderId;
				const status = actionEl.dataset.status;
				if (orderId && status) deliveryAction(orderId, status);
			}
		});

		setOrderUpdateCallback(() => loadDeliveries());
		pollingInterval = setInterval(() => loadDeliveries(), 10000);
		loadDeliveries();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
