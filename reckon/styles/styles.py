"""Reckon Styles"""

favicon="/favicon.svg"

reckon_green="#16e073"
reckon_dark_green="#01cc5d"

button_style = dict(
    bg=reckon_green,
    color="white",
    _hover={"bg": reckon_dark_green},
    border_radius="full",
)

dialog_button_style = dict(
    max_width="36px",
    max_height="36px",
)

image_button_style = dict(
    _hover={"bg": "rgba(255, 255, 255, 0)"},
    _focus={"bg": "rgba(255, 255, 255, 0)"},
    display="flex",
    align_items="center",
    justify_content="center",
    border_radius="50%",
)

page_footer_style = dict(
    margin_top="auto",
    width="100%",
    text_align="center",
    position="relative",
    bottom="0",
)

interior_grid_style = dict (
    # py=1,
    # px=1,
    # gap=1,
    # padding="1",
    padding="1px",
    spacing="2",
    align="center",
    justify="center",
)

reckoning_grid_style = dict (
    border="2px solid #ededed",
    border_radius="10px",
    padding="4px",
    # gap=4,
    spacing="4",
    margin="4px",
)

input_style = dict(
     margin="4px",
     padding="4px",
     size="1",
     width="100%",
    # _focus={"borderColor": "#000000", "boxShadowColor": "#000000"}
)

comment_badge_style = dict(
    position="absolute",
    top="5px",
    left="5px",
    z_index="20",
    # width="15px",
    height="15px",
)

vote_count_and_timestamp_style = dict(
    position="absolute",
    right="5px",
    bottom="5px",
    white_space="nowrap", #Prevents the text from wrapping
    overflow="hidden", #Hides overflow
    text_overflow="ellipsis", #Adds an ellipsis for text that overflows the container width
    max_width="100%",
)

popover_button_style = dict(
    max_width="32px",
    max_height="32px",
)

read_only_text_style = dict(
    read_only=True,
    overflow="hidden",
    background="var(--gray-a2)",
    border_radius="10px",
    padding="2em",
    size="1"
)

form_box_style = dict(
    background="white",
    border="1px solid #eaeaea",
    padding="24px",
    width="100%",
    max_width="420px",
    border_radius="20px",
    box_shadow="0 20px 45px rgba(15, 23, 42, 0.12)",
)

link_style = dict(
    color="gray.600",
    _hover={"color": "gray.800", "textDecoration": "underline"}
)

info_text_style = dict (
    font_size="1xl",
    font_weight="normal",
    margin="1em",
)

meta = [
    {"name":"viewport", "content":"width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"}
]

page_params = dict(
    title="Reckon",
    description="Speak Together",
    image=favicon,
    meta=meta
)

from reflex.components.datadisplay.dataeditor import (
    DataEditorTheme,
)

reckon_data_editor_theme = {
    "accent_color": reckon_dark_green,
    "accent_light": reckon_green,

}
