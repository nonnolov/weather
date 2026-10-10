"""Add separate append-only station fetch evidence."""
from alembic import op
import sqlalchemy as sa
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("rain_station_fetches",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("station_id",sa.Integer(),nullable=False),
        sa.Column("poll_slot",sa.DateTime(timezone=True),nullable=False),
        sa.Column("collected_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("status",sa.String(24),nullable=False),
        sa.Column("error_code",sa.String(40),nullable=True),
        sa.Column("raw_sha256",sa.String(64),nullable=True),
        sa.Column("raw_body",sa.Text(),nullable=True),
        sa.Column("evidence",sa.JSON(),nullable=True),
        sa.UniqueConstraint("station_id","poll_slot",name="uq_rain_station_poll_slot"),
        sa.CheckConstraint("status IN ('quarantined','failed')",name="ck_rain_station_fetch_status"))
    op.create_index("ix_rain_station_fetches_station_id","rain_station_fetches",["station_id"])
    op.create_index("ix_rain_station_fetches_collected_at","rain_station_fetches",["collected_at"])

def downgrade():
    op.drop_index("ix_rain_station_fetches_collected_at",table_name="rain_station_fetches")
    op.drop_index("ix_rain_station_fetches_station_id",table_name="rain_station_fetches")
    op.drop_table("rain_station_fetches")
