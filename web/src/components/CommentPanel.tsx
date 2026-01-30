/**
 * 评论面板组件
 */

import { FC, useState, useEffect } from 'react'
import { List, Avatar, Input, Button, Space, Typography, Tag, Empty, Spin, Tabs, Divider, message, Modal, Tooltip } from 'antd'
import {
  MessageOutlined,
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  EditOutlined,
  DeleteOutlined,
  CloseOutlined,
  CheckOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons'
import type { Note, ReviewComment } from '../types'
import { api } from '../api/client'
import { useApp } from '../contexts/AppContext'
import MRDetail from './MRDetail'

const { TextArea } = Input
const { Text, Paragraph } = Typography

interface CommentPanelProps {}

const CommentPanel: FC<CommentPanelProps> = () => {
  const {
    currentProject,
    currentMR,
    currentDiffFile,
    notes,
    setNotes,
    aiComments,
    setAiComments,
    loading,
    setLoading,
    jumpToLine,
    isReviewingAllFiles,
    setIsReviewingAllFiles,
    isReviewingSingleFile,
  } = useApp()

  const [commentInput, setCommentInput] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [aiReviewing, setAiReviewing] = useState(false)
  const [activeTab, setActiveTab] = useState('comments')
  const [editingAIComment, setEditingAIComment] = useState<{ index: number; content: string } | null>(null)
  const [sendingAIComment, setSendingAIComment] = useState<number | null>(null)
  const [aiSummarizing, setAiSummarizing] = useState(false)

  // 格式化完整时间为中国习惯格式
  const formatFullTime = (dateString: string) => {
    const date = new Date(dateString)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`
  }

  // 格式化相对时间
  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)

    const intervals = {
      年: 31536000,
      月: 2592000,
      周: 604800,
      天: 86400,
      小时: 3600,
      分钟: 60,
    }

    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
      const interval = Math.floor(seconds / secondsInUnit)
      if (interval >= 1) {
        return `${interval} ${unit}前`
      }
    }
    return '刚刚'
  }

  // 当 MR 变化时加载评论
  useEffect(() => {
    if (currentMR && currentProject) {
      loadNotes()
    } else {
      setNotes([])
    }
    // 清空 AI 评论
    setAiComments([])
  }, [currentMR, currentProject, setNotes, setAiComments])

  const loadNotes = async () => {
    if (!currentMR || !currentProject) return

    setLoading(true)
    try {
      const result = await api.getMergeRequestNotes(
        currentProject.id.toString(),
        currentMR.iid
      )
      setNotes(result)
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || '加载评论失败')
    } finally {
      setLoading(false)
    }
  }

  const handlePublishComment = async () => {
    if (!commentInput.trim() || !currentMR || !currentProject) {
      return
    }

    setPublishing(true)
    try {
      await api.createMergeRequestNote(
        currentProject.id.toString(),
        currentMR.iid,
        {
          body: commentInput,
          file_path: currentDiffFile?.new_path,
          line_number: undefined,
        }
      )

      message.success('评论已发布')
      setCommentInput('')
      // 重新加载评论
      await loadNotes()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '发布失败')
    } finally {
      setPublishing(false)
    }
  }

  const handleDeleteNote = async (noteId: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这条评论吗？',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        if (!currentMR || !currentProject) return

        try {
          await api.deleteMergeRequestNote(
            currentProject.id.toString(),
            currentMR.iid,
            noteId
          )
          message.success('评论已删除')
          await loadNotes()
        } catch (err: any) {
          message.error(err.response?.data?.detail || '删除失败')
        }
      }
    })
  }

  const handleDeleteAIComment = (index: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这条 AI 评论吗？',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        const updatedComments = aiComments.filter((_, i) => i !== index)
        setAiComments(updatedComments)
        message.success('AI 评论已删除')
      }
    })
  }

  const handleClearAIComments = () => {
    Modal.confirm({
      title: '确认清空',
      content: `确定要清空所有 AI 评论吗？共 ${aiComments.length} 条`,
      okText: '清空',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        setAiComments([])
        message.success('已清空所有 AI 评论')
      }
    })
  }

  const handleAIReview = async () => {
    if (!currentMR || !currentProject) {
      message.warning('请先选择一个 MR')
      return
    }

    setAiReviewing(true)
    setIsReviewingAllFiles(true)
    try {
      const result = await api.startReview(
        currentProject.id.toString(),
        currentMR.iid
      )

      // 轮询获取结果
      const pollResult = async () => {
        try {
          const status = await api.getReviewStatus(result.task_id)
          if ('status' in status && status.status === 'running') {
            // 继续轮询
            setTimeout(pollResult, 2000)
          } else if ('status' in status && status.status === 'completed') {
            // 完成
            setAiComments(status.comments)
            message.success(`AI 审查完成，生成 ${status.comments.length} 条评论`)
            setAiReviewing(false)
            setIsReviewingAllFiles(false)
          } else if ('status' in status && status.status === 'error') {
            // 错误
            message.error(status.error || 'AI 审查失败')
            setAiReviewing(false)
            setIsReviewingAllFiles(false)
          } else if ('comments' in status) {
            // 兼容旧格式（直接返回结果）
            setAiComments(status.comments)
            message.success(`AI 审查完成，生成 ${status.comments.length} 条评论`)
            setAiReviewing(false)
            setIsReviewingAllFiles(false)
          }
        } catch (err: any) {
          message.error(err.response?.data?.detail || err.message || '获取审查结果失败')
          setAiReviewing(false)
          setIsReviewingAllFiles(false)
        }
      }

      pollResult()
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'AI 审查失败')
      setAiReviewing(false)
      setIsReviewingAllFiles(false)
    }
  }

  // 开始编辑 AI 评论
  const handleStartEditAIComment = (index: number, content: string) => {
    setEditingAIComment({ index, content })
  }

  // 取消编辑 AI 评论
  const handleCancelEditAIComment = () => {
    setEditingAIComment(null)
  }

  // 保存 AI 评论修改
  const handleSaveAIComment = () => {
    if (editingAIComment) {
      const updatedComments = [...aiComments]
      updatedComments[editingAIComment.index] = {
        ...updatedComments[editingAIComment.index],
        content: editingAIComment.content,
      }
      setAiComments(updatedComments)
      setEditingAIComment(null)
      message.success('评论已更新')
    }
  }

  // AI 总结处理函数
  const handleAISummarize = async () => {
    if (!currentMR || !currentProject) {
      message.warning('请先选择一个 MR')
      return
    }

    setAiSummarizing(true)
    setCommentInput('') // 清空输入框，准备接收流式输出

    try {
      await api.summarizeChanges(
        currentProject.id.toString(),
        currentMR.iid,
        (chunk) => {
          setCommentInput((prev) => prev + chunk)
        }
      )
      message.success('AI 总结完成')
    } catch (err: any) {
      message.error(err.message || 'AI 总结失败')
    } finally {
      setAiSummarizing(false)
    }
  }

  // 发送 AI 评论到 GitLab
  const handleSendAIComment = async (comment: ReviewComment, index: number) => {
    if (!currentMR || !currentProject) {
      message.warning('请先选择一个 MR')
      return
    }

    setSendingAIComment(index)
    try {
      await api.createMergeRequestNote(
        currentProject.id.toString(),
        currentMR.iid,
        {
          body: comment.content,
          file_path: comment.file_path,
          line_number: comment.line_number,
        }
      )

      message.success('评论已发布到 GitLab')

      // 从 AI 评论列表中删除已发送的评论
      const updatedComments = aiComments.filter((_, i) => i !== index)
      setAiComments(updatedComments)

      // 重新加载评论到"评论"标签页
      await loadNotes()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '发布失败')
    } finally {
      setSendingAIComment(null)
    }
  }

  const getSeverityTag = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <Tag color="red">严重</Tag>
      case 'warning':
        return <Tag color="orange">警告</Tag>
      case 'suggestion':
        return <Tag color="blue">建议</Tag>
      default:
        return <Tag>{severity}</Tag>
    }
  }

  const renderNote = (note: Note) => {
    console.log("note>>", note);

    // System 类型的评论显示为系统活动样式
    if (note.system) {
      // 解析并格式化 system 评论内容
      const formatSystemNote = (body: string, authorName: string) => {
        // 检查 body 是否以 author_name 开头，如果是则去掉
        let content = body
        if (content.startsWith(authorName)) {
          content = content.slice(authorName.length).trim()
        }

        // 处理 @username 格式
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

      return (
        <div key={note.id} style={{
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
            {formatSystemNote(note.body, note.author_name)}
          </span>
          <Tooltip title={formatFullTime(note.created_at)}>
            <span style={{ fontSize: 11, color: '#666' }}>
              {formatTimeAgo(note.created_at)}
            </span>
          </Tooltip>
        </div>
      )
    }

    const canJump = note.file_path && note.line_number

    return (
      <div key={note.id} style={{
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
            src={note.author_avatar}
            icon={<UserOutlined />}
            size="small"
          />
          <Text strong style={{ fontSize: 13, color: '#ddd' }}>{note.author_name}</Text>
          <Tooltip title={formatFullTime(note.created_at)}>
            <Text type="secondary" style={{ fontSize: 11, color: '#999' }}>
              {formatTimeAgo(note.created_at)}
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
          {note.body}
        </Paragraph>

        {/* 底部：文件位置和操作按钮 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {canJump && (
            <Space size={4}>
              <Text type="secondary" style={{ fontSize: 11, color: '#999' }}>
                {note.file_path}:{note.line_number}
              </Text>
              <Button
                type="link"
                size="small"
                icon={<ArrowRightOutlined />}
                onClick={() => jumpToLine(note.file_path!, note.line_number!)}
                style={{ padding: 0, fontSize: 11, color: '#999' }}
              >
                跳转
              </Button>
            </Space>
          )}
          <Button
            type="text"
            size="small"
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteNote(note.id)}
            danger
            style={{ fontSize: 11 }}
          >
            删除
          </Button>
        </div>
      </div>
    )
  }

  const renderAIComment = (comment: ReviewComment, index: number) => {
    const isEditing = editingAIComment?.index === index
    const isSending = sendingAIComment === index
    const canJump = comment.file_path && comment.line_number

    return (
      <List.Item key={index} style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
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
                value={editingAIComment.content}
                onChange={(e) => setEditingAIComment({ ...editingAIComment, content: e.target.value })}
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
                    onClick={handleSaveAIComment}
                  >
                    保存
                  </Button>
                  <Button
                    size="small"
                    icon={<CloseOutlined />}
                    onClick={handleCancelEditAIComment}
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
                    onClick={() => handleSendAIComment(comment, index)}
                    loading={isSending}
                  >
                    发送
                  </Button>
                  <Button
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => handleStartEditAIComment(index, comment.content)}
                  >
                    编辑
                  </Button>
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => handleDeleteAIComment(index)}
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

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* MR 详情 */}
      {currentMR && currentProject && (
        <MRDetail
          project_id={currentProject.id.toString()}
          mr={currentMR}
          onRefresh={loadNotes}
        />
      )}

      {/* 头部：输入框和操作 */}
      <div style={{ padding: '12px', borderBottom: '1px solid #303030' }}>
        <TextArea
          placeholder="添加评论..."
          value={commentInput}
          onChange={(e) => setCommentInput(e.target.value)}
          autoSize={{ minRows: 2, maxRows: 4 }}
          style={{ marginBottom: 8 }}
          disabled={aiSummarizing}
        />
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handlePublishComment}
              loading={publishing}
              disabled={!commentInput.trim() || aiSummarizing}
              size="small"
            >
              发布
            </Button>
            <Button
              icon={<RobotOutlined />}
              onClick={handleAISummarize}
              loading={aiSummarizing}
              disabled={!currentMR || aiReviewing}
              size="small"
            >
              AI 总结
            </Button>
          </Space>
          <Button
            icon={<RobotOutlined />}
            onClick={handleAIReview}
            loading={aiReviewing}
            disabled={!currentMR || isReviewingSingleFile || aiSummarizing}
            size="small"
          >
            AI 审查全部文件
          </Button>
        </Space>
      </div>

      {/* 内容：Tab */}
      <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
        <Tabs
          className='comment-tab'
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
          items={[
            {
              key: 'comments',
              label: (
                <Space>
                  <MessageOutlined />
                  评论
                  {notes.length > 0 && <Tag>{notes.length}</Tag>}
                </Space>
              ),
              children: (
                <div style={{ height: '100%', overflowY: 'auto', overflowX: 'hidden', padding: '0 6px' }}>
                  <Spin spinning={loading}>
                    {notes.length === 0 ? (
                      <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="暂无评论"
                        style={{ marginTop: 60 }}
                      />
                    ) : (
                      <List
                        dataSource={notes}
                        renderItem={renderNote}
                        size="small"
                      />
                    )}
                  </Spin>
                </div>
              ),
            },
            {
              key: 'ai',
              label: (
                <Space>
                  <RobotOutlined />
                  AI 评论
                  {aiComments.length > 0 && <Tag>{aiComments.length}</Tag>}
                </Space>
              ),
              children: (
                <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  {aiComments.length > 0 && (
                    <div style={{ padding: '2px' }}>
                      <Button
                        style={{float: 'right'}}
                        type="text"
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={handleClearAIComments}
                        danger
                      >
                        清空所有 AI 评论
                      </Button>
                    </div>
                  )}
                  <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
                    {aiComments.length === 0 ? (
                      <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="点击 AI 审查 开始审查代码"
                        style={{ marginTop: 60 }}
                      />
                    ) : (
                      <List
                        dataSource={aiComments}
                        renderItem={renderAIComment}
                        size="small"
                      />
                    )}
                  </div>
                </div>
              ),
            },
          ]}
        />
      </div>
    </div>
  )
}

export default CommentPanel
