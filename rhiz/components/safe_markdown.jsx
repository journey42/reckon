import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import rehypeUnwrapImages from 'rehype-unwrap-images'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'

// Sanitize user-authored HTML (rehype-raw passes raw HTML through, so without
// this a malicious concept/comment could inject <script>/onerror/javascript:
// and run in other users' browsers — incl. on the public debate pages).
// Runs AFTER rehype-raw (filters the parsed user HTML) but BEFORE rehype-katex,
// so KaTeX's own (trusted) output is generated afterward and not stripped.
// We extend the default schema to keep the app's legitimate rich content:
//   - className everywhere (lets remark-math's math nodes reach rehype-katex)
//   - <iframe> with http/https src (YouTube embeds)
//   - images are already allowed by the default schema (http/https)
// <script>, event handlers (on*), and javascript:/data: URLs remain blocked.
const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames || []), 'iframe'],
  attributes: {
    ...defaultSchema.attributes,
    '*': [...((defaultSchema.attributes && defaultSchema.attributes['*']) || []), 'className'],
    iframe: ['src', 'width', 'height', 'allow', 'allowFullScreen', 'frameBorder', 'title'],
  },
  protocols: {
    ...defaultSchema.protocols,
    src: ['http', 'https'],
  },
}

const SafeMarkdown = ({ content, className, style }) => {
  return React.createElement('div', {
    className: className || '',
    style: style || {}
  },
    React.createElement(ReactMarkdown, {
      remarkPlugins: [remarkGfm, remarkMath],
      rehypePlugins: [
        rehypeRaw,
        [rehypeSanitize, sanitizeSchema],
        rehypeUnwrapImages,
        [rehypeKatex, { strict: 'ignore' }],
      ]
    }, content || '')
  )
}

export default SafeMarkdown
