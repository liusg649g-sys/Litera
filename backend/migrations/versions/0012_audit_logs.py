"""SEC-07 unified audit log: seven-column operation trail, single-row JSON payload.

Columns:
  user_id      -- operator (who performed it); nullable for system actions
  created_at   -- operation timestamp (UTC DATETIME(6))
  action       -- operation type (extract / qa_ask / translate / upload / ...)
  target       -- primary resource id (document_id / note_id / annotation_id / ...)
  status       -- result (success / failed / partial / skipped)
  skill        -- capability identifier (extract-llm / qa-rag / translate / ...)
  usage        -- JSON blob: {duration_ms, tokens_in, tokens_out, model, extra}

Plus a ``payload`` JSON column that contains the full seven-column event so
downstream consumers can read one row and everything is there.  ``payload``
content is truncated to 4096 bytes at write time to protect log volume.

Indexes cover the common filter axes; the row is always INSERT-only
(never updated), so indexes are cheap.
"""
from alembic import op
import sqlalchemy as sa

revision = '0012_audit_logs'
down_revision = '0011_extraction_retry_queue'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), nullable=False),
        sa.Column('action', sa.String(32), nullable=False),
        sa.Column('target', sa.String(36), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('skill', sa.String(48), nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('usage', sa.JSON(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        mysql_engine='InnoDB',
    )
    op.create_index('ix_audit_logs_user_created', 'audit_logs', ['user_id', 'created_at'])
    op.create_index('ix_audit_logs_action_status', 'audit_logs', ['action', 'status'])
    op.create_index('ix_audit_logs_target', 'audit_logs', ['target'])


def downgrade():
    op.drop_index('ix_audit_logs_target', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action_status', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_created', table_name='audit_logs')
    op.drop_table('audit_logs')
