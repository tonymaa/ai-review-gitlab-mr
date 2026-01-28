/**
 * Diff 查看器组件
 */

import { type FC, useMemo, useEffect, useRef, useState } from 'react'
import { List, Empty, Typography, Space, Input, Popover, Button, message, Tag } from 'antd'
import {
  FileOutlined,
  PlusOutlined,
  MinusOutlined,
  ArrowRightOutlined,
  CommentOutlined,
  RobotOutlined,
  EditOutlined,
  DeleteOutlined,
  CloseOutlined,
  CheckOutlined,
  SendOutlined,
} from '@ant-design/icons'
import type { DiffFile, ReviewComment } from '../types'
import { useApp } from '../contexts/AppContext'
import { api } from '../api/client'

const { Text } = Typography

interface DiffViewerProps {
  diffFile: DiffFile | null
  diffLines: Array<{
    type: 'addition' | 'deletion' | 'context' | 'header'
    oldNumber?: number
    newNumber?: number
    content: string
  }>
  fileList: DiffFile[]
  selectedFile: DiffFile | null
  onSelectFile: (file: DiffFile) => void
  aiComments?: ReviewComment[]
}

const DiffViewer: FC<DiffViewerProps> = ({
  diffFile,
  diffLines,
  fileList,
  selectedFile,
  onSelectFile,
  aiComments = [],
}) => {
  const {
    setCurrentDiffFile,
    highlightLine,
    setHighlightLine,
    currentProject,
    currentMR,
    setNotes,
    setAiComments,
    isReviewingAllFiles,
    setIsReviewingSingleFile,
  } = useApp()
  const diffContainerRef = useRef<HTMLDivElement>(null)

  // 行内评论状态
  const [commentLineId, setCommentLineId] = useState<string | null>(null)
  const [commentInput, setCommentInput] = useState('')
  const [submittingComment, setSubmittingComment] = useState(false)

  // AI 评论编辑状态
  const [editingAIComment, setEditingAIComment] = useState<{
    comment: ReviewComment
    content: string
  } | null>(null)
  const [sendingAIComment, setSendingAIComment] = useState<string | null>(null)

  // AI 审查状态 - 使用 Set 支持多个文件同时审查
  const [reviewingFiles, setReviewingFiles] = useState<Set<string>>(new Set())

  // AI 审查当前文件
  const handleReviewFile = async (file: DiffFile) => {
    if (!currentProject || !currentMR) {
      message.warning('请先选择一个 MR')
      return
    }

    // 添加到正在审查的文件集合
    setReviewingFiles(prev => new Set(prev).add(file.new_path))
    setIsReviewingSingleFile(true)
    try {
      const result = await api.reviewSingleFile(
        currentProject.id.toString(),
        currentMR.iid,
        file.new_path
      )

      // 只移除当前文件的旧评论，添加新评论，保留其他文件的评论
      // 使用函数式更新避免并发时的竞态条件
      setAiComments(prev => [
        ...prev.filter(c => c.file_path !== file.new_path),
        ...result.comments
      ])
      message.success(`AI 审查完成，生成 ${result.comments.length} 条评论`)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      message.error(error.response?.data?.detail || 'AI 审查失败')
    } finally {
      // 从正在审查的文件集合中移除
      setReviewingFiles(prev => {
        const next = new Set(prev)
        next.delete(file.new_path)
        return next
      })
      setIsReviewingSingleFile(false)
    }
  }

  // 当高亮行变化时，滚动到对应行
  useEffect(() => {
    if (highlightLine && diffFile && diffFile.new_path === highlightLine.filePath && diffContainerRef.current) {
      // 找到对应的行
      const targetLine = diffLines.find(line =>
        (line.newNumber === highlightLine.lineNumber || line.oldNumber === highlightLine.lineNumber)
      )
      if (targetLine) {
        const lineIndex = diffLines.indexOf(targetLine)
        // 计算滚动位置（每行高度约20px）
        const scrollPosition = lineIndex * 20
        diffContainerRef.current.scrollTop = scrollPosition
      }
      // 3秒后清除高亮
      const timer = setTimeout(() => {
        setHighlightLine(null)
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [highlightLine, diffFile, diffLines, setHighlightLine])

  // 调试：查看接收到的 props
  useEffect(() => {
    console.log('DiffViewer props:', {
      hasDiffFile: !!diffFile,
      diffFilePath: diffFile?.new_path,
      diffLength: diffFile?.diff?.length,
      diffLinesCount: diffLines.length,
      fileListLength: fileList.length,
    })
  }, [diffFile, diffLines, fileList])

  // 统计增删行数
  const stats = useMemo(() => {
    if (!diffFile) return { additions: 0, deletions: 0 }
    return {
      additions: diffLines.filter(l => l.type === 'addition').length,
      deletions: diffLines.filter(l => l.type === 'deletion').length,
    }
  }, [diffFile, diffLines])

  const renderLine = (line: typeof diffLines[number], index: number) => {
    const isHeader = line.type === 'header'
    // 检查是否是高亮行（只高亮修改行，不包括上下文行）
    const isHighlighted = highlightLine && diffFile &&
      (line.type === 'addition' || line.type === 'deletion') &&
      ((line.newNumber === highlightLine.lineNumber && line.newNumber) ||
       (line.oldNumber === highlightLine.lineNumber && line.oldNumber))

    // 生成行的唯一ID
    const lineId = `${diffFile?.new_path}-${index}-${line.oldNumber}-${line.newNumber}`
    const isCommenting = commentLineId === lineId

    // 发送行内评论
    const handleSubmitComment = async () => {
      if (!commentInput.trim() || !diffFile || !currentProject || !currentMR) return

      setSubmittingComment(true)
      try {
        await api.createMergeRequestNote(
          currentProject.id.toString(),
          currentMR.iid,
          {
            body: commentInput,
            file_path: diffFile.new_path,
            line_number: line.newNumber || line.oldNumber,
          }
        )
        message.success('评论已发布')
        setCommentInput('')
        setCommentLineId(null)

        // 重新加载评论列表
        try {
          const notes = await api.getMergeRequestNotes(
            currentProject.id.toString(),
            currentMR.iid
          )
          setNotes(notes)
        } catch (loadErr) {
          console.error('重新加载评论失败:', loadErr)
        }
      } catch (err) {
        const error = err as { response?: { data?: { detail?: string } } }
        message.error(error.response?.data?.detail || '发送评论失败')
      } finally {
        setSubmittingComment(false)
      }
    }

    // 评论输入框内容
    const commentContent = (
      <div style={{ width: 300 }}>
        <Input.TextArea
          value={commentInput}
          onChange={(e) => setCommentInput(e.target.value)}
          placeholder="输入评论..."
          autoSize={{ minRows: 3, maxRows: 6 }}
          onPressEnter={(e) => {
            if (e.shiftKey) return
            e.preventDefault()
            handleSubmitComment()
          }}
        />
        <div style={{ marginTop: 8, textAlign: 'right' }}>
          <Space>
            <Button size="small" onClick={() => setCommentLineId(null)}>
              取消
            </Button>
            <Button
              type="primary"
              size="small"
              onClick={handleSubmitComment}
              loading={submittingComment}
              disabled={!commentInput.trim()}
            >
              发送
            </Button>
          </Space>
        </div>
      </div>
    )

    // 只有修改行（新增或删除）才能添加评论
    const canAddComment = !isHeader && (line.type === 'addition' || line.type === 'deletion')

    return (
      <div
        key={index}
        className={`diff-line ${line.type}`}
        style={{
          display: 'flex',
          fontFamily: 'Consolas, Monaco, "Courier New", monospace',
          fontSize: 13,
          lineHeight: '20px',
          whiteSpace: 'pre',
          backgroundColor: isHighlighted
            ? '#ffec3d26'
            : line.type === 'addition'
              ? 'rgba(82, 196, 26, 0.15)'
              : line.type === 'deletion'
                ? 'rgba(255, 77, 79, 0.15)'
                : 'transparent',
          position: 'relative',
        }}
        onMouseEnter={(e) => {
          // 悬停时显示评论图标
          const iconArea = (e.currentTarget as HTMLElement).querySelector('.comment-icon-area')
          if (iconArea && !isCommenting) {
            (iconArea as HTMLElement).style.opacity = '1'
          }
        }}
        onMouseLeave={(e) => {
          // 离开时隐藏评论图标（除非正在编辑）
          if (!isCommenting) {
            const iconArea = (e.currentTarget as HTMLElement).querySelector('.comment-icon-area')
            if (iconArea) {
              (iconArea as HTMLElement).style.opacity = '0'
            }
          }
        }}
      >
        {/* 评论图标 */}
        {canAddComment && (
          <div
            className="comment-icon-area"
            style={{
              position: 'absolute',
              left: '-5px',
              top: '1px',
              width: 30,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              opacity: isCommenting ? 1 : 0,
              transition: 'opacity 0.2s',
            }}
          >
            <Popover
              content={commentContent}
              title="添加行内评论"
              trigger="click"
              open={isCommenting}
              onOpenChange={(open) => {
                if (open) {
                  setCommentLineId(lineId)
                } else if (commentLineId === lineId) {
                  setCommentLineId(null)
                  setCommentInput('')
                }
              }}
            >
              <CommentOutlined style={{ cursor: 'pointer', color: '#1677ff' }} />
            </Popover>
          </div>
        )}

        {/* 行号 */}
        <div style={{
          width: 50,
          textAlign: 'right',
          paddingRight: 10,
          color: '#737373',
          userSelect: 'none',
          flexShrink: 0,
        }}>
          {line.oldNumber ?? line.newNumber ?? ''}
        </div>

        {/* 另一侧行号 */}
        <div style={{
          width: 50,
          textAlign: 'right',
          paddingRight: 10,
          color: '#737373',
          userSelect: 'none',
          flexShrink: 0,
        }}>
          {line.newNumber ?? line.oldNumber ?? ''}
        </div>

        {/* 标记 */}
        <div style={{
          width: 20,
          flexShrink: 0,
          color: line.type === 'addition' ? '#52c41a' : line.type === 'deletion' ? '#ff4d4f' : '#888',
        }}>
          {line.type === 'addition' && '+'}
          {line.type === 'deletion' && '-'}
          {line.type === 'context' && ' '}
          {line.type === 'header' && ' '}
        </div>

        {/* 内容 */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          color: isHeader ? '#888' : '#d4d4d4',
        }}>
          {line.content}
        </div>
      </div>
    )
  }

  const getFileIcon = (file: DiffFile) => {
    if (file.new_file) return <PlusOutlined style={{ color: '#52c41a' }} />
    if (file.deleted_file) return <MinusOutlined style={{ color: '#ff4d4f' }} />
    if (file.renamed_file) return <ArrowRightOutlined style={{ color: '#faad14' }} />
    return <FileOutlined />
  }

  // 获取指定行的 AI 评论
  const getAICommentsForLine = (lineNumber: number | undefined) => {
    if (!lineNumber || !diffFile) return []
    return aiComments.filter(
      comment => comment.file_path === diffFile.new_path && comment.line_number === lineNumber
    )
  }

  // AI 评论操作函数
  const handleDeleteAIComment = (comment: ReviewComment) => {
    const updatedComments = aiComments.filter(c =>
      !(c.file_path === comment.file_path && c.line_number === comment.line_number && c.content === comment.content)
    )
    setAiComments(updatedComments)
    message.success('AI 评论已删除')
  }

  const handleSendAIComment = async (comment: ReviewComment) => {
    if (!currentProject || !currentMR) {
      message.warning('请先选择一个 MR')
      return
    }

    const commentKey = `${comment.file_path}-${comment.line_number}-${comment.content.slice(0, 20)}`
    setSendingAIComment(commentKey)
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
      // 删除已发送的评论
      handleDeleteAIComment(comment)
      // 重新加载评论
      const notes = await api.getMergeRequestNotes(
        currentProject.id.toString(),
        currentMR.iid
      )
      setNotes(notes)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      message.error(error.response?.data?.detail || '发布失败')
    } finally {
      setSendingAIComment(null)
    }
  }

  const handleStartEditAIComment = (comment: ReviewComment) => {
    setEditingAIComment({ comment, content: comment.content })
  }

  const handleCancelEditAIComment = () => {
    setEditingAIComment(null)
  }

  const handleSaveAIComment = () => {
    if (!editingAIComment) return
    const updatedComments = aiComments.map(c =>
      c.file_path === editingAIComment.comment.file_path &&
      c.line_number === editingAIComment.comment.line_number &&
      c.content === editingAIComment.comment.content
        ? { ...c, content: editingAIComment.content }
        : c
    )
    setAiComments(updatedComments)
    setEditingAIComment(null)
    message.success('评论已更新')
  }

  // 渲染 AI 评论
  const renderAIComment = (comment: ReviewComment) => {
    const getSeverityTag = (severity: string) => {
      switch (severity) {
        case 'critical':
          return <Tag color="red" style={{ fontSize: 11 }}>严重</Tag>
        case 'warning':
          return <Tag color="orange" style={{ fontSize: 11 }}>警告</Tag>
        case 'suggestion':
          return <Tag color="blue" style={{ fontSize: 11 }}>建议</Tag>
        default:
          return <Tag style={{ fontSize: 11 }}>{severity}</Tag>
      }
    }

    const commentKey = `${comment.file_path}-${comment.line_number}-${comment.content.slice(0, 20)}`
    const isEditing = editingAIComment?.comment.file_path === comment.file_path &&
                     editingAIComment?.comment.line_number === comment.line_number &&
                     editingAIComment?.comment.content === comment.content
    const isSending = sendingAIComment === commentKey

    return (
      <div
        key={commentKey}
        style={{
          marginLeft: 120, // 对齐到内容区域
          marginTop: 4,
          marginBottom: 8,
          padding: '8px 12px',
          background: '#1677ff15',
          borderLeft: '3px solid #1677ff',
          borderRadius: 4,
        }}
      >
        <Space size="small" direction="vertical" style={{ width: '100%' }}>
          <Space size="small" wrap>
            <RobotOutlined style={{ color: '#1677ff', fontSize: 12 }} />
            {getSeverityTag(comment.severity)}
          </Space>
          {isEditing ? (
            <Input.TextArea
              value={editingAIComment.content}
              onChange={(e) => setEditingAIComment({ ...editingAIComment, content: e.target.value })}
              autoSize={{ minRows: 2, maxRows: 6 }}
              size="small"
              style={{ fontSize: 12 }}
            />
          ) : (
            <Text style={{ fontSize: 12, color: '#d9d9d9', whiteSpace: 'pre-wrap' }}>
              {comment.content}
            </Text>
          )}
          <Space size="small">
            {isEditing ? (
              <>
                <Button
                  type="primary"
                  size="small"
                  icon={<CheckOutlined />}
                  onClick={handleSaveAIComment}
                  style={{ fontSize: 11 }}
                >
                  保存
                </Button>
                <Button
                  size="small"
                  icon={<CloseOutlined />}
                  onClick={handleCancelEditAIComment}
                  style={{ fontSize: 11 }}
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
                  onClick={() => handleSendAIComment(comment)}
                  loading={isSending}
                  style={{ fontSize: 11 }}
                >
                  发送
                </Button>
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => handleStartEditAIComment(comment)}
                  style={{ fontSize: 11 }}
                >
                  编辑
                </Button>
                <Button
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => handleDeleteAIComment(comment)}
                  danger
                  style={{ fontSize: 11 }}
                >
                  删除
                </Button>
              </>
            )}
          </Space>
        </Space>
      </div>
    )
  }

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      overflow: 'hidden',
    }}>
      {/* 文件列表 */}
      <div style={{
        height: 200,
        borderBottom: '1px solid #303030',
        overflow: 'auto',
      }}>
        <List
          dataSource={fileList}
          size="small"
          renderItem={(file) => (
            <List.Item
              key={file.new_path}
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                background: selectedFile?.new_path === file.new_path ? '#1677ff20' : 'transparent',
                display: 'flex',
                alignItems: 'center',
              }}
              onClick={() => onSelectFile(file)}
            >
              <List.Item.Meta
                avatar={getFileIcon(file)}
                title={
                  <Space>
                    <Text
                      ellipsis={{ tooltip: file.new_path }}
                      style={{ fontSize: 13, maxWidth: 400 }}
                    >
                      {file.new_path}
                    </Text>
                    {file.additions > 0 && (
                      <Text type="success" style={{ fontSize: 12 }}>
                        +{file.additions}
                      </Text>
                    )}
                    {file.deletions > 0 && (
                      <Text type="danger" style={{ fontSize: 12 }}>
                        -{file.deletions}
                      </Text>
                    )}
                  </Space>
                }
                description={
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {file.old_path !== file.new_path && file.old_path}
                  </Text>
                }
              />
              <Button
                type="primary"
                size="small"
                icon={<RobotOutlined />}
                onClick={(e) => {
                  e.stopPropagation()
                  handleReviewFile(file)
                }}
                loading={reviewingFiles.has(file.new_path)}
                disabled={isReviewingAllFiles}
                style={{ fontSize: 11, marginLeft: 8 }}
              >
                AI 审查
              </Button>
            </List.Item>
          )}
        />
      </div>

      {/* Diff 内容 */}
      <div
        ref={diffContainerRef}
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '8px 0',
        }}
      >
        {!diffFile ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="选择文件查看 Diff"
            style={{ marginTop: 60 }}
          />
        ) : (
          // Use key to force re-render when file changes
          <div key={diffFile.new_path}>
            {/* 文件头部信息 */}
            <div style={{
              padding: '8px 16px',
              borderBottom: '1px solid #303030',
              background: '#1f1f1f',
            }}>
              <Space>
                <FileOutlined />
                <Text strong>{diffFile.new_path}</Text>
                {diffFile.old_path !== diffFile.new_path && (
                  <Text type="secondary">
                    (原名: {diffFile.old_path})
                  </Text>
                )}
                {stats.additions > 0 && (
                  <Text type="success" style={{ fontSize: 12 }}>
                    +{stats.additions}
                  </Text>
                )}
                {stats.deletions > 0 && (
                  <Text type="danger" style={{ fontSize: 12 }}>
                    -{stats.deletions}
                  </Text>
                )}
              </Space>
            </div>

            {/* Diff 行 */}
            <div>
              {(() => {
                // 跟踪已经渲染的 AI 评论，确保每条评论只显示一次
                const renderedComments = new Set<string>()
                // 存储：行索引 -> 需要渲染的评论列表
                const commentsByLineIndex = new Map<number, ReviewComment[]>()

                // 第一遍历：优先将评论分配给新增行
                aiComments.forEach(comment => {
                  const commentKey = `${comment.file_path}-${comment.line_number}-${comment.content.slice(0, 20)}`
                  if (renderedComments.has(commentKey)) return

                  // 优先在新增行中查找匹配的行号
                  const additionLineIndex = diffLines.findIndex(line =>
                    line.type === 'addition' && line.newNumber === comment.line_number
                  )

                  if (additionLineIndex !== -1) {
                    // 找到新增行，分配评论
                    if (!commentsByLineIndex.has(additionLineIndex)) {
                      commentsByLineIndex.set(additionLineIndex, [])
                    }
                    commentsByLineIndex.get(additionLineIndex)!.push(comment)
                    renderedComments.add(commentKey)
                  } else {
                    // 如果没有新增行匹配，尝试在删除行中查找
                    const deletionLineIndex = diffLines.findIndex(line =>
                      line.type === 'deletion' && line.oldNumber === comment.line_number
                    )
                    if (deletionLineIndex !== -1) {
                      if (!commentsByLineIndex.has(deletionLineIndex)) {
                        commentsByLineIndex.set(deletionLineIndex, [])
                      }
                      commentsByLineIndex.get(deletionLineIndex)!.push(comment)
                      renderedComments.add(commentKey)
                    }
                  }
                })

                // 第二遍历：渲染 diff 行和对应的 AI 评论
                return diffLines.map((line, index) => {
                  const lineComments = commentsByLineIndex.get(index) || []

                  return (
                    <div key={index}>
                      {renderLine(line, index)}
                      {/* AI 评论 */}
                      {lineComments.length > 0 && lineComments.map(renderAIComment)}
                    </div>
                  )
                })
              })()}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default DiffViewer
