"""User-scoped encrypted model profiles. Additive; no changes to existing tables."""
from alembic import op
import sqlalchemy as sa
revision = '0008_user_model_profiles'
down_revision = '0007_literature_notes'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('user_model_profiles',
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('revision', sa.String(36), nullable=False),
        sa.Column('provider', sa.String(40), nullable=False),
        sa.Column('base_url', sa.String(2048), nullable=False),
        sa.Column('model', sa.String(200), nullable=False),
        sa.Column('encrypted_key', sa.LargeBinary(), nullable=True),
        sa.Column('encryption_scheme', sa.String(64), nullable=False),
        sa.Column('tested_revision', sa.String(36), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False), mysql_engine='InnoDB')

def downgrade():
    if op.get_bind().execute(sa.text('SELECT COUNT(*) FROM user_model_profiles')).scalar():
        raise RuntimeError('Refusing to drop saved model configurations; review a backup/export plan first')
    op.drop_table('user_model_profiles')
