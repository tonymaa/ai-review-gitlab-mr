/**
 * 评论项组件（包含主评论和回复）
 */

import { FC } from 'react'
import { Avatar, Button, Input, Menu, Space, Tooltip, Typography } from 'antd'
import { ArrowRightOutlined, DeleteOutlined, UserOutlined } from '@ant-design/icons'
import type { Discussion } from '../../../types'
import ReplyItem from './ReplyItem'
import SystemCommentItem from './SystemCommentItem'

const { TextArea } = Input
const { Text, Paragraph } = Typography

interface CommentItemProps {
  discussion: Discussion
  formatFullTime: (dateString: string) => string
  formatTimeAgo: (dateString: string) => string
  jumpToLine: (filePath: string, lineNumber: number) => void
  onDelete: (noteId: number) => void
  showReplies: boolean
  showReplyInput: boolean
  replyInput: string
  replying: boolean
  onToggleReplies: () => void
  onToggleReplyInput: () => void
  onReplyInputChange: (value: string) => void
  onPublishReply: () => void
}

const CommentItem: FC<CommentItemProps> = ({
  discussion,
  formatFullTime,
  formatTimeAgo,
  jumpToLine,
  onDelete,
  showReplies,
  showReplyInput,
  replyInput,
  replying,
  onToggleReplies,
  onToggleReplyInput,
  onReplyInputChange,
  onPublishReply,
}) => {
  const mainNote = discussion.notes[0]
  const replies = discussion.notes.slice(1)
  const hasReplies = replies.length > 0

  // 系统评论样式
  if (mainNote.system) {
    return <SystemCommentItem note={mainNote} formatFullTime={formatFullTime} formatTimeAgo={formatTimeAgo} />
  }

  // 获取文件位置信息
  const position = mainNote.position
  const canJump = position && (position.new_path || position.old_path) && (position.new_line || position.old_line)
  const filePath = position?.new_path || position?.old_path
  const lineNumber = position?.new_line || position?.old_line

  return (
    <div style={{
      padding: '12px',
      margin: '8px 0',
      background: '#2a2a2a',
      borderRadius: 4,
      fontSize: 12,
      border: '1px solid #3a3a3a',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px'
    }}>
      {/* 头部：作者信息和时间 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Avatar
          src={mainNote.author.avatar_url}
          icon={<UserOutlined />}
          size="small"
        />
        <Text strong style={{ fontSize: 13, color: '#ddd' }}>{mainNote.author.name}</Text>
        <Tooltip title={formatFullTime(mainNote.created_at)}>
          <Text type="secondary" style={{ fontSize: 11, color: '#999' }}>
            {formatTimeAgo(mainNote.created_at)}
          </Text>
        </Tooltip>
      </div>

      {/* 评论内容 */}
      <Paragraph
        style={{
          fontSize: 13,
          color: '#d9d9d9',
          marginBottom: 0
        }}
        ellipsis={{ rows: 3, expandable: 'collapsible' }}
      >
        {mainNote.body}
      </Paragraph>

      {/* 底部：文件位置和操作按钮 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space size={4}>
          {canJump && (
            <>
              <Text type="secondary" style={{ fontSize: 11, color: '#999' }}>
                {filePath}:{lineNumber}
              </Text>
              <Button
                type="link"
                size="small"
                icon={<ArrowRightOutlined />}
                onClick={() => jumpToLine(filePath!, lineNumber!)}
                style={{ padding: 0, fontSize: 11, color: '#999' }}
              >
                跳转
              </Button>
            </>
          )}
          {hasReplies && (
            <Button
              type="link"
              size="small"
              onClick={onToggleReplies}
              style={{ padding: 0, fontSize: 11, color: '#999' }}
            >
              {showReplies ? '收起回复' : `展开回复 (${replies.length})`}
            </Button>
          )}
        </Space>
        <Space size={4}>
          <Button
            type="text"
            size="small"
            onClick={onToggleReplyInput}
            style={{ fontSize: 11 }}
          >
            回复
          </Button>
          <Button
            type="text"
            size="small"
            icon={<DeleteOutlined />}
            onClick={() => onDelete(mainNote.id)}
            danger
            style={{ fontSize: 11 }}
          >
            删除
          </Button>
        </Space>
      </div>

      {/* 回复列表 */}
      {showReplies && hasReplies && (
        <div style={{ marginLeft: '32px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {replies.map((reply) => (
            <ReplyItem
              key={reply.id}
              reply={reply}
              formatFullTime={formatFullTime}
              formatTimeAgo={formatTimeAgo}
            />
          ))}
        </div>
      )}

      {/* 回复输入框 */}
      {showReplyInput && (
        <div style={{ marginLeft: '32px', marginTop: '8px' }}>
          <Space.Compact style={{ width: '100%', gap: '5px', alignItems: 'start', flexDirection:'column' }}>
            <TextArea
              placeholder="写回复..."
              value={replyInput}
              onChange={(e) => onReplyInputChange(e.target.value)}
              autoSize={{ minRows: 1, maxRows: 4 }}
              onPressEnter={(e) => {
                if (!e.shiftKey) {
                  e.preventDefault()
                  onPublishReply()
                }
              }}
              style={{ fontSize: 12 }}
            />
            <Button
              type="primary"
              size="small"
              onClick={onPublishReply}
              loading={replying}
              disabled={!replyInput.trim()}
            >
              发送
            </Button>
          </Space.Compact>
        </div>
      )}
    </div>
  )
}

export default CommentItem
