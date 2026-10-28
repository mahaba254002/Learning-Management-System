"""Preserve approved grading policy when institution defaults change."""
from alembic import op
import sqlalchemy as sa

revision = 'g9c0d1e2f3b4'
down_revision = 'f8b9c0d1e2a3'
branch_labels = depends_on = None


def upgrade():
    op.add_column('coursework', sa.Column('grading_bands', sa.JSON(), nullable=True))
    op.execute("""UPDATE coursework c SET grading_bands = COALESCE(i.learning_settings -> 'grade_bands', '[]'::json)
        FROM institutions i WHERE i.id=c.institution_id AND EXISTS(SELECT 1 FROM student_scores s WHERE s.coursework_id=c.id)""")


def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM coursework WHERE grading_bands IS NOT NULL LIMIT 1')).first():
        raise RuntimeError('Grading policy snapshots exist. Preserve their academic history before downgrading.')
    op.drop_column('coursework', 'grading_bands')
