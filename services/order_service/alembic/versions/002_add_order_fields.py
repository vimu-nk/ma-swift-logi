"""Alembic migration — add display_id, sender_name, receiver_name.

Adds new fields required by feature enhancements.
"""

from alembic import op

# revision identifiers
revision = "002_add_order_fields"
down_revision = "001_create_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns as nullable first
    op.execute("ALTER TABLE orders ADD COLUMN display_id VARCHAR(20);")
    op.execute("ALTER TABLE orders ADD COLUMN sender_name VARCHAR(100);")
    op.execute("ALTER TABLE orders ADD COLUMN receiver_name VARCHAR(100);")

    # Update existing rows (populate with defaults to satisfy NOT NULL constraints)
    op.execute(
        "UPDATE orders SET "
        "display_id = 'ODR-' || upper(substring(replace(id::text, '-', '') for 8)), "
        "sender_name = client_id, "
        "receiver_name = client_id "
        "WHERE display_id IS NULL;"
    )

    # Alter columns to NOT NULL
    op.execute("ALTER TABLE orders ALTER COLUMN display_id SET NOT NULL;")
    op.execute("ALTER TABLE orders ALTER COLUMN sender_name SET NOT NULL;")
    op.execute("ALTER TABLE orders ALTER COLUMN receiver_name SET NOT NULL;")

    # Add unique index
    op.execute("CREATE UNIQUE INDEX ix_orders_display_id ON orders (display_id);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_orders_display_id;")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS receiver_name;")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS sender_name;")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS display_id;")
