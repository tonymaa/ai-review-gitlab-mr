/**
 * 评论面板组件
 */

import { type FC, useState, useEffect } from 'react'
import { List, Input, Button, Space, Tag, Empty, Spin, Tabs, message, Modal, Tooltip } from 'antd'
import {
  MessageOutlined,
  SendOutlined,
  RobotOutlined,
  DeleteOutlined,
  ExpandOutlined,
  ShrinkOutlined,
} from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import type { Note, ReviewComment, Discussion } from '../types'
import { api } from '../api/client'
import { useApp } from '../contexts/AppContext'
import MRDetail from './MRDetail'
import { CommentItem, AICommentItem } from './atom/comment'

const { TextArea } = Input

type CommentPanelProps = object

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
  const [expandModalVisible, setExpandModalVisible] = useState(false)
  const [discussions, setDiscussions] = useState<Discussion[]>([])
  const [replyInputs, setReplyInputs] = useState<Record<string, string>>({})
  const [replying, setReplying] = useState<Record<string, boolean>>({})
  const [showReplyInput, setShowReplyInput] = useState<Record<string, boolean>>({})
  const [expandedReplies, setExpandedReplies] = useState<Record<string, boolean>>({})
  const [aiGenerating, setAiGenerating] = useState<Record<string, boolean>>({})

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
      setDiscussions([])
      setNotes([])
    }
    // 清空 AI 评论
    setAiComments([])
    // 清空评论输入框
    setCommentInput('')
  }, [currentMR, currentProject, setNotes, setAiComments])
  

  const loadNotes = async () => {
    if (!currentMR || !currentProject) return

    setLoading(true)
    try {
      // 只加载 discussions（包含主评论和回复）
      const discussionsResult = await api.getMergeRequestDiscussions(
        currentProject.id.toString(),
        currentMR.iid
      )
      // 按父评论创建时间降序排序（最新的在最上面）
      const sortedDiscussions = discussionsResult.sort((a, b) => {
        const aTime = new Date(a.notes[0]?.created_at || 0).getTime()
        const bTime = new Date(b.notes[0]?.created_at || 0).getTime()
        return bTime - aTime
      })
      setDiscussions(sortedDiscussions)
      // 同时加载 notes 用于系统评论等
      const notesResult = await api.getMergeRequestNotes(
        currentProject.id.toString(),
        currentMR.iid
      )
      setNotes(notesResult)
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || '加载评论失败')
    } finally {
      setLoading(false)
    }
  }

  // 获取某个 note 对应的 discussion ID
  const getDiscussionIdForNote = (noteId: number) => {
    const discussion = discussions.find(d => d.notes[0]?.id === noteId)
    return discussion?.id
  }

  // 发布回复
  const handlePublishReply = async (noteId: number) => {
    const discussionId = getDiscussionIdForNote(noteId)
    if (!discussionId || !replyInputs[noteId]?.trim() || !currentMR || !currentProject) {
      return
    }

    setReplying(prev => ({ ...prev, [noteId]: true }))
    try {
      await api.addDiscussionNote(
        currentProject.id.toString(),
        currentMR.iid,
        discussionId,
        replyInputs[noteId]
      )

      message.success('回复已发布')
      setReplyInputs(prev => ({ ...prev, [noteId]: '' }))
      // 重新加载评论
      await loadNotes()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '发布回复失败')
    } finally {
      setReplying(prev => ({ ...prev, [noteId]: false }))
    }
  }

  // AI 生成回复
  const handleGenerateAIReply = async (noteId: number, parentComment: string) => {
    if (!currentMR || !currentProject) {
      message.warning('请先选择一个 MR')
      return
    }

    setAiGenerating(prev => ({ ...prev, [noteId]: true }))
    try {
      const result = await api.generateAIReply(
        currentProject.id.toString(),
        currentMR.iid,
        parentComment
      )
      // 将生成的回复填入输入框
      setReplyInputs(prev => ({ ...prev, [noteId]: result.reply }))
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'AI 生成回复失败')
    } finally {
      setAiGenerating(prev => ({ ...prev, [noteId]: false }))
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
            const completedStatus = status as { status: 'completed'; comments: ReviewComment[] }
            setAiComments(completedStatus.comments)
            message.success(`AI 审查完成，生成 ${completedStatus.comments.length} 条评论`)
            setAiReviewing(false)
            setIsReviewingAllFiles(false)
          } else if ('status' in status && status.status === 'error') {
            // 错误
            const errorStatus = status as { status: 'error'; error: string }
            message.error(errorStatus.error || 'AI 审查失败')
            setAiReviewing(false)
            setIsReviewingAllFiles(false)
          } else if ('comments' in status) {
            // 兼容旧格式（直接返回结果）
            const reviewResponse = status as { comments: ReviewComment[] }
            setAiComments(reviewResponse.comments)
            message.success(`AI 审查完成，生成 ${reviewResponse.comments.length} 条评论`)
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

  // 渲染单个 discussion（包含主评论和回复）
  const renderDiscussion = (discussion: Discussion) => {
    const mainNote = discussion.notes[0]
    const showReplies = expandedReplies[mainNote.id]
    const showReplyInputFlag = showReplyInput[mainNote.id]

    return (
      <CommentItem
        key={discussion.id}
        discussion={discussion}
        formatFullTime={formatFullTime}
        formatTimeAgo={formatTimeAgo}
        jumpToLine={jumpToLine}
        onDelete={handleDeleteNote}
        showReplies={showReplies}
        showReplyInput={showReplyInputFlag}
        replyInput={replyInputs[mainNote.id] || ''}
        replying={replying[mainNote.id] || false}
        aiGenerating={aiGenerating[mainNote.id] || false}
        onToggleReplies={() => {
          setExpandedReplies(prev => ({ ...prev, [mainNote.id]: !prev[mainNote.id] }))
        }}
        onToggleReplyInput={() => {
          setShowReplyInput(prev => ({ ...prev, [mainNote.id]: !prev[mainNote.id] }))
        }}
        onReplyInputChange={(value) => {
          setReplyInputs(prev => ({ ...prev, [mainNote.id]: value }))
        }}
        onPublishReply={() => handlePublishReply(mainNote.id)}
        onGenerateAIReply={() => handleGenerateAIReply(mainNote.id, mainNote.body)}
      />
    )
  }

  // 渲染 AI 评论
  const renderAIComment = (comment: ReviewComment, index: number) => {
    const isEditing = editingAIComment?.index === index
    const isSending = sendingAIComment === index

    return (
      <AICommentItem
        key={index}
        comment={comment}
        index={index}
        isEditing={isEditing}
        isSending={isSending}
        editingContent={editingAIComment?.content || comment.content}
        formatFullTime={formatFullTime}
        formatTimeAgo={formatTimeAgo}
        jumpToLine={jumpToLine}
        onSend={() => handleSendAIComment(comment, index)}
        onEdit={() => handleStartEditAIComment(index, comment.content)}
        onDelete={() => handleDeleteAIComment(index)}
        onSaveEdit={handleSaveAIComment}
        onCancelEdit={handleCancelEditAIComment}
        onEditChange={(value) => setEditingAIComment({ index, content: value })}
        getSeverityTag={getSeverityTag}
      />
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
        <div style={{ position: 'relative', marginBottom: 8 }}>
          <TextArea
            placeholder="添加评论..."
            value={commentInput}
            onChange={(e) => setCommentInput(e.target.value)}
            autoSize={{ minRows: 2, maxRows: 4 }}
            disabled={aiSummarizing}
          />
          <Tooltip title="放大编辑">
            <Button
              type="text"
              size="small"
              icon={<ExpandOutlined />}
              onClick={() => setExpandModalVisible(true)}
              style={{
                position: 'absolute',
                right: 8,
                bottom: 8,
                zIndex: 1,
                opacity: 0.6,
              }}
            />
          </Tooltip>
        </div>
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
                    {discussions.length === 0 ? (
                      <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="暂无评论"
                        style={{ marginTop: 60 }}
                      />
                    ) : (
                      <List
                        dataSource={discussions}
                        renderItem={renderDiscussion}
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

      {/* 放大编辑模态框 */}
      <Modal
        title="编辑评论"
        open={expandModalVisible}
        onCancel={() => setExpandModalVisible(false)}
        onOk={() => setExpandModalVisible(false)}
        width={1200}
        styles={{ body: { padding: '16px 0' } }}
        footer={[]}
        closeIcon={<ShrinkOutlined />}
      >
        <div style={{ display: 'flex', gap: 16, height: 500 }}>
          {/* 左侧编辑区 */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>编辑 (Markdown)</div>
            <TextArea
              value={commentInput}
              onChange={(e) => setCommentInput(e.target.value)}
              style={{ flex: 1, resize: 'none' }}
              placeholder="在此输入评论内容，支持 Markdown 格式..."
              disabled={aiSummarizing}
            />
          </div>
          {/* 右侧预览区 */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ fontSize: 12, color: '#999', marginBottom: 8 }}>预览</div>
            <div style={{
              flex: 1,
              overflowY: 'auto',
              padding: 12,
              background: '#1f1f1f',
              borderRadius: 6,
              border: '1px solid #303030',
              fontSize: 14,
            }}>
              {commentInput ? (
                <ReactMarkdown>{commentInput}</ReactMarkdown>
              ) : (
                <div style={{ color: '#666', fontStyle: 'italic' }}>暂无内容，在左侧输入以预览...</div>
              )}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default CommentPanel
