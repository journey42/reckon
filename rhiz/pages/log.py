"""logs page"""

import reflex as rx
from sqlmodel import select
from zoneinfo import ZoneInfo
from typing import Any, List
from rhiz.state.base import Log, AppState
from rhiz.styles import button_style, page_params, rhiz_data_editor_theme
from rhiz.layouts import profile_layout
from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnNames:
    """The column name to index mapping for the logs editor."""

    id: int = 1
    username: int = 0
    email: int = 2
    type: int = 3
    content: int = 4
    created_at: int = 5


column_names = ColumnNames()


def get_logs() -> List[List]:
    """Get all logs from the database and prepare them for display in the editor."""

    logs_data_list = []

    # Querying the database for all logs
    with rx.session() as session:
        results = session.exec(select(Log).order_by(Log.created_at.desc()))
        logs = results.all()

        for log in logs:
            # Extracting the relevant attributes from each logs
            logs_data = [
                log.user.username if log.user is not None else "",
                str(log.id),
                log.user.email if log.user is not None else "",
                log.type,
                log.content,
                str(log.created_at.astimezone(ZoneInfo("America/Los_Angeles"))),
            ]
            logs_data_list.append(logs_data)

    return logs_data_list


class LogEditorState(AppState):
    """The logs editor state."""

    logs: List[List]

    cols: list[Any] = [
        {
            "title": "Username",
            "type": "str",
        },
        {"title": "ID", "type": "str"},
        {
            "title": "Email",
            "type": "str",
        },
        {
            "title": "Type",
            "type": "str",
        },
        {
            "title": "Content",
            "type": "str",
        },
        {
            "title": "Created At",
            "type": "str",
        },
    ]

    def on_load(self):
        """Load the logs editor."""
        result = self.check_login()
        if result:
            return result
        self.logs = get_logs()

    def refresh(self):
        """Refresh the logs editor."""
        self.logs = get_logs()

    def on_column_resize(self, col, width):
        """Resize a column in the logs editor."""
        self.cols[col["pos"]]["width"] = width

    def on_cell_edited(self, pos, val) -> str:
        """Edit a cell in the logs editor."""
        pass

    def on_delete(self, selection):
        """Delete the selected logs."""

        if selection["current"] is None:
            return

        starting_row = selection["current"]["range"]["y"]
        num_rows_selected = selection["current"]["range"]["height"]

        ending_row = starting_row + num_rows_selected

        for row in range(starting_row, ending_row):
            with rx.session() as session:
                logs_id = self.logs[row][column_names.id]
                print(f"Deleting logs with ID: {logs_id}")
                logs = session.exec(select(Log).where(Log.id == logs_id)).first()
                if logs:
                    session.delete(logs)
                    # session.expire_on_commit = False
                    session.commit()

        for row in range(starting_row, ending_row):
            del self.logs[starting_row]


@rx.page(on_load=LogEditorState.on_load(), **page_params)
def log():
    """log page."""
    return profile_layout(
        rx.vstack(
            rx.data_editor(
                columns=LogEditorState.cols,
                data=LogEditorState.logs,
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
                on_cell_edited=LogEditorState.on_cell_edited,
                on_delete=LogEditorState.on_delete,
                on_column_resize=LogEditorState.on_column_resize,
                width="100%",
                height="40vh",
                theme=rhiz_data_editor_theme,
            ),
            rx.button("Refresh", on_click=LogEditorState.refresh, **button_style),
            width="100%",
            spacing="4",
        ),
    )
