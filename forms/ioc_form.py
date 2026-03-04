from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length

SEVERITIES = [('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High'), ('Critical', 'Critical')]
HASH_TYPES = [
    ('', '— select —'),
    ('MD5', 'MD5'),
    ('SHA1', 'SHA1'),
    ('SHA256', 'SHA256'),
    ('SHA512', 'SHA512'),
    ('SSDEEP', 'SSDEEP'),
]

_INDICATOR_FIELDS = [
    'hostname', 'ip_address', 'domain', 'url', 'hash_value',
    'filename', 'file_path', 'registry_key', 'command_line',
    'email', 'user_account',
]


class IocForm(FlaskForm):
    case_name    = StringField('Case / Hunt', validators=[Length(max=256)])
    severity     = SelectField('Severity', choices=SEVERITIES, default='Medium')
    hostname     = StringField('Hostname / System', validators=[Length(max=512)])
    ip_address   = StringField('IP Address', validators=[Length(max=45)])
    domain       = StringField('Domain', validators=[Length(max=512)])
    url          = StringField('URL', validators=[Length(max=2048)])
    hash_value   = StringField('Hash Value', validators=[Length(max=256)])
    hash_type    = SelectField('Hash Type', choices=HASH_TYPES)
    filename     = StringField('Filename', validators=[Length(max=512)])
    file_path    = StringField('File Path', validators=[Length(max=1024)])
    registry_key = StringField('Registry Key', validators=[Length(max=1024)])
    command_line = TextAreaField('Command Line', validators=[Length(max=2048)])
    email        = StringField('Email Address', validators=[Length(max=512)])
    user_account = StringField('User Account', validators=[Length(max=256)])
    notes        = TextAreaField('Notes', validators=[Length(max=4096)])
    tags         = StringField('Tags')
    editor_name  = StringField('Your Name', validators=[DataRequired(), Length(max=128)])
    change_note  = StringField('Change Note', validators=[DataRequired(), Length(max=512)])
    submit       = SubmitField('Save IOC')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        if not any(getattr(self, f).data.strip() for f in _INDICATOR_FIELDS):
            self.hostname.errors.append('At least one indicator field is required.')
            return False
        return True
