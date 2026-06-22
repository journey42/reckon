import React from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import Underline from '@tiptap/extension-underline'
import Link from '@tiptap/extension-link'
import Image from '@tiptap/extension-image'
import Youtube from '@tiptap/extension-youtube'

const RhizTiptapEditor = ({ value, onChange, placeholder, height, toolbarEnabled, style }) => {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        link: false,
        underline: false,
      }),
      Placeholder.configure({
        placeholder: placeholder || 'Write something...',
      }),
      Underline.configure(),
      Link.configure({ openOnClick: false }),
      Image.configure(),
      Youtube.configure({ modestBranding: true, width: 480, height: 360 }),
    ],
    content: value || '',
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML())
    },
    editorProps: {
      attributes: {
        class: 'rhiz-editor prose prose-sm max-w-none focus:outline-none',
      },
    },
    immediatelyRender: true,
  }, [])

  React.useEffect(() => {
    if (editor && value !== undefined && value !== editor.getHTML()) {
      editor.commands.setContent(value || '', false)
    }
  }, [value, editor])

  if (!editor) return null

  const tb = (label, onClick, active, title) =>
    React.createElement('button', {
      type: 'button',
      onClick,
      title,
      className: `rtb ${active ? 'active' : ''}`,
      key: title,
    }, label)

  const sep = () =>
    React.createElement('div', { className: 'rtb-sep', key: Math.random() })

  const toolbar = toolbarEnabled
    ? React.createElement('div', { className: 'rtb-bar' },
        ...[
          tb('\u21A9', () => editor.chain().focus().undo().run(), false, 'Undo'),
          tb('\u21AA', () => editor.chain().focus().redo().run(), false, 'Redo'),
          sep(),
          tb('B', () => editor.chain().focus().toggleBold().run(), editor.isActive('bold'), 'Bold'),
          tb('I', () => editor.chain().focus().toggleItalic().run(), editor.isActive('italic'), 'Italic'),
          tb('U', () => editor.chain().focus().toggleUnderline().run(), editor.isActive('underline'), 'Underline'),
          tb('S', () => editor.chain().focus().toggleStrike().run(), editor.isActive('strike'), 'Strikethrough'),
          sep(),
          tb('H1', () => editor.chain().focus().toggleHeading({ level: 1 }).run(), editor.isActive('heading', { level: 1 }), 'Heading 1'),
          tb('H2', () => editor.chain().focus().toggleHeading({ level: 2 }).run(), editor.isActive('heading', { level: 2 }), 'Heading 2'),
          tb('H3', () => editor.chain().focus().toggleHeading({ level: 3 }).run(), editor.isActive('heading', { level: 3 }), 'Heading 3'),
          sep(),
          tb('\u2022', () => editor.chain().focus().toggleBulletList().run(), editor.isActive('bulletList'), 'Bullet List'),
          tb('1.', () => editor.chain().focus().toggleOrderedList().run(), editor.isActive('orderedList'), 'Ordered List'),
          tb('\u21B6', () => editor.chain().focus().liftListItem('listItem').run(), false, 'Outdent'),
          tb('\u21B7', () => editor.chain().focus().sinkListItem('listItem').run(), false, 'Indent'),
          sep(),
          tb('\u275E', () => editor.chain().focus().toggleBlockquote().run(), editor.isActive('blockquote'), 'Blockquote'),
          tb('\u2015', () => editor.chain().focus().setHorizontalRule().run(), false, 'Horizontal Rule'),
          sep(),
          tb('\u{1F517}', () => {
            const url = window.prompt('Enter URL:')
            if (url) editor.chain().focus().setLink({ href: url }).run()
          }, editor.isActive('link'), 'Link'),
          tb('\u{1F5BC}', () => {
            const url = window.prompt('Enter image URL:')
            if (url) editor.chain().focus().setImage({ src: url }).run()
          }, false, 'Image'),
          tb('\u25B6', () => {
            const url = window.prompt('Enter YouTube URL:')
            if (url) editor.chain().focus().setYoutubeVideo({ src: url }).run()
          }, false, 'Video'),
          sep(),
          tb('\u2715', () => editor.chain().focus().clearNodes().unsetAllMarks().run(), false, 'Remove Format'),
        ])
    : null

  return React.createElement('div', {
    className: 'rhiz-wrap',
    style: { ...(style || {}) },
  },
    toolbar,
    React.createElement(EditorContent, { editor, className: 'rhiz-ed-wrap' }),
    React.createElement('style', null, `
      .rhiz-wrap {
        border: 1px solid #d0d5dd;
        border-radius: 8px;
        overflow: hidden;
        background: #fff;
      }
      .rtb-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 1px;
        padding: 6px 8px;
        background: #f9fafb;
        border-bottom: 1px solid #eaecf0;
      }
      .rtb {
        padding: 3px 7px;
        border: 1px solid transparent;
        border-radius: 4px;
        background: transparent;
        cursor: pointer;
        font-size: 12.5px;
        line-height: 1.5;
        color: #344054;
        min-width: 26px;
        text-align: center;
        font-family: system-ui, sans-serif;
      }
      .rtb:hover {
        background: #eaecf0;
        border-color: #d0d5dd;
      }
      .rtb.active {
        background: #e0f2fe;
        border-color: #7dd3fc;
        color: #0369a1;
      }
      .rtb-sep {
        width: 1px;
        background: #d0d5dd;
        margin: 2px 4px;
        align-self: stretch;
      }
      .rhiz-ed-wrap .ProseMirror {
        min-height: ${height || '320px'};
        padding: 12px 14px;
        outline: none;
        cursor: text;
        font-size: 15px;
        line-height: 1.7;
      }
      .rhiz-ed-wrap .ProseMirror p { margin: 0.3em 0; }
      .rhiz-ed-wrap .ProseMirror h1 { font-size: 1.5em; font-weight: 700; margin: 0.5em 0; }
      .rhiz-ed-wrap .ProseMirror h2 { font-size: 1.25em; font-weight: 600; margin: 0.4em 0; }
      .rhiz-ed-wrap .ProseMirror h3 { font-size: 1.1em; font-weight: 600; margin: 0.3em 0; }
      .rhiz-ed-wrap .ProseMirror ul, .rhiz-ed-wrap .ProseMirror ol { padding-left: 1.5em; }
      .rhiz-ed-wrap .ProseMirror blockquote {
        border-left: 3px solid #d0d5dd;
        padding-left: 1em;
        margin: 0.5em 0;
        color: #667085;
      }
      .rhiz-ed-wrap .ProseMirror hr { border: none; border-top: 1px solid #eaecf0; margin: 1em 0; }
      .rhiz-ed-wrap .ProseMirror img { max-width: 100%; height: auto; border-radius: 6px; margin: 0.5em 0; }
      .rhiz-ed-wrap .ProseMirror a { color: #2563eb; text-decoration: underline; cursor: pointer; }
      .rhiz-ed-wrap .ProseMirror iframe { max-width: 100%; border-radius: 6px; margin: 0.5em 0; }
    `)
  )
}

export default RhizTiptapEditor