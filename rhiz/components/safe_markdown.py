import reflex as rx


class SafeMarkdown(rx.NoSSRComponent):
    tag = "SafeMarkdown"
    is_default = True
    library = rx.asset("safe_markdown.jsx", shared=True).importable_path
    lib_dependencies: list[str] = [
        "react-markdown",
        "remark-gfm",
        "rehype-raw",
        "rehype-sanitize",
        "rehype-unwrap-images",
        "remark-math",
        "rehype-katex",
    ]
    content: rx.Var[str]
