/**
 * Diff 查看器组件
 */

import { type FC, useMemo, useEffect, useRef, useState } from 'react'
import { List, Empty, Typography, Space, Input, Popover, Button, message } from 'antd'
import {
  FileOutlined,
  PlusOutlined,
  MinusOutlined,
  ArrowRightOutlined,
  CommentOutlined,
} from '@ant-design/icons'
import type { DiffFile } from '../types'
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
}

const DiffViewer: FC<DiffViewerProps> = ({
  diffFile,
  diffLines,
  fileList,
  selectedFile,
  onSelectFile,
}) => {
  const { setCurrentDiffFile, highlightLine, setHighlightLine, currentProject, currentMR, setNotes } = useApp()
  const diffContainerRef = useRef<HTMLDivElement>(null)

  // 行内评论状态
  const [commentLineId, setCommentLineId] = useState<string | null>(null)
  const [commentInput, setCommentInput] = useState('')
  const [submittingComment, setSubmittingComment] = useState(false)

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
              {diffLines.map((line, index) => renderLine(line, index))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default DiffViewer
