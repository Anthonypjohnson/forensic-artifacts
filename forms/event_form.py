from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, BooleanField, SubmitField
from wtforms.validators import Optional, Length, DataRequired

from forms.ioc_form import MITRE_TACTICS

_ALLOWED_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp']


class EventForm(FlaskForm):
    ioc_id            = SelectField('Linked IOC', coerce=str, validators=[Optional()])
    show_on_timeline  = BooleanField('Show on Timeline', default=True)
    event_category    = SelectField('MITRE Tactic / Category', choices=MITRE_TACTICS)
    system            = StringField('Hostname / System', validators=[Length(max=512)])
    account           = StringField('Account / Username', validators=[Length(max=256)])
    event_datetime    = StringField('Event Date/Time (UTC)', validators=[Length(max=32)])
    high_level_source = StringField('High-Level Source (e.g. SIEM, EDR)', validators=[Length(max=256)])
    detailed_source   = TextAreaField('Detailed Source (log path / query / rule)', validators=[Length(max=2048)])
    notes             = TextAreaField('Notes', validators=[Length(max=4096)])
    screenshot        = FileField('Screenshot',
                                  validators=[FileAllowed(_ALLOWED_IMAGE_EXTENSIONS,
                                                          'Images only (png, jpg, jpeg, gif, webp)')])
    task_id           = StringField('External Reference', validators=[Optional(), Length(max=128)])
    linked_task_id    = SelectField('Linked Task', coerce=str, validators=[Optional()])
    tags              = StringField('Tags')
    editor_name       = StringField('Your Name', validators=[DataRequired(), Length(max=128)])
    change_note       = StringField('Change Note', validators=[DataRequired(), Length(max=512)])
    submit            = SubmitField('Save Event')
