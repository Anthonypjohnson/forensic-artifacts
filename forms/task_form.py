from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Length

STATUSES = [
    ('Open', 'Open'),
    ('In Progress', 'In Progress'),
    ('Blocked', 'Blocked'),
    ('Done', 'Done'),
]

PRIORITIES = [
    ('Low', 'Low'),
    ('Medium', 'Medium'),
    ('High', 'High'),
    ('Critical', 'Critical'),
]


class TaskForm(FlaskForm):
    title       = StringField('Title', validators=[DataRequired(), Length(max=256)])
    status      = SelectField('Status', choices=STATUSES, default='Open')
    priority    = SelectField('Priority', choices=PRIORITIES, default='Medium')
    assignee    = StringField('Assignee', validators=[Optional(), Length(max=128)])
    description = TextAreaField('Description', validators=[Length(max=4096)])
    notes       = TextAreaField('Notes', validators=[Length(max=4096)])
    submit      = SubmitField('Save Task')
