/**
 * 评论面板组件
 */

import { FC, useState, useEffect } from 'react'
import { List, Avatar, Input, Button, Space, Typography, Tag, Empty, Spin, Tabs, Divider, message } from 'antd'
import {
  MessageOutlined,
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import type { Note, ReviewComment } from '../types'
import { api } from '../api/client'
import { useApp } from '../contexts/AppContext'

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
  } = useApp()

  const [commentInput, setCommentInput] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [aiReviewing, setAiReviewing] = useState(false)
  const [activeTab, setActiveTab] = useState('comments')

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
    } catch (err) {
      console.error('Failed to load notes:', err)
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

  const handleAIReview = async () => {
    if (!currentMR || !currentProject) {
      message.warning('请先选择一个 MR')
      return
    }

    setAiReviewing(true)
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
          }
        } catch (err) {
          console.error('Failed to poll result:', err)
          setAiReviewing(false)
        }
      }

      pollResult()
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'AI 审查失败')
      setAiReviewing(false)
    }
  }

  const handleAIReviewCurrentFile = async () => {
    if (!currentMR || !currentProject || !currentDiffFile) {
      message.warning('请先选择一个 MR 和文件')
      return
    }

    setAiReviewing(true)
    try {
      const result = await api.reviewSingleFile(
        currentProject.id.toString(),
        currentMR.iid,
        currentDiffFile.new_path
      )

      setAiComments(result.comments)
      message.success(`AI 审查完成，生成 ${result.comments.length} 条评论`)
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'AI 审查失败')
    } finally {
      setAiReviewing(false)
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

  const renderNote = (note: Note) => (
    <List.Item key={note.id}>
      <List.Item.Meta
        avatar={
          <Avatar
            src={note.author_avatar}
            icon={<UserOutlined />}
            size="small"
          />
        }
        title={
          <Space>
            <Text strong>{note.author_name}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {new Date(note.created_at).toLocaleString()}
            </Text>
          </Space>
        }
        description={
          <div>
            <Paragraph
              style={{ marginBottom: 8, whiteSpace: 'pre-wrap' }}
              ellipsis={{ rows: 6, expandable: true, symbol: '展开' }}
            >
              {note.body}
            </Paragraph>
            {!note.system && (
              <Space>
                <Button
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => handleDeleteNote(note.id)}
                >
                  删除
                </Button>
              </Space>
            )}
          </div>
        }
      />
    </List.Item>
  )

  const renderAIComment = (comment: ReviewComment, index: number) => (
    <List.Item key={index}>
      <List.Item.Meta
        avatar={
          <Avatar
            icon={<RobotOutlined />}
            size="small"
            style={{ background: '#1677ff' }}
          />
        }
        title={
          <Space>
            <Text strong>AI 审查</Text>
            {getSeverityTag(comment.severity)}
            {comment.file_path && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {comment.file_path}
                {comment.line_number && `:${comment.line_number}`}
              </Text>
            )}
          </Space>
        }
        description={
          <Paragraph
            style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}
            ellipsis={{ rows: 4, expandable: true, symbol: '展开' }}
          >
            {comment.content}
          </Paragraph>
        }
      />
    </List.Item>
  )

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* 头部：输入框和操作 */}
      <div style={{ padding: '12px', borderBottom: '1px solid #303030' }}>
        <TextArea
          placeholder="添加评论..."
          value={commentInput}
          onChange={(e) => setCommentInput(e.target.value)}
          autoSize={{ minRows: 2, maxRows: 4 }}
          style={{ marginBottom: 8 }}
        />
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handlePublishComment}
            loading={publishing}
            disabled={!commentInput.trim()}
            size="small"
          >
            发布
          </Button>
          <Button
            icon={<RobotOutlined />}
            onClick={handleAIReview}
            loading={aiReviewing}
            disabled={!currentMR}
            size="small"
          >
            AI 审查
          </Button>
          <Button
            icon={<RobotOutlined />}
            onClick={handleAIReviewCurrentFile}
            loading={aiReviewing}
            disabled={!currentDiffFile}
            size="small"
          >
            AI 审查当前文件
          </Button>
        </Space>
      </div>

      {/* 内容：Tab */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
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
                <div style={{ height: 'calc(100% - 46px)', overflow: 'auto' }}>
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
                <div style={{ height: 'calc(100% - 46px)', overflow: 'auto' }}>
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
              ),
            },
          ]}
        />
      </div>
    </div>
  )
}

export default CommentPanel
