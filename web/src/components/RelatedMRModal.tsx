/**
 * 与我相关的 MR 弹窗组件
 */

import { type FC, useState, useEffect, useCallback, useRef } from 'react'
import { Modal, List, Tag, Avatar, Space, Typography, Spin, Button, Tooltip, message } from 'antd'
import type { ButtonProps } from 'antd/es/button'

// 带自动 loading 状态的按钮组件
interface LoadingButtonProps extends Omit<ButtonProps, 'onClick'> {
  onClick: () => Promise<void> | void
}

const LoadingButton: FC<LoadingButtonProps> = ({ onClick, children, ...props }) => {
  const [loading, setLoading] = useState(false)

  const handleClick = async () => {
    setLoading(true)
    try {
      await onClick()
    } finally {
      setLoading(false)
    }
  }

  return (
    <Button {...props} loading={loading} onClick={handleClick}>
      {children}
    </Button>
  )
}
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  MergeCellsOutlined,
  MessageOutlined,
  LinkOutlined,
  ExportOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import type { RelatedMR } from '../types'
import type { AutoReviewConfig, AutoReviewSettingsModalRef } from './AutoReviewSettingsModal'
import { getAutoReviewConfig, AutoReviewSettingsModal, getDefaultAutoReviewConfig } from './AutoReviewSettingsModal'
import { api } from '../api/client'
import { useApp } from '../contexts/AppContext'

const { Text } = Typography

// 根据字符串生成一致的颜色
const stringToColor = (str: string): string => {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  // 使用 HSL 颜色空间，确保颜色鲜艳且可读
  const hue = Math.abs(hash % 360)
  return `hsla(${hue}, 100%, 30%, 0.7)`
}

interface ViewedMRState {
  [key: string]: boolean
}

interface ApprovedMRState {
  [key: string]: boolean
}

interface RelatedMRModalProps {
  open: boolean
  onClose: () => void
  mode?: 'related' | 'authored'
}

// 获取 localStorage key，根据 mode 添加前缀
const getViewedKey = (mode: 'related' | 'authored'): string => {
  return mode === 'authored' ? 'authored_viewed_mr_items' : 'viewed_mr_items'
}

const getApprovedKey = (mode: 'related' | 'authored'): string => {
  return mode === 'authored' ? 'authored_approved_mr_items' : 'approved_mr_items'
}

// 获取 MR 的唯一标识 key
const getMRKey = (item: RelatedMR): string => {
  return `${item.mr.project_id}_${item.mr.iid}`
}

// 从 localStorage 读取已查看的 MR 状态
const getViewedMRs = (mode: 'related' | 'authored'): ViewedMRState => {
  try {
    const stored = localStorage.getItem(getViewedKey(mode))
    return stored ? JSON.parse(stored) : {}
  } catch {
    return {}
  }
}

// 保存已查看的 MR 状态到 localStorage
const saveViewedMR = (key: string, mode: 'related' | 'authored') => {
  try {
    const viewed = getViewedMRs(mode)
    viewed[key] = true
    localStorage.setItem(getViewedKey(mode), JSON.stringify(viewed))
  } catch {
    // ignore storage errors
  }
}

// 清理 localStorage 中不再存在的 MR 记录
const cleanupViewedMRs = (currentItems: RelatedMR[], mode: 'related' | 'authored') => {
  try {
    const viewed = getViewedMRs(mode)
    const currentKeys = new Set(currentItems.map(getMRKey))
    const cleaned: ViewedMRState = {}

    for (const [key, value] of Object.entries(viewed)) {
      if (currentKeys.has(key)) {
        cleaned[key] = value
      }
    }

    localStorage.setItem(getViewedKey(mode), JSON.stringify(cleaned))
  } catch {
    // ignore storage errors
  }
}

// 从 localStorage 读取已批准的 MR 状态
const getApprovedMRs = (mode: 'related' | 'authored'): ApprovedMRState => {
  try {
    const stored = localStorage.getItem(getApprovedKey(mode))
    return stored ? JSON.parse(stored) : {}
  } catch {
    return {}
  }
}

// 保存已批准的 MR 状态到 localStorage
const saveApprovedMR = (key: string, mode: 'related' | 'authored') => {
  try {
    const approved = getApprovedMRs(mode)
    approved[key] = true
    localStorage.setItem(getApprovedKey(mode), JSON.stringify(approved))
  } catch {
    // ignore storage errors
  }
}

