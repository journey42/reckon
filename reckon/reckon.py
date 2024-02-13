"""App routes"""
import reflex as rx
from .pages import home, login, logged_out, about, guidelines, help, privacy, terms, signup, register, reset_password, reset_password_via_email, request_reset_password, reset_password_email_sent, reset_password_successful, reset_password_via_email_successful, signup_successful, profile, profile_updated, users, feedback, log, new_concepts, trending_concepts, your_reckonings, comments, comment_editor, new_comment_editor, new_comment_on_parent_editor, concept, concept_editor

app = rx.App()
