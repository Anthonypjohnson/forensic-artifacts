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
MITRE_TACTICS = [
    ('', '— none —'),
    ('Reconnaissance', 'Reconnaissance'),
    ('Resource Development', 'Resource Development'),
    ('Initial Access', 'Initial Access'),
    ('Execution', 'Execution'),
    ('Persistence', 'Persistence'),
    ('Privilege Escalation', 'Privilege Escalation'),
    ('Defense Evasion', 'Defense Evasion'),
    ('Credential Access', 'Credential Access'),
    ('Discovery', 'Discovery'),
    ('Lateral Movement', 'Lateral Movement'),
    ('Collection', 'Collection'),
    ('Command and Control', 'Command and Control'),
    ('Exfiltration', 'Exfiltration'),
    ('Impact', 'Impact'),
]
PROTOCOLS = [
    ('', '— none —'),
    ('TCP', 'TCP'), ('UDP', 'UDP'), ('ICMP', 'ICMP'),
    ('HTTP', 'HTTP'), ('HTTPS', 'HTTPS'), ('DNS', 'DNS'),
    ('SMTP', 'SMTP'), ('FTP', 'FTP'), ('SSH', 'SSH'),
    ('SMB', 'SMB'), ('RDP', 'RDP'), ('TLS', 'TLS'),
    ('Other', 'Other'),
]

_INDICATOR_FIELDS = [
    'hostname', 'ip_address', 'domain', 'url', 'hash_value',
    'filename', 'file_path', 'registry_key', 'command_line',
    'email', 'user_account', 'user_agent', 'network_port', 'network_protocol',
]


class IocForm(FlaskForm):
    category         = StringField('Category', validators=[Length(max=256)])
    severity         = SelectField('Severity', choices=SEVERITIES, default='Medium')
    hostname         = StringField('Hostname / System', validators=[Length(max=512)])
    ip_address       = StringField('IP Address', validators=[Length(max=45)])
    domain           = StringField('Domain', validators=[Length(max=512)])
    url              = StringField('URL', validators=[Length(max=2048)])
    hash_value       = StringField('Hash Value', validators=[Length(max=256)])
    hash_type        = SelectField('Hash Type', choices=HASH_TYPES)
    filename         = StringField('Filename', validators=[Length(max=512)])
    file_path        = StringField('File Path', validators=[Length(max=1024)])
    registry_key     = StringField('Registry Key', validators=[Length(max=1024)])
    command_line     = TextAreaField('Command Line', validators=[Length(max=2048)])
    email            = StringField('Email Address', validators=[Length(max=512)])
    user_account     = StringField('User Account', validators=[Length(max=256)])
    notes            = TextAreaField('Notes', validators=[Length(max=4096)])
    user_agent       = StringField('User-Agent String', validators=[Length(max=1024)])
    mitre_category   = SelectField('MITRE ATT&CK Tactic', choices=MITRE_TACTICS)
    detection_rule   = TextAreaField('Detection Rule', validators=[Length(max=8192)])
    network_port     = StringField('Network Port', validators=[Length(max=64)])
    network_protocol = SelectField('Network Protocol', choices=PROTOCOLS)
    tags             = StringField('Tags')
    editor_name      = StringField('Your Name', validators=[DataRequired(), Length(max=128)])
    change_note      = StringField('Change Note', validators=[DataRequired(), Length(max=512)])
    submit           = SubmitField('Save IOC')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        if not any(getattr(self, f).data.strip() for f in _INDICATOR_FIELDS):
            self.hostname.errors.append('At least one indicator field is required.')
            return False
        return True
