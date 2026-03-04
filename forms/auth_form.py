from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from pathlib import Path

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


def _load_common_passwords():
    path = Path(__file__).parent.parent / "static" / "common_passwords.txt"
    try:
        with open(path) as f:
            return {line.strip().lower() for line in f if line.strip()}
    except FileNotFoundError:
        return set()


COMMON_PASSWORDS = _load_common_passwords()


def validate_password_strength(form, field):
    pw = field.data or ""
    if len(pw) < MIN_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(pw) > MAX_PASSWORD_LENGTH:
        raise ValidationError(f"Password must be no more than {MAX_PASSWORD_LENGTH} characters.")
    if pw.lower() in COMMON_PASSWORDS:
        raise ValidationError("That password is too common. Please choose a more unique one.")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=64)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign In")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password",
        validators=[DataRequired(), validate_password_strength],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Change Password")


class CreateUserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=2, max=64)])
    password = PasswordField(
        "Password",
        validators=[DataRequired(), validate_password_strength],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    is_admin = BooleanField("Grant admin role")
    submit = SubmitField("Create User")
