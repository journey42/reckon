"""users page."""
import reflex as rx
from sqlmodel import select
from typing import Any, List, Optional
from reckon.state.base import User, Log, AppState
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from reckon.styles import button_style, reckon_data_editor_theme
from reckon.layouts import profile_layout
from reckon.utils.validations import validate_username, validate_email, validate_role
from dataclasses import dataclass
from reckon.utils.comms import send_welcome_email

class WelcomeEmailConfirmationDialogState(AppState):
    show: bool = False
    username: Optional[str] = None
    email: Optional[str] = None
    target_user: Optional[User] = None

    @rx.event
    def visible(self):
        """Change the visibility of the dialog."""
        self.show = not (self.show)

    @rx.event
    def set_username(self, value: str) -> None:
        self.username = value or None

    @rx.event
    def set_email(self, value: str) -> None:
        self.email = value or None

    @rx.event
    def set_recipient(self, target_user: User):
        print(target_user)
        self.target_user = target_user

    @rx.event
    def yes(self):
        with rx.session() as session:
            try:
                self.visible()
                send_result = send_welcome_email(session, self.username, self.email, 'https://reckon.cc')  
                if not send_result:
                    raise ValueError("Email not sent")
            except Exception as e:
                return rx.window_alert(f"Email not sent. Error {str(e)}")

def send_welcome_email_confirmation_dialog():
    return rx.alert_dialog.root(
        rx.alert_dialog.content(
            rx.alert_dialog.title("Email Confirmation"),
            rx.alert_dialog.description(
                "Send welcome email?",
            ),
            rx.flex(
                rx.alert_dialog.action(
                    rx.button("Yes", on_click=WelcomeEmailConfirmationDialogState.yes),
                ),
                rx.alert_dialog.cancel(
                    rx.button("No", on_click=WelcomeEmailConfirmationDialogState.visible),
                ),
                spacing="3",
                margin_top="16px",
                justify="end",
            ),
            style={"max_width": 450},
        ),
        open=WelcomeEmailConfirmationDialogState.show,
    )

@dataclass(frozen=True)
class ColumnNames:
    """The column name to index mapping for the user editor."""
    id: int = 1
    username: int = 0
    email: int = 2
    enabled: int = 3  
    role: int = 4
    created_at: int = 5
    updated_at: int = 6

column_names = ColumnNames()

def get_users() -> List[List]:
    """Get all users from the database and prepare them for display in the editor."""

    user_data_list = []
    
    # Querying the database for all users
    with rx.session() as session: 
        results = session.exec(select(User).order_by(User.created_at.desc()))
        users = results.all()

        for user in users:
            # Extracting the relevant attributes from each user
            user_data = [
                user.username,
                str(user.id),
                user.email,
                user.enabled,
                user.role,
                str(user.created_at.astimezone(ZoneInfo('America/Los_Angeles'))),
                str(user.updated_at.astimezone(ZoneInfo('America/Los_Angeles'))),
            ]
            user_data_list.append(user_data)
    return user_data_list

class UserEditorState(AppState):
    """The user editor state."""

    users: List[List]

    cols: list[Any] = [
        {
            "title": "Username",
            "type": "str",
        },
        {
            "title": "ID",
            "type": "str"
        },
        {
            "title": "Email",
            "type": "str",
        },
        {
            "title": "Enabled",
            "type": "bool",
        },
        {
            "title": "Role",
            "type": "int",
        },
                {
            "title": "Created At",
            "type": "str",
        },
                {
            "title": "Updated At",
            "type": "str",
        },
    ]

    def on_load(self):
        """Load the users page."""
        result = self.check_login()
        if result:
            return result
        self.users = get_users()

    def refresh(self):
        self.users = get_users()

    def on_column_resize(self, col, width):
        """Resize a column in the logs editor."""
        self.cols[col["pos"]]["width"] = width

    def on_cell_edited(self, pos, val) -> str:
        """Edit the selected cell."""
        col, row = pos

        if val["data"] is None or val["data"] == "": #No deletes of individual cells
            return

        if (col in [column_names.id, column_names.created_at, column_names.updated_at]): #No ID or datetime editing
            return rx.window_alert("You cannot edit this field")
        
        try:
            with rx.session() as session:
                user = session.exec(select(User).where(User.id == self.users[row][column_names.id])).first()
                if user is not None:
                    if (col == column_names.username):
                        is_valid, message = validate_username(val["data"])
                        if not is_valid:
                            return rx.window_alert(message)
                        user.username = val["data"]
                    elif (col == column_names.email):
                        is_valid, message = validate_email(val["data"])
                        if not is_valid:
                            return rx.window_alert(message)
                        user.email = val["data"]
                    elif (col == column_names.enabled):
                        user.enabled = val["data"]
                        if user.enabled == True:
                            yield WelcomeEmailConfirmationDialogState.set_username(user.username)
                            yield WelcomeEmailConfirmationDialogState.set_email(user.email)
                            yield WelcomeEmailConfirmationDialogState.visible()       
                    elif (col == column_names.role):
                        is_valid, message = validate_role(val["data"])
                        if not is_valid:
                            return rx.window_alert(message)
                        user.role = val["data"]
                    user.updated_at = datetime.now(timezone.utc)
                    session.add(user)
                    log = Log(user_id=self.user.id, content=f"user with username:{user.username} and id:{user.id} updated", type="admin", created_at=datetime.now(timezone.utc))
                    session.add(log)
                    #session.expire_on_commit = False
                    session.commit()
                    self.users[row][col] = val["data"]
        except Exception as e:
            print(f"An error occurred: {e}")
            rx.window_alert(f"An error occurred: {e}")
            return

    def on_delete(self, selection):
        """Delete selected users."""
        if selection['current'] is None:
            return

        starting_row = selection['current']['range']['y']
        num_rows_selected = selection['current']['range']['height']
        
        ending_row = starting_row + num_rows_selected

        for row in range(starting_row, ending_row):
            with rx.session() as session:
                user_id = self.users[row][column_names.id]
                print(f"Deleting user with ID: {user_id}")
                user = session.exec(select(User).where(User.id == user_id)).first()
                if user:
                    session.delete(user)
                    log = Log(user_id=self.user.id, content=f"user with username:{user.username} and id:{user.id} deleted", type="admin", created_at=datetime.now(timezone.utc))
                    session.add(log)
                    #session.expire_on_commit = False
                    session.commit()
        
        for row in range(starting_row, ending_row):
            del self.users[starting_row]


@rx.page(on_load=UserEditorState.on_load())
def users():
    """The users page."""
    return profile_layout(
        rx.vstack(
            rx.data_editor(
                columns=UserEditorState.cols,
                data=UserEditorState.users,
                on_paste=True,
                draw_focus_ring=False,
                freeze_columns=1,
                group_header_height=0,
                header_height=80,
                max_column_auto_width=100,
                min_column_width=100,
                smooth_scroll_x=True,
                vertical_border=False,
                overscroll_x=0,
                on_cell_edited=UserEditorState.on_cell_edited,
                on_delete=UserEditorState.on_delete,
                on_column_resize=UserEditorState.on_column_resize,
                width="65vw",
                height="40vh",
                theme=reckon_data_editor_theme,
            ),
            rx.button("Refresh", on_click=UserEditorState.refresh, **button_style),
            align="center"
        ),
        send_welcome_email_confirmation_dialog(),
    )
