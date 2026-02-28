/* ═══════════════════════════════════════════════════════════
   SwiftTrack — Client Dashboard Script
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
		formatTime,
		initShell,
		setOrderUpdateCallback,
		getUser,
	} = ST;

	let orders = [];

	// ── Auth guard ────────────────────────────────────────
	if (!requireAuth("client")) return;

	// ── Data Loading ──────────────────────────────────────
	async function loadOrders(statusFilter = "") {
		try {
			const params = new URLSearchParams();
			if (statusFilter) params.set("status", statusFilter);
			params.set("limit", "100");

			const data = await api("GET", `/api/orders?${params}`);
			orders = data.orders || [];
			renderOrders(orders);
			updateClientStats(orders);
		} catch (e) {
			console.error("Failed to load orders:", e);
		}
	}

	function updateClientStats(orderList) {
		const total = orderList.length;
		const delivered = orderList.filter(
			(o) => o.status === "DELIVERED",
		).length;
		const inTransit = orderList.filter((o) =>
			[
				"PICKUP_ASSIGNED",
				"PICKING_UP",
				"PICKED_UP",
				"AT_WAREHOUSE",
				"OUT_FOR_DELIVERY",
				"DELIVERY_ATTEMPTED",
			].includes(o.status),
		).length;
		const inProgress = orderList.filter(
			(o) => !["DELIVERED", "FAILED", "CANCELLED"].includes(o.status),
		).length;

		$("#stat-total").textContent = total;
		$("#stat-delivered").textContent = delivered;
		$("#stat-in-progress").textContent = inProgress;
		$("#stat-in-transit").textContent = inTransit;
	}

	function renderOrders(orderList) {
		const tbody = $("#orders-tbody");
		const empty = $("#orders-empty");

		if (!orderList.length) {
			tbody.innerHTML = "";
			empty.classList.remove("hidden");
			return;
		}

		empty.classList.add("hidden");
		tbody.innerHTML = orderList
			.map(
				(order) => `
      <tr>
        <td><span class="order-id clickable" data-action="view-order" data-order-id="${order.id}">${order.display_id || shortId(order.id)}</span></td>
        <td><span class="status-badge status-${order.status}">${formatStatus(order.status)}</span></td>
        <td>
          <div style="font-size:0.85em; opacity:0.8">${truncate(order.sender_name, 25)}</div>
          <div>${truncate(order.pickup_address, 25)}</div>
        </td>
        <td>
          <div style="font-size:0.85em; opacity:0.8">${truncate(order.receiver_name, 25)}</div>
          <div>${truncate(order.delivery_address, 25)}</div>
        </td>
        <td class="text-muted text-sm">${formatTime(order.created_at)}</td>
      </tr>
    `,
			)
			.join("");
	}

	async function createOrder(formData) {
		const btn = $("#create-order-btn");
		btn.disabled = true;
		btn.innerHTML = '<span class="spinner"></span> Creating...';

		try {
			const order = await api("POST", "/api/orders", {
				client_id: getUser().username,
				sender_name: formData.sender_name,
				receiver_name: formData.receiver_name,
				pickup_address: formData.pickup_address,
				delivery_address: formData.delivery_address,
				package_details: {
					weight: parseFloat(formData.weight) || 1.0,
					type: formData.type,
					description: formData.description,
				},
			});

			showToast(
				"success",
				"Order Created",
				`Order ${shortId(order.id)} submitted!`,
			);
			$("#create-order-form").reset();
			await loadOrders();
		} catch (e) {
			showToast("error", "Creation Failed", e.message);
		} finally {
			btn.disabled = false;
			btn.innerHTML = '<i class="ph ph-rocket-launch"></i> Create Order';
		}
	}

	// ── Init ──────────────────────────────────────────────
	function init() {
		initShell();

		// Create order form
		$("#create-order-form").addEventListener("submit", async (e) => {
			e.preventDefault();
			await createOrder({
				sender_name: $("#sender-name").value,
				receiver_name: $("#receiver-name").value,
				pickup_address: $("#pickup-address").value,
				delivery_address: $("#delivery-address").value,
				weight: $("#pkg-weight").value,
				type: $("#pkg-type").value,
				description: $("#pkg-description").value,
			});
		});

		// Filter
		$("#filter-status").addEventListener("change", (e) => {
			loadOrders(e.target.value);
		});

		// Refresh
		$("#refresh-orders-btn").addEventListener("click", () => loadOrders());

		// WebSocket callback
		setOrderUpdateCallback(() => loadOrders());

		// Initial load
		loadOrders();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
