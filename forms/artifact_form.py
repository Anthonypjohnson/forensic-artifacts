from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length


class ArtifactForm(FlaskForm):
    name = StringField(
        "Artifact Name",
        validators=[DataRequired(), Length(max=256)],
        description="e.g. NTUSER.DAT — UserAssist",
    )
    location = TextAreaField(
        "Location",
        validators=[DataRequired()],
        description="OS path, registry key, event log location, etc.",
    )
    tools = TextAreaField(
        "Tools",
        validators=[DataRequired()],
        description="Tools used to parse (e.g. RegRipper, Autopsy)",
    )
    instructions = TextAreaField(
        "Instructions",
        validators=[DataRequired()],
        description="Step-by-step parsing instructions",
    )
    significance = TextAreaField(
        "Significance",
        validators=[DataRequired()],
        description="Forensic value / what this artifact proves",
    )
    tags = StringField(
        "Tags",
        description="Comma-separated tags (e.g. Windows, Registry, Execution)",
    )
    editor_name = StringField(
        "Your Name / Handle",
        validators=[DataRequired(), Length(max=128)],
        description="Name to record in the edit history",
    )
    change_note = StringField(
        "Change Note",
        validators=[DataRequired(), Length(max=512)],
        description="Brief summary of what changed (shown in history)",
    )
    submit = SubmitField("Save Artifact")
