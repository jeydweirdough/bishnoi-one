"""Pin a single-company service database to a company stored on the Platform."""
import sqlalchemy as sa
from alembic import op
revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nbpl_applications", sa.Column("database_company_id", sa.String(36), nullable=True))


def downgrade():
    op.drop_column("nbpl_applications", "database_company_id")
