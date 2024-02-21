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

image_button_style = dict(
   # _hover={"bg": reckon_dark_green},
    display="flex",
    align_items="center",
    justify_content="center",
    border_radius="50%",
)

control_panel_text_style = dict (
    # display="flex",
    align_items="center",
    justify_content="center",
)

input_style = dict(
     mb=4,
    _focus={"borderColor": "#000000", "boxShadowColor": "#000000"}
)

input_style_focus = dict(
    _focus={"borderColor": "#000000", "boxShadowColor": "#000000"}
)

read_only_text_style = dict(
    is_read_only=True,
    overflow="hidden",
    background_color="gray.50",
    border_radius="10px",
    padding="1em",
    font_size="sm"
)

form_box_style = dict(
    bg="white",
    border="1px solid #eaeaea",
    p=4,
    max_width="400px",
    border_radius="lg",
)

link_style = dict(
    color="gray.600",
    _hover={"color": "gray.800", "textDecoration": "underline"}
)

info_text_style = dict (
    font_size="1xl",
    font_weight="normal",
    mb=4,
    border_x="1px solid #ededed",
    h="100%",
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

