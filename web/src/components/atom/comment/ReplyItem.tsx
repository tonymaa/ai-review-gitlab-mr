/**
 * 回复项组件
 */

import { FC } from 'react'
import { Avatar, Tooltip, Typography } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import type { DiscussionNote } from '../../../types'

const { Text, Paragraph } = Typography

interface ReplyItemProps {
  reply: DiscussionNote
  formatFullTime: (dateString: string) => string
  formatTimeAgo: (dateString: string) => string
}

const ReplyItem: FC<ReplyItemProps> = ({ reply, formatFullTime, formatTimeAgo }) => {
  return (
    <div style={{
      padding: '8px',
      background: '#1f1f1f',
      borderRadius: 4,
      border: '1px solid #2a2a2a',
      display: 'flex',
      flexDirection: 'column',
      gap: '4px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        <Avatar
          src={reply.author.avatar_url}
          icon={<UserOutlined />}
          size={20}
        />
        <Text strong style={{ fontSize: 12, color: '#ddd' }}>{reply.author.name}</Text>
        <Tooltip title={formatFullTime(reply.created_at)}>
          <Text type="secondary" style={{ fontSize: 10, color: '#999' }}>
            {formatTimeAgo(reply.created_at)}
          </Text>
        </Tooltip>
      </div>
      <Paragraph style={{
        fontSize: 12,
        color: '#d9d9d9',
        marginBottom: 0
      }}>
        {reply.body}
      </Paragraph>
    </div>
  )
}

export default ReplyItem
