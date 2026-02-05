/**
 * AI评论项组件
 */

import { FC } from 'react'
import { Avatar, Button, Input, Space, Tag, Tooltip, Typography, List } from 'antd'
import { ArrowRightOutlined, CheckOutlined, CloseOutlined, EditOutlined, DeleteOutlined, SendOutlined, RobotOutlined } from '@ant-design/icons'
import type { ReviewComment } from '../../../types'

const { TextArea } = Input
const { Text, Paragraph } = Typography

interface AICommentItemProps {
  comment: ReviewComment
  index: number
  isEditing: boolean
  isSending: boolean
  editingContent: string
  formatFullTime: (dateString: string) => string
  formatTimeAgo: (dateString: string) => string
  jumpToLine: (filePath: string, lineNumber: number) => void
  onSend: () => void
  onEdit: () => void
  onDelete: () => void
  onSaveEdit: () => void
  onCancelEdit: () => void
  onEditChange: (value: string) => void
  getSeverityTag: (severity: string) => React.ReactNode
}

const AICommentItem: FC<AICommentItemProps> = ({
  comment,
  index,
  isEditing,
  isSending,
  editingContent,
  formatFullTime,
  formatTimeAgo,
  jumpToLine,
  onSend,
  onEdit,
  onDelete,
  onSaveEdit,
  onCancelEdit,
  onEditChange,
  getSeverityTag,
}) => {
  const canJump = comment.file_path && comment.line_number

  return (
    <List.Item style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
      <div style={{ width: '100%', display: 'flex', gap: 8 }}>
        <Avatar
          icon={<RobotOutlined />}
          size="small"
          style={{ background: '#1677ff', flexShrink: 0 }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* 标题栏 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <Space size="small">
              {getSeverityTag(comment.severity)}
              {comment.file_path && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {comment.file_path}
                  {comment.line_number && `:${comment.line_number}`}
                </Text>
              )}
            </Space>
            {canJump && (
              <Button
                type="link"
                size="small"
                icon={<ArrowRightOutlined />}
                onClick={() => jumpToLine(comment.file_path!, comment.line_number!)}
                style={{ padding: 0, fontSize: 12 }}
              >
                跳转
              </Button>
            )}
          </div>

          {/* 内容区域 */}
          {isEditing ? (
            <TextArea
              value={editingContent}
              onChange={(e) => onEditChange(e.target.value)}
              autoSize={{ minRows: 2, maxRows: 8 }}
              style={{ marginBottom: 8, fontSize: 13 }}
            />
          ) : (
            <Paragraph
              style={{ marginBottom: 8, whiteSpace: 'pre-wrap', fontSize: 13 }}
              ellipsis={{ rows: 4, expandable: true, symbol: '展开' }}
            >
              {comment.content}
            </Paragraph>
          )}

          {/* 操作按钮 */}
          <Space size="small">
            {isEditing ? (
              <>
                <Button
                  type="primary"
                  size="small"
                  icon={<CheckOutlined />}
                  onClick={onSaveEdit}
                >
                  保存
                </Button>
                <Button
                  size="small"
                  icon={<CloseOutlined />}
                  onClick={onCancelEdit}
                >
                  取消
                </Button>
              </>
            ) : (
              <>
                <Button
                  type="primary"
                  size="small"
                  icon={<SendOutlined />}
                  onClick={onSend}
                  loading={isSending}
                >
                  发送
                </Button>
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={onEdit}
                >
                  编辑
                </Button>
                <Button
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={onDelete}
                  danger
                >
                  删除
                </Button>
              </>
            )}
          </Space>
        </div>
      </div>
    </List.Item>
  )
}

export default AICommentItem