// 从 localStorage 移除已批准的 MR 状态
const removeApprovedMR = (key: string, mode: 'related' | 'authored') => {
  try {
    const approved = getApprovedMRs(mode)
    delete approved[key]
    localStorage.setItem(getApprovedKey(mode), JSON.stringify(approved))
  } catch {
    // ignore storage errors
  }
}

// 清理 localStorage 中不再存在的已批准 MR 记录
const cleanupApprovedMRs = (currentItems: RelatedMR[], mode: 'related' | 'authored') => {
  try {
    const approved = getApprovedMRs(mode)
    const currentKeys = new Set(currentItems.map(getMRKey))
    const cleaned: ApprovedMRState = {}

    for (const [key, value] of Object.entries(approved)) {
      if (currentKeys.has(key)) {
        cleaned[key] = value
      }
    }

    localStorage.setItem(getApprovedKey(mode), JSON.stringify(cleaned))
  } catch {
    // ignore storage errors
  }
}

const RelatedMRModal: FC<RelatedMRModalProps> = ({ open, onClose, mode = 'related' }) => {
  const {
    setCurrentProject,
    setCurrentMR,
    setMrListFilterRelated,
    setMrListFilterState,
    addProject
  } = useApp()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<RelatedMR[]>([])
  const [viewedMRs, setViewedMRs] = useState<ViewedMRState>({})
  const [approvedMRs, setApprovedMRs] = useState<ApprovedMRState>({})

  // 自动 Review 配置状态
  const [autoReviewConfig, setAutoReviewConfig] = useState<AutoReviewConfig>(getDefaultAutoReviewConfig())
  const [autoReviewRunning, setAutoReviewRunning] = useState(false)
  const settingsModalRef = useRef<AutoReviewSettingsModalRef>(null)

  // 检查 MR 是否是新的（未查看过）
  const isNewMR = useCallback((item: RelatedMR): boolean => {
    return !viewedMRs[getMRKey(item)]
  }, [viewedMRs])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const result = mode === 'authored'
        ? await api.listAuthoredMergeRequests('opened')
        : await api.listRelatedMergeRequests('opened')
      // 清理 localStorage 中不再存在的 MR 记录
      cleanupViewedMRs(result, mode)
      cleanupApprovedMRs(result, mode)
      // 更新本地状态
      setViewedMRs(getViewedMRs(mode))
      setApprovedMRs(getApprovedMRs(mode))
      setData(result)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '加载 MR 列表失败')
    } finally {
      setLoading(false)
    }
  }, [mode])

  useEffect(() => {
    if (open) {
      loadData()
    }
  }, [open, loadData])

  // 加载自动 Review 配置
  useEffect(() => {
    setAutoReviewConfig(getAutoReviewConfig())
  }, [])

  // 自动 Review 后台任务
  useEffect(() => {
    // 只在 mode 为 'related' 时启用
    if (mode !== 'related') return

    // 如果未启用，不执行
    if (!autoReviewConfig.enabled || !autoReviewConfig.creators.length) {
      setAutoReviewRunning(false)
      return
    }

    setAutoReviewRunning(true)

    const intervalMs = autoReviewConfig.interval * 1000
    let mounted = true

    const runAutoReview = async () => {
      try {
        if (!mounted) return

        // 获取相关 MR
        const relatedMRs = await api.listRelatedMergeRequests('opened')
        setData(relatedMRs)
        cleanupViewedMRs(relatedMRs, mode)
        cleanupApprovedMRs(relatedMRs, mode)
        // 更新本地状态
        setViewedMRs(getViewedMRs(mode))
        setApprovedMRs(getApprovedMRs(mode))

        // 筛选指定创建者的 MR
        const targetMRs = relatedMRs.filter(item => {
          const key = getMRKey(item)
          // 已经被批准过的跳过
          const approvedMRs = getApprovedMRs(mode)
          if (approvedMRs[key]) return false
          // 筛选创建者
          return autoReviewConfig.creators.includes(item.mr.author_name)
        })

        if (targetMRs.length === 0) return

        // 处理每个符合条件的 MR
        for (const item of targetMRs) {
          if (!mounted) break
          if (!item.project) continue

          const key = getMRKey(item)
          try {
            // 调用 AI 总结接口
            let summary = ''
            await api.summarizeChanges(
              item.project.id.toString(),
              item.mr.iid,
              (chunk) => {
                summary += chunk
              }
            )

            // 将 AI 总结作为评论回复
            if (summary) {
              await api.createMergeRequestNote(
                item.project.id.toString(),
                item.mr.iid,
                { body: summary }
              )
            }

            // 自动批准 MR
            await api.approveMergeRequest(
              item.project.id.toString(),
              item.mr.iid
            )

            // 标记为已查看和已批准
            saveViewedMR(key, mode)
            saveApprovedMR(key, mode)

            console.log(`[Auto Review] 成功处理 MR: ${item.mr.title} (${item.mr.author_name})`)
          } catch (err) {
            console.error(`[Auto Review] 处理 MR 失败: ${item.mr.title}`, err)
          }
        }
      } catch (err) {
        console.error('[Auto Review] 获取 MR 列表失败:', err)
      }
    }

    // 首次执行
    runAutoReview()

    // 设置定时器
    const timer = setInterval(runAutoReview, intervalMs)

    return () => {
      mounted = false
      clearInterval(timer)
      setAutoReviewRunning(false)
    }
  }, [autoReviewConfig, mode])

  const handleOpenMR = async (item: RelatedMR) => {
    if (!item.project) return

    // 标记为已查看
    const key = getMRKey(item)
    saveViewedMR(key, mode)
    setViewedMRs(getViewedMRs(mode))

    // 将项目添加到最近打开的项目列表（localStorage）
    if (item.project) {
      addProject(item.project)
    }

    // 切换项目
    setCurrentProject(item.project)

    // 设置当前 MR
    setCurrentMR(item.mr)

    // 设置左侧 MR 列表的筛选状态：勾选"与我相关"，状态切到 opened
    if (mode !== 'authored') {
      setMrListFilterRelated(true)
    }
    setMrListFilterState('opened')

    onClose()
  }

  const handleApprove = async (item: RelatedMR) => {
    if (!item.project) return
    const key = getMRKey(item)
    try {
      await api.approveMergeRequest(
        item.project.id.toString(),
        item.mr.iid
      )
      message.success('已批准')
      // 标记为已查看和已批准
      saveViewedMR(key, mode)
      setViewedMRs(getViewedMRs(mode))
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '批准失败')
    } finally {
      saveApprovedMR(key, mode)
      setApprovedMRs(getApprovedMRs(mode))
    }
  }

  const handleUnapprove = async (item: RelatedMR) => {
    if (!item.project) return

    try {
      await api.unapproveMergeRequest(
        item.project.id.toString(),
        item.mr.iid
      )
      message.success('已取消批准')
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '取消批准失败')
    } finally{
      // 移除已批准状态
      const key = getMRKey(item)
      removeApprovedMR(key, mode)
      setApprovedMRs(getApprovedMRs(mode))
    }
  }

  const handleSendLGTM = async (item: RelatedMR) => {
    if (!item.project) return

    try {
      // 发送 LGTM 评论
      await api.createMergeRequestNote(
        item.project.id.toString(),
        item.mr.iid,
        { body: 'LGTM' }
      )

      // 同时批准 MR
      await api.approveMergeRequest(
        item.project.id.toString(),
        item.mr.iid
      )

      message.success('已发送 LGTM 并批准')

      // 标记为已查看和已批准
      const key = getMRKey(item)
      saveViewedMR(key, mode)
      saveApprovedMR(key, mode)
      setViewedMRs(getViewedMRs(mode))
      setApprovedMRs(getApprovedMRs(mode))
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '发送失败')
    }
  }

  const handleCopyLink = async (item: RelatedMR) => {
    try {
      await navigator.clipboard.writeText(item.mr.web_url)
      message.success('链接已复制到剪贴板')
    } catch {
      message.error('复制失败')
    }
  }

  const handleOpenGitLab = (item: RelatedMR) => {
    window.open(item.mr.web_url, '_blank')
  }

  const getStateTag = (state: string) => {
    switch (state) {
      case 'opened':
        return <Tag icon={<ClockCircleOutlined />} color="blue">打开中</Tag>
      case 'closed':
        return <Tag icon={<CloseCircleOutlined />} color="red">已关闭</Tag>
      case 'merged':
        return <Tag icon={<MergeCellsOutlined />} color="green">已合并</Tag>
      default:
        return <Tag>{state}</Tag>
    }
  }

  return (
    <>
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span>{mode === 'authored' ? '我创建的 Merge Requests' : '与我相关的 Merge Requests'}</span>
            {mode === 'related' && (
              <Space>
                {autoReviewRunning && autoReviewConfig.enabled && (
                  <Tag color="green" icon={<CheckCircleOutlined />}>自动 Review 运行中</Tag>
                )}
                <Tooltip title="自动 Review 设置">
                  <Button
                    type="text"
                    size="small"
                    icon={<SettingOutlined />}
                    onClick={() => settingsModalRef.current?.open()}
                  />
                </Tooltip>
              </Space>
            )}
          </div>
        }
        open={open}
        onCancel={onClose}
        footer={null}
        width={800}
      >
      <Spin spinning={loading}>
        <List
          dataSource={data}
          renderItem={(item) => (
            <List.Item style={{ display: 'block', padding: '12px 16px' }}>
              <div style={{ position: 'relative' }}>
                {/* 右上角按钮 */}
                <Space style={{ position: 'absolute', top: 0, right: 0 }}>
                  <Tooltip title="复制链接">
                    <Button
                      size="small"
                      icon={<LinkOutlined />}
                      onClick={() => handleCopyLink(item)}
                    />
                  </Tooltip>
                  <Tooltip title="在 GitLab 中打开">
                    <Button
                      size="small"
                      icon={<ExportOutlined />}
                      onClick={() => handleOpenGitLab(item)}
                    />
                  </Tooltip>
                </Space>

                {/* 主要内容 */}
                <div style={{ paddingRight: 120 }}>
                  <List.Item.Meta
                    avatar={
                      <Avatar
                        src={item.mr.author_avatar}
                        icon={<MergeCellsOutlined />}
                      />
                    }
                    title={
                      <Space>
                        <Text strong>{item.mr.title}</Text>
                        {isNewMR(item) && (
                          <Tag color="red">New</Tag>
                        )}
                        {getStateTag(item.mr.state)}
                        {approvedMRs[getMRKey(item)] && (
                          <Tag icon={<CheckCircleOutlined />} color="success">已批准</Tag>
                        )}
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={0}>
                        <Space size={4}>
                          <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>
                            {item.mr.author_name}
                          </Tag>
                          <Tag color={stringToColor(item.project?.name || 'Unknown')} style={{ fontSize: 11, margin: 0 }}>
                            {item.project?.name || 'Unknown'}
                          </Tag>
                          <Tag style={{ fontSize: 11, margin: 0 }}>
                            !{item.mr.iid}
                          </Tag>
                        </Space>
                        <Space size={4}>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {item.mr.source_branch} → {item.mr.target_branch}
                          </Text>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            ·
                          </Text>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            <MessageOutlined style={{ marginRight: 2 }} />
                            {item.mr.user_notes_count}
                          </Text>
                        </Space>
                      </Space>
                    }
                  />
                </div>

                {/* 底部操作按钮 */}
                <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                  <LoadingButton
                    size="small"
                    onClick={() => handleSendLGTM(item)}
                  >
                    发送LGTM并批准
                  </LoadingButton>
                  {approvedMRs[getMRKey(item)] ? (
                    <LoadingButton
                      size="small"
                      danger
                      onClick={() => handleUnapprove(item)}
                    >
                      取消批准
                    </LoadingButton>
                  ) : (
                    <LoadingButton
                      size="small"
                      type="primary"
                      onClick={() => handleApprove(item)}
                    >
                      批准
                    </LoadingButton>
                  )}
                  <Button
                    size="small"
                    onClick={() => handleOpenMR(item)}
                  >
                    打开
                  </Button>
                </div>
              </div>
            </List.Item>
          )}
        />
      </Spin>
    </Modal>

      {/* 自动 Review 设置弹窗 */}
      <AutoReviewSettingsModal
        ref={settingsModalRef}
        onConfigChange={setAutoReviewConfig}
      />
    </>
  )
}

export default RelatedMRModal
