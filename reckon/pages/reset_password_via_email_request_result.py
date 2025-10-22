"""password reset via email result page."""
import reflex as rx
from reckon.layouts import auth_layout
from reckon.styles import link_style, page_params, info_text_style
from reckon.state.base import AppState

class ResetPasswordViaEmailRequestResultPageState(AppState):
    @rx.var
    def result_message(self) -> str:
        result_param = self.get_path_param("result").lower()
        if result_param == "true":
            return "Your password has been reset."
        return "Your password has not been reset. Please try again."

@rx.page(route="/reset_password_via_email_request_result/[result]", **page_params)
def reset_password_via_email_request_result():
    """The password reset via email result page."""
    return auth_layout(
        rx.text(
            ResetPasswordViaEmailRequestResultPageState.result_message,
            **info_text_style,
        ),
        rx.text(
            rx.link("Ready to login?", href="/login", **link_style),
        )
    )
