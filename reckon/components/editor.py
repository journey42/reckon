"""Editor component"""
import reflex as rx
import uuid

def editor(*args, **kwargs) -> rx.Component:
    return rx.editor(
        set_options = rx.EditorOptions(
                resizing_bar=False,  
                button_list=[
                    # ["font", "fontSize", "formatBlock"],
                    # ["fontColor", "hiliteColor"],
                    [
                        "bold",
                        "underline",
                        "italic",
                        "strike",
                        "subscript",
                        "superscript",
                    ],
                    ["fullScreen"],
                    # ["removeFormat"],
                    # ["undo", "redo"],
                    # "/",
                    # ["outdent", "indent"],
                    ["align", "horizontalRule", "list", "table"],
                    ["link", "video"],
                ]
            ),
            id=str(uuid.uuid4()),
            *args,
            **kwargs,
    )