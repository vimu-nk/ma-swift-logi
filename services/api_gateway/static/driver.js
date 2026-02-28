/* ═══════════════════════════════════════════════════════════
   SwiftTrack — Driver Dashboard Script (Unified)
   ═══════════════════════════════════════════════════════════ */

(() => {
	"use strict";

	const ST = window.SwiftTrack;
	const {
		$,
		$$,
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

	// ── Tabs Logic ────────────────────────────────────────
	function initTabs() {
		const tabs = $$(".tab-btn");
		const panes = $$(".tab-pane");

		tabs.forEach((tab) => {
			tab.addEventListener("click", () => {
				// Remove active class from all
				tabs.forEach((t) => t.classList.remove("active"));
				panes.forEach((p) => p.classList.remove("active"));

				// Add active to clicked tab and corresponding pane
				tab.classList.add("active");
				const targetId = tab.dataset.target;
				$(`#${targetId}`).classList.add("active");
			});
		});
	}

	// ── Data Loading & Rendering ──────────────────────────
	async function loadDriverData() {
		try {
			// Fetch all orders related to this driver
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

			// Categorize orders
			const pickups = allOrders.filter(
				(o) =>
					o.pickup_driver_id === currentUser.username &&
					pickupStatuses.includes(o.status),
			);

			const deliveries = allOrders.filter(
				(o) =>
					o.delivery_driver_id === currentUser.username &&
					[
						"AT_WAREHOUSE",
						"OUT_FOR_DELIVERY",
						"DELIVERY_ATTEMPTED",
					].includes(o.status),
			);

			const completed = allOrders.filter(
				(o) =>
					(o.pickup_driver_id === currentUser.username ||
						o.delivery_driver_id === currentUser.username) &&
					["DELIVERED", "FAILED"].includes(o.status),
			);

			// Update dashboard stats
			$("#driver-stat-pickup").textContent = pickups.length;
			$("#driver-stat-delivery").textContent = deliveries.length;
			$("#driver-stat-completed").textContent = completed.length;

			// Render tables
			renderPickups(pickups);
			renderDeliveries(deliveries);
			renderCompleted(completed);
		} catch (e) {
			console.error("Failed to load driver data:", e);
		}
	}

	// ── Pickups ───────────────────────────────────────────
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
			return `<div class="table-action-group"><button class="btn btn-sm btn-action-start" data-action="order-status" data-order-id="${order.id}" data-status="PICKING_UP"><i class="ph ph-rocket-launch"></i> Start Pickup</button></div>`;
		}
		if (order.status === "PICKING_UP") {
			return `<div class="table-action-group"><button class="btn btn-sm btn-action-confirm" data-action="order-status" data-order-id="${order.id}" data-status="PICKED_UP"><i class="ph ph-package"></i> Confirm Pickup</button></div>`;
		}
		if (order.status === "PICKED_UP") {
			return `<div class="table-action-group"><button class="btn btn-sm btn-action-handover" data-action="order-status" data-order-id="${order.id}" data-status="AT_WAREHOUSE"><i class="ph ph-buildings"></i> Drop at Warehouse</button></div>`;
		}
		return `<span class="text-muted text-sm">${formatStatus(order.status)}</span>`;
	}

	// ── Deliveries ────────────────────────────────────────
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
		if (order.status === "AT_WAREHOUSE") {
			return `<div class="table-action-group"><button class="btn btn-sm btn-action-start" data-action="order-status" data-order-id="${order.id}" data-status="OUT_FOR_DELIVERY"><i class="ph ph-truck"></i> Start Delivery</button></div>`;
		}
		return `
			<div class="table-action-group">
				<button class="btn btn-sm btn-action-deliver" data-action="order-status" data-order-id="${order.id}" data-status="DELIVERED"><i class="ph ph-check-circle"></i> Deliver</button>
				<button class="btn btn-sm btn-action-fail" data-action="order-status" data-order-id="${order.id}" data-status="DELIVERY_ATTEMPTED"><i class="ph ph-x-circle"></i> Fail Attempt</button>
			</div>
		`;
	}

	// ── Completed ─────────────────────────────────────────
	function renderCompleted(orderList) {
		const tbody = $("#completed-tbody");
		const empty = $("#completed-empty");

		if (!orderList.length) {
			tbody.innerHTML = "";
			empty.classList.remove("hidden");
			return;
		}

		empty.classList.add("hidden");
		tbody.innerHTML = orderList
			.map((order) => {
				return `
        <tr>
		  <td><span class="order-id clickable" data-action="view-order" data-order-id="${order.id}">${order.display_id || shortId(order.id)}</span></td>
          <td><span class="status-badge status-${order.status}">${formatStatus(order.status)}</span></td>
          <td>${truncate(order.pickup_address, 30)}</td>
          <td>${truncate(order.delivery_address, 30)}</td>
        </tr>
      `;
			})
			.join("");
	}

	// ── Actions ───────────────────────────────────────────
	async function orderAction(orderId, newStatus) {
		try {
			const payload = { status: newStatus };

			if (newStatus === "DELIVERY_ATTEMPTED") {
				const notes = await ST.showPromptDialog(
					"Failure Reason",
					"Enter failure reason (optional):",
					"e.g. Customer not home",
				);
				if (notes === null) return; // Cancelled
				if (notes.trim() !== "") {
					payload.delivery_notes = notes;
				}
			}

			await api("PATCH", `/api/orders/${orderId}/status`, payload);
			showToast(
				"success",
				"Status Updated",
				`Order marked as ${formatStatus(newStatus)}`,
			);
			await loadDriverData();
		} catch (e) {
			showToast("error", "Update Failed", e.message);
		}
	}

	// ── Init ──────────────────────────────────────────────
	function init() {
		initShell();
		initTabs();

		$("#refresh-driver-btn").addEventListener("click", () =>
			loadDriverData(),
		);

		document.addEventListener("click", (e) => {
			const actionEl = e.target.closest('[data-action="order-status"]');
			if (actionEl) {
				const orderId = actionEl.dataset.orderId;
				const status = actionEl.dataset.status;
				if (orderId && status) orderAction(orderId, status);
			}
		});

		setOrderUpdateCallback(() => loadDriverData());
		loadDriverData();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
