/* ═══════════════════════════════════════════════════════════
   SwiftTrack — Admin Dashboard Script
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
	} = ST;

	let pollingInterval = null;
	let ordersCache = [];
	let driversCache = [];
	let activeTab = "orders";

	// ── Auth guard ────────────────────────────────────────
	if (!requireAuth("admin")) return;

	// ── Data Loading ──────────────────────────────────────
	async function loadAdminData(statusFilter = "") {
		try {
			const orderParams = new URLSearchParams();
			if (statusFilter) orderParams.set("status", statusFilter);
			orderParams.set("limit", "200");

			const [orderData, driverData] = await Promise.all([
				api("GET", `/api/orders?${orderParams}`),
				api("GET", "/api/auth/drivers"),
			]);

			ordersCache = orderData.orders || [];
			driversCache = Array.isArray(driverData) ? driverData : [];

			renderAdminOrders(ordersCache, driversCache);
			renderDrivers(driversCache, ordersCache);
			updateAdminStats(ordersCache, driversCache);
		} catch (e) {
			console.error("Failed to load admin data:", e);
		}
	}

	function updateAdminStats(orderList, driverList) {
		const total = orderList.length;
		const delivered = orderList.filter(
			(o) => o.status === "DELIVERED",
		).length;
		const processing = orderList.filter(
			(o) => !["DELIVERED", "FAILED", "CANCELLED"].includes(o.status),
		).length;
		const failed = orderList.filter((o) => o.status === "FAILED").length;
		const activePickups = orderList.filter(
			(o) =>
				["PICKUP_ASSIGNED", "PICKING_UP", "PICKED_UP"].includes(o.status),
		).length;

		$("#admin-stat-total").textContent = total;
		$("#admin-stat-delivered").textContent = delivered;
		$("#admin-stat-processing").textContent = processing;
		$("#admin-stat-failed").textContent = failed;
		$("#admin-stat-drivers").textContent = driverList.length;
		$("#admin-stat-pickup").textContent = activePickups;
	}

	function renderAdminOrders(orderList, driverList) {
		const tbody = $("#admin-orders-tbody");
		const empty = $("#admin-orders-empty");

		if (!orderList.length) {
			tbody.innerHTML = "";
			empty.classList.remove("hidden");
			return;
		}

		empty.classList.add("hidden");
		const driverOptions = driverList
			.map((d) => `<option value="${d.username}">${d.username}</option>`)
			.join("");

		tbody.innerHTML = orderList
			.map(
				(order) => `
      <tr>
        <td><span class="order-id">${shortId(order.id)}</span></td>
        <td class="text-sm">${order.client_id}</td>
        <td><span class="status-badge status-${order.status}">${formatStatus(order.status)}</span></td>
        <td>${truncate(order.pickup_address, 20)}</td>
        <td>${truncate(order.delivery_address, 20)}</td>
        <td class="text-sm">${order.pickup_driver_id || '<span class="text-muted">-</span>'}</td>
        <td class="text-sm">${order.delivery_driver_id || '<span class="text-muted">-</span>'}</td>
        <td class="text-muted text-sm">${formatTime(order.created_at)}</td>
        <td class="cell-actions">
          <button class="btn btn-sm btn-secondary" data-action="view-order" data-order-id="${order.id}">View</button>
        </td>
      </tr>
    `,
			)
			.join("");
	}

	function renderDrivers(driverList, orderList) {
		const tbody = $("#drivers-tbody");
		const empty = $("#drivers-empty");

		if (!driverList.length) {
			tbody.innerHTML = "";
			empty.classList.remove("hidden");
			return;
		}

		empty.classList.add("hidden");
		tbody.innerHTML = driverList
			.map((driver) => {
				const assignedCount = orderList.filter(
					(o) =>
						(o.pickup_driver_id === driver.username || o.delivery_driver_id === driver.username) &&
						!["DELIVERED", "FAILED", "CANCELLED"].includes(o.status),
				).length;

				return `
        <tr>
          <td class="text-sm">${driver.username}</td>
          <td class="text-sm">${driver.name}</td>
          <td class="text-sm">${assignedCount}</td>
        </tr>
      `;
			})
			.join("");
	}

	// assignment is now automated

	async function createDriver(event) {
		event.preventDefault();
		const form = event.target;

		const username = form.username.value.trim();
		const name = form.name.value.trim();
		const password = form.password.value;

		if (!username || !name || !password) {
			showToast(
				"warning",
				"Missing Fields",
				"All driver fields are required.",
			);
			return;
		}

		try {
			await api("POST", "/api/auth/drivers", {
				username,
				name,
				password,
			});
			showToast(
				"success",
				"Driver Created",
				`Driver ${username} is ready.`,
			);
			form.reset();
			await loadAdminData($("#admin-filter-status").value);
		} catch (e) {
			showToast("error", "Create Failed", e.message);
		}
	}

	function setActiveTab(tab) {
		activeTab = tab;
		document.querySelectorAll("#admin-tabs .tab-btn").forEach((btn) => {
			btn.classList.toggle("active", btn.dataset.tab === tab);
		});
		$("#panel-orders").classList.toggle("hidden", tab !== "orders");
		$("#panel-drivers").classList.toggle("hidden", tab !== "drivers");
	}

	// ── Init ──────────────────────────────────────────────
	function init() {
		initShell();

		// Tabs
		document.querySelectorAll("#admin-tabs .tab-btn").forEach((btn) => {
			btn.addEventListener("click", () => setActiveTab(btn.dataset.tab));
		});

		// Filter
		$("#admin-filter-status").addEventListener("change", (e) => {
			loadAdminData(e.target.value);
		});

		// Refresh
		$("#refresh-admin-btn").addEventListener("click", () =>
			loadAdminData($("#admin-filter-status").value),
		);

		// Create driver
		$("#create-driver-form").addEventListener("submit", createDriver);

		// Removed manual assignment event listener

		// WebSocket callback
		setOrderUpdateCallback(() =>
			loadAdminData($("#admin-filter-status").value),
		);

		// Start polling
		pollingInterval = setInterval(
			() => loadAdminData($("#admin-filter-status").value),
			10000,
		);

		// Initial load
		setActiveTab(activeTab);
		loadAdminData();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
