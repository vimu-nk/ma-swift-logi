/* ═══════════════════════════════════════════════════════════
   SwiftTrack — Driver Dashboard Script
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

	// ── Auth guard ────────────────────────────────────────
	if (!requireAuth("driver")) return;
	const currentUser = getUser();
	if (!currentUser) return;

	// ── Data Loading ──────────────────────────────────────
	async function loadDriverStats() {
		try {
			const data = await api("GET", `/api/orders?driver_id_any=${currentUser.username}&limit=200`);
			const myOrders = data.orders || [];

			let activePickups = 0;
			let activeDeliveries = 0;
			let completedToday = 0;

			// Quick filtering directly matching user
			myOrders.forEach(o => {
				if (o.pickup_driver_id === currentUser.username) {
					if (["PICKUP_ASSIGNED", "PICKING_UP", "PICKED_UP"].includes(o.status)) {
						activePickups++;
					}
					// If the driver was both pickup & delivery, don't double count completed today, wait, let's just count globally
				}
				if (o.delivery_driver_id === currentUser.username) {
					if (["OUT_FOR_DELIVERY", "DELIVERY_ATTEMPTED"].includes(o.status)) {
						activeDeliveries++;
					}
				}
				
				if (["DELIVERED", "FAILED"].includes(o.status)) {
					// Extremely naive today check
					const orderDate = new Date(o.created_at).setHours(0,0,0,0);
					const today = new Date().setHours(0,0,0,0);
					if (orderDate === today) completedToday++;
				}
			});

			$("#driver-stat-pickup").textContent = activePickups;
			$("#driver-stat-delivery").textContent = activeDeliveries;
			$("#driver-stat-completed").textContent = completedToday;
		} catch (e) {
			console.error("Failed to load driver stats:", e);
		}
	}

	// ── Init ──────────────────────────────────────────────
	function init() {
		initShell();

		// Refresh
		$("#refresh-driver-btn").addEventListener("click", () =>
			loadDriverStats(),
		);

		// WebSocket callback
		setOrderUpdateCallback(() => loadDriverStats());

		// Start polling
		pollingInterval = setInterval(() => loadDriverStats(), 10000);

		// Initial load
		loadDriverStats();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
