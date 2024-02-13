"""validations for common user inputs."""
import re

def validate_email(email):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if re.match(pattern, email):
        return True, "Email is valid."
    return False, "Email is invalid."

foul_words = {"shit", "fuck", "tits", "balls"}  # Add your list of foul words

def validate_username(username):
    if any(foul_word in username.lower() for foul_word in foul_words):
        return False, "Username contains inappropriate language."
    if not username.isalnum():
        return False, "Username must contain only letters and numbers."
    return True, "Username is valid."

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search("[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search("[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search("[0-9]", password):
        return False, "Password must contain at least one number."
    if not re.search("[_@$!%*?&#]", password):
        return False, "Password must contain at least one special character (_@$!%*?&#)."
    return True, "Password is strong."

def validate_role(role):
    if role not in {"u", "a", "m"}:
        return False, "Role must be either 'user (u)' or 'admin (a)' or 'moderator (m)'."
    return True, "Role is valid."
