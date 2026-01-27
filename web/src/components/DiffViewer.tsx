/**
 * Diff 查看器组件
 */

import { type FC, useMemo, useEffect, useRef } from 'react'
import { List, Empty, Typography, Space, Button, Tooltip } from 'antd'
import {
  FileOutlined,
  PlusOutlined,
  MinusOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons'
import type { DiffFile } from '../types'
import { useApp } from '../contexts/AppContext'

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
  const { setCurrentDiffFile, highlightLine, setHighlightLine } = useApp()
  const diffContainerRef = useRef<HTMLDivElement>(null)

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
          backgroundColor: isHighlighted ? '#ffec3d26' : 'transparent',
        }}
      >
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
