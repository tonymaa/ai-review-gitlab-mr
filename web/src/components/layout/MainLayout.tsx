/**
 * 主布局组件 - 三栏布局
 */

import { type FC, useEffect, useState } from 'react'
import { Layout } from 'antd'
import { useApp } from '../../contexts/AppContext'
import MRListPanel from '../MRListPanel'
import DiffViewer from '../DiffViewer'
import CommentPanel from '../CommentPanel'

const { Content, Sider } = Layout

/**
 * 解析 diff 内容为行
 */
function parseDiffLines(diff: string): Array<{
  type: 'addition' | 'deletion' | 'context' | 'header'
  oldNumber?: number
  newNumber?: number
  content: string
}> {
  const lines: ReturnType<typeof parseDiffLines> = []
  const diffLines = diff.split('\n')

  let oldLine = 0
  let newLine = 0
  let inHunk = false

  for (const line of diffLines) {
    // Hunk 头部
    const hunkMatch = line.match(/^@@\s+-(\d+),?\d*\s+\+(\d+),?\d*\s+@@/)
    if (hunkMatch) {
      oldLine = parseInt(hunkMatch[1]) - 1
      newLine = parseInt(hunkMatch[2]) - 1
      inHunk = true
      lines.push({
        type: 'header',
        content: line,
      })
      continue
    }

    // 文件头部
    if (line.startsWith('diff --git') || line.startsWith('index ') ||
        line.startsWith('--- ') || line.startsWith('+++ ') ||
        line.startsWith('new file') || line.startsWith('deleted file')) {
      inHunk = false
      lines.push({
        type: 'header',
        content: line,
      })
      continue
    }

    if (!inHunk) {
      lines.push({
        type: 'header',
        content: line,
      })
      continue
    }

    // 添加行
    if (line.startsWith('+') && !line.startsWith('+++')) {
      newLine += 1
      lines.push({
        type: 'addition',
        newNumber: newLine,
        content: line.slice(1),
      })
    }
    // 删除行
    else if (line.startsWith('-') && !line.startsWith('---')) {
      oldLine += 1
      lines.push({
        type: 'deletion',
        oldNumber: oldLine,
        content: line.slice(1),
      })
    }
    // 上下文行
    else if (line.startsWith(' ')) {
      oldLine += 1
      newLine += 1
      lines.push({
        type: 'context',
        oldNumber: oldLine,
        newNumber: newLine,
        content: line.slice(1),
      })
    }
    // 其他
    else {
      lines.push({
        type: 'header',
        content: line,
      })
    }
  }

  return lines
}

const MainLayout: FC = () => {
  const {
    currentProject,
    mergeRequests,
    setMergeRequests,
    currentMR,
    setCurrentMR,
    diffFiles,
    setDiffFiles,
    currentDiffFile,
    setCurrentDiffFile,
    loading,
    setLoading,
  } = useApp()

  const [diffLines, setDiffLines] = useState<ReturnType<typeof parseDiffLines>>([])

  // 当选择 MR 时加载 diff
  useEffect(() => {
    if (currentMR && currentProject) {
      const loadDiffs = async () => {
        setLoading(true)
        try {
          console.log('Loading diffs for MR:', currentMR.iid, 'project:', currentProject.id)
          const { api } = await import('../../api/client')
          const diffs = await api.getMergeRequestDiffs(
            currentProject.id.toString(),
            currentMR.iid
          )
          console.log('Loaded diffs:', diffs)
          console.log('First diff:', diffs[0])
          if (diffs.length > 0) {
            console.log('Setting first diff file:', diffs[0])
            setCurrentDiffFile(diffs[0])
          } else {
            console.log('No diffs found')
          }
          setDiffFiles(diffs)
        } catch (err) {
          console.error('Failed to load diffs:', err)
        } finally {
          setLoading(false)
        }
      }
      loadDiffs()
    }
  }, [currentMR, currentProject, setDiffFiles, setCurrentDiffFile, setLoading])

  // 当选择文件时解析 diff
  useEffect(() => {
    if (currentDiffFile) {
      setDiffLines(parseDiffLines(currentDiffFile.diff))
    } else {
      setDiffLines([])
    }
  }, [currentDiffFile])

  return (
    <Layout style={{ height: 'calc(100vh - 48px)', background: '#000' }}>
      {/* 左侧：MR 列表 */}
      <Sider
        width={320}
        style={{
          background: '#1f1f1f',
          borderRight: '1px solid #303030',
        }}
      >
        <MRListPanel
          mergeRequests={mergeRequests}
          onSelectMR={(mr) => setCurrentMR(mr)}
        />
      </Sider>

      {/* 中间：Diff 查看器 */}
      <Content style={{ flex: 1, display: 'flex', overflow: 'hidden', background: '#141414' }}>
        <DiffViewer
          diffFile={currentDiffFile}
          diffLines={diffLines}
          fileList={diffFiles}
          selectedFile={currentDiffFile}
          onSelectFile={(file) => setCurrentDiffFile(file)}
        />
      </Content>

      {/* 右侧：评论面板 */}
      <Sider
        width={380}
        style={{
          background: '#1f1f1f',
          borderLeft: '1px solid #303030',
        }}
      >
        <CommentPanel />
      </Sider>
    </Layout>
  )
}

export default MainLayout
