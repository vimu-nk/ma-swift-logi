"""Alembic migration — create orders and order_status_history tables.

Uses raw SQL to avoid SQLAlchemy's Enum DDL machinery silently re-emitting
CREATE TYPE even when create_type=False is set.
"""

from alembic import op

# revision identifiers
revision = "001_create_orders"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enum type (idempotent) ──────────────────────────────────────────
    op.execute(
        "DO $$ BEGIN "
        "  CREATE TYPE order_status AS ENUM ("
        "    'PENDING','CMS_REGISTERED','WMS_RECEIVED','ROUTE_OPTIMIZED',"
        "    'READY','PICKUP_ASSIGNED','PICKING_UP','PICKED_UP','AT_WAREHOUSE',"
        "    'OUT_FOR_DELIVERY','DELIVERY_ATTEMPTED','DELIVERED','FAILED','CANCELLED'"
        "  );"
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )

    # ── Orders table ────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE orders (
            id              UUID            PRIMARY KEY,
            client_id       VARCHAR(100)    NOT NULL,
            status          order_status    NOT NULL DEFAULT 'PENDING',
            pickup_address  TEXT            NOT NULL,
            delivery_address TEXT           NOT NULL,
            package_details JSONB           NOT NULL DEFAULT '{}',
            cms_reference   VARCHAR(100),
            wms_reference   VARCHAR(100),
            route_id        VARCHAR(100),
            pickup_driver_id VARCHAR(100),
            delivery_driver_id VARCHAR(100),
            delivery_notes  TEXT,
            delivery_attempts INTEGER NOT NULL DEFAULT 0,
            max_delivery_attempts INTEGER NOT NULL DEFAULT 3,
            proof_of_delivery JSONB,
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_orders_client_id  ON orders (client_id);")
    op.execute("CREATE INDEX ix_orders_status     ON orders (status);")
    op.execute("CREATE INDEX ix_orders_created_at ON orders (created_at);")

    # ── Order status history table ──────────────────────────────────────
    op.execute("""
        CREATE TABLE order_status_history (
            id          UUID            PRIMARY KEY,
            order_id    UUID            NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            old_status  order_status,
            new_status  order_status    NOT NULL,
            details     TEXT,
            created_at  TIMESTAMPTZ     NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_order_status_history_order_id ON order_status_history (order_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS order_status_history;")
    op.execute("DROP TABLE IF EXISTS orders;")
    op.execute("DROP TYPE IF EXISTS order_status;")
