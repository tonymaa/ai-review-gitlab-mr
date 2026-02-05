/**
 * 系统评论项组件
 */

import { FC } from 'react'
import { Typography, Tag, Tooltip } from 'antd'
import type { DiscussionNote } from '../../../types'

const { Text } = Typography

interface SystemCommentItemProps {
  note: DiscussionNote
  formatFullTime: (dateString: string) => string
  formatTimeAgo: (dateString: string) => string
}

const formatSystemNote = (body: string, authorName: string) => {
  let content = body
  if (content.startsWith(authorName)) {
    content = content.slice(authorName.length).trim()
  }

  const parts = content.split(/(@[\w-]+)/g)
  const formattedParts = parts.map((part, index) => {
    if (part.startsWith('@')) {
      return <Tag key={index} color="blue" style={{ fontSize: 11, margin: '0 2px' }}>{part}</Tag>
    }
    return part
  })

  return (
    <>
      <Text strong style={{ color: '#ccc' }}>{authorName}</Text>
      {' '}
      {formattedParts}
    </>
  )
}

const SystemCommentItem: FC<SystemCommentItemProps> = ({ note, formatFullTime, formatTimeAgo }) => {
  return (
    <div style={{
      padding: '8px 12px',
      margin: '8px 0',
      background: '#2a2a2a',
      borderRadius: 4,
      fontSize: 12,
      color: '#999',
      border: '1px solid #3a3a3a',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    }}>
      <span style={{ flex: 1 }}>
        {formatSystemNote(note.body, note.author.name)}
      </span>
      <Tooltip title={formatFullTime(note.created_at)}>
        <span style={{ fontSize: 11, color: '#666' }}>
          {formatTimeAgo(note.created_at)}
        </span>
      </Tooltip>
    </div>
  )
}

export default SystemCommentItem
