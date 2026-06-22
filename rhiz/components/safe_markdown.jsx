import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeUnwrapImages from 'rehype-unwrap-images'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'

const SafeMarkdown = ({ content, className, style }) => {
  return React.createElement('div', {
    className: className || '',
    style: style || {}
  },
    React.createElement(ReactMarkdown, {
      remarkPlugins: [remarkGfm, remarkMath],
      rehypePlugins: [rehypeRaw, rehypeUnwrapImages, [rehypeKatex, { strict: 'ignore' }]]
    }, content || '')
  )
}

export default SafeMarkdown
