import reflex as rx


class TiptapEditor(rx.NoSSRComponent):
    tag = "RhizTiptapEditor"
    is_default = True
    library = rx.asset("tiptap_editor.jsx", shared=True).importable_path
    lib_dependencies: list[str] = [
        "@tiptap/react",
        "@tiptap/starter-kit",
        "@tiptap/extension-placeholder",
        "@tiptap/extension-underline",
        "@tiptap/extension-link",
        "@tiptap/extension-image",
        "@tiptap/extension-youtube",
    ]
    value: rx.Var[str]
    on_change: rx.EventHandler[lambda e: [e]]
    placeholder: rx.Var[str]
    height: rx.Var[str]
    toolbar_enabled: rx.Var[bool]
