"""initial_schema

Revision ID: 4b3e2274e4f4
Revises: 
Create Date: 2026-06-22 11:06:32.586890

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4b3e2274e4f4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create events table
    op.create_table(
        'events',
        sa.Column('event_id', sa.String(), primary_key=True),
        sa.Column('event_type', sa.String(), nullable=True),
        sa.Column('event_cause', sa.String(), nullable=True),
        sa.Column('corridor', sa.String(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('requires_road_closure', sa.Boolean(), nullable=True),
        sa.Column('priority', sa.String(), nullable=True),
        sa.Column('start_datetime', sa.DateTime(), nullable=True),
        sa.Column('end_datetime', sa.DateTime(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()'))
    )

    # Create predictions table
    op.create_table(
        'predictions',
        sa.Column('prediction_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(), sa.ForeignKey('events.event_id'), nullable=True),
        sa.Column('predicted_duration_min', sa.Float(), nullable=True),
        sa.Column('predicted_disruption_class', sa.String(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('recommended_officers', sa.Integer(), nullable=True),
        sa.Column('recommended_barricades', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('recommended_diversions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('predicted_at', sa.DateTime(), nullable=True, server_default=sa.text('now()'))
    )

    # Create outcomes table
    op.create_table(
        'outcomes',
        sa.Column('outcome_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(), sa.ForeignKey('events.event_id'), nullable=True),
        sa.Column('actual_duration_min', sa.Float(), nullable=True),
        sa.Column('actual_disruption_class', sa.String(), nullable=True),
        sa.Column('actual_officers_deployed', sa.Integer(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('logged_by', sa.String(), nullable=True),
        sa.Column('logged_at', sa.DateTime(), nullable=True, server_default=sa.text('now()'))
    )

    # Create recalibration_log table
    op.create_table(
        'recalibration_log',
        sa.Column('recal_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_cause', sa.String(), nullable=True),
        sa.Column('corridor', sa.String(), nullable=True),
        sa.Column('old_bias_correction', sa.Float(), nullable=True),
        sa.Column('new_bias_correction', sa.Float(), nullable=True),
        sa.Column('n_outcomes_used', sa.Integer(), nullable=True),
        sa.Column('recalibrated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()'))
    )

    # Create index on recalibration_log(event_cause, corridor)
    op.create_index(
        'idx_recal_cause_corridor',
        'recalibration_log',
        ['event_cause', 'corridor']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index
    op.drop_index('idx_recal_cause_corridor', table_name='recalibration_log')
    # Drop tables in reverse dependency order
    op.drop_table('recalibration_log')
    op.drop_table('outcomes')
    op.drop_table('predictions')
    op.drop_table('events')
