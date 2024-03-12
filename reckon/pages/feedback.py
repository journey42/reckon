"""feedback page"""
import reflex as rx
from sqlmodel import select
from typing import Any, List
from zoneinfo import ZoneInfo
from reckon.state.base import Feedback, AppState
from reckon.styles import button_style, page_params, reckon_data_editor_theme
from reckon.layouts import profile_layout
from dataclasses import dataclass



@dataclass(frozen=True)
class ColumnNames:
    """The column name to index mapping for the feedback editor."""
    id: int = 1
    username: int = 0
    email: int = 2
    type: int = 3  
    content: int = 4
    created_at: int = 5

column_names = ColumnNames()

def get_feedback() -> List[List]:
    """Get all feedback from the database and prepare them for display in the editor."""

    feedback_data_list = []
    
    # Querying the database for all feedback
    with rx.session() as session: 
        results = session.exec(select(Feedback).order_by(Feedback.created_at.desc()))
        feedback = results.all()

        for feedback in feedback:
            # Extracting the relevant attributes from each feedback
            feedback_data = [
                feedback.user.username,
                str(feedback.id),
                feedback.user.email,
                feedback.type,
                feedback.content,
                str(feedback.created_at.astimezone(ZoneInfo('America/Los_Angeles'))),
            ]
            feedback_data_list.append(feedback_data)
    
    return feedback_data_list

class FeedbackEditorState(AppState):
    """The feedback editor state."""

    feedback: List[List]

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
        """Load the feedback editor."""
        yield self.check_login()
        self.feedback = get_feedback()

    def refresh(self):
        """Refresh the feedback editor."""
        self.feedback = get_feedback()

    def on_column_resize(self, col, width):
        """Resize a column in the logs editor."""
        self.cols[col["pos"]]["width"] = width

    def on_cell_edited(self, pos, val) -> str:
        pass

    def on_delete(self, selection):
        """Delete feedback from the feedback editor."""
        if selection['current'] is None:
            return

        starting_row = selection['current']['range']['y']
        num_rows_selected = selection['current']['range']['height']
        
        ending_row = starting_row + num_rows_selected

        for row in range(starting_row, ending_row):
            with rx.session() as session:
                feedback_id = self.feedback[row][column_names.id]
                print(f"Deleting feedback with ID: {feedback_id}")
                feedback = session.exec(select(Feedback).where(Feedback.id == feedback_id)).first()
                if feedback:
                    session.delete(feedback)
                    #session.expire_on_commit = False
                    session.commit()
        
        for row in range(starting_row, ending_row):
            del self.feedback[starting_row]


@rx.page(on_load=FeedbackEditorState.on_load(), **page_params)
def feedback():
    """The feedback page."""
    return profile_layout(
        rx.vstack(
            rx.data_editor(
                columns=FeedbackEditorState.cols,
                data=FeedbackEditorState.feedback,
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
                on_cell_edited=FeedbackEditorState.on_cell_edited,
                on_delete=FeedbackEditorState.on_delete,
                on_column_resize=FeedbackEditorState.on_column_resize,
                width="65vw",
                height="40vh",
                theme=reckon_data_editor_theme,
            ),
            rx.button("Refresh", on_click=FeedbackEditorState.refresh, **button_style),
            align="center"
        ),
    )