import reflex as rx
from azure.communication.email import EmailClient
from datetime import datetime, timezone
from reckon.state.base import User  # Import the module where your SQLAlchemy models are defined
import string
import random

# Use the correct connection string or credential authentication as per your setup
CONNECTION_STRING = "endpoint=https://reckon-acs.unitedstates.communication.azure.com/;accesskey=gdk42ovV9gaOJfMd/c1IkAa5bfJ09j6U/vxNWs/VE4QasjfDxDml33Os1u6JzVc7DSK2hDD0Z1joRufQxcVivg=="

SUPPORT_EMAIL_ADDRESS = "support@reckon.cc"

def generate_temp_password(length=12):
    """Generate a random password."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    return ''.join(random.choice(chars) for _ in range(length))

def send_password_reset_email(session: rx.session, user: User, reset_page_url: str):
    # Generate a temporary password
    temp_password = generate_temp_password()

    # Update the user's password and updated_at fields
    user.password = temp_password  # Remember to hash this in a real application
    user.updated_at = datetime.now(timezone.utc)
    session.commit()

    # Create an EmailClient
    email_client = EmailClient.from_connection_string(CONNECTION_STRING)

    # Prepare the email message
    message = {
        "content": {
            "subject": "Password Reset Request",
            "plainText": f"Your temporary password is: {temp_password}\nPlease use it to log in and then immediately change your password.\nYou can reset your password here: {reset_page_url}",
            "html": f"<p>Your temporary password is: <strong>{temp_password}</strong></p><p>Please use it to log in and then immediately change your password.</p><p>You can reset your password by clicking <a href='{reset_page_url}'>here</a>.</p>"
        },
        "recipients": {
            "to": [{"address": user.email}]
        },
        "senderAddress": SUPPORT_EMAIL_ADDRESS
    }
    
    # Send the email
    try:
        poller = email_client.begin_send(message)
        send_result = poller.result()  # You might need to handle this asynchronously depending on your application
        if send_result['status'] == "Succeeded":
            return True
        else:
            return False
    except Exception as e:
        # Roll back password change in case of email send failure
        session.rollback()
        raise(e)
    
def send_welcome_email(session: rx.session, username: str, email: str, beta_site_url: str):
    # Create an EmailClient
    email_client = EmailClient.from_connection_string(CONNECTION_STRING)
    
    # Prepare the email message
    message = {
        "content": {
            "subject": "Welcome to the Reckon Beta!",
            "plainText": f"Hello {username},\n\nYou have been granted access to the Reckon beta! You can now log in using your existing credentials.\n\nAccess the beta site here: {beta_site_url}\n\nWe look forward to your feedback!",
            "html": f"<p>Hello <strong>{username}</strong>,</p><p>You have been granted access to the Reckon beta! You can now log in using your existing credentials.</p><p>Access the beta site <a href='{beta_site_url}'>here</a>.</p><p>We look forward to your feedback!</p>"
        },
        "recipients": {
            "to": [{"address": email}]
        },
        "senderAddress": SUPPORT_EMAIL_ADDRESS
    }
    
    # Send the email
    try:
        poller = email_client.begin_send(message)
        send_result = poller.result()  # Handle this result according to your application's needs
        if send_result['status'] == "Succeeded":
            return True
        else:
            return False
    except Exception as e:
        session.rollback()  # Consider what to do in case of failure. For simplicity, this just rolls back the session.
        raise(e)
