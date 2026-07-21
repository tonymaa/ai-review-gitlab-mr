/**
 * 与我相关的 MR 弹窗组件
 */

import { type FC, useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { Modal, List, Tag, Avatar, Space, Typography, Spin, Button, Tooltip, message, Popconfirm } from 'antd'
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
  LoadingOutlined,
  MergeCellsOutlined,
  MessageOutlined,
  LinkOutlined,
  ExportOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import type { RelatedMR } from '../types'
import type { AutoReviewSettingsModalRef } from './AutoReviewSettingsModal'
import { AutoReviewSettingsModal } from './AutoReviewSettingsModal'
import { api, type AutoReviewConfig } from '../api/client'
import { useApp } from '../contexts/AppContext'

const { Text } = Typography

// 默认自动审查配置
const getDefaultAutoReviewConfig = (): AutoReviewConfig => ({
  enabled: false,
  interval_seconds: 120,
  target_creators: [],
  target_projects: [],
  auto_approve_keywords: [],
  auto_approve_mode: 'always',
  add_as_comment: true,
})

// 排序函数：优先按项目名称排序，然后按创建时间排序
const sortMRs = (items: RelatedMR[]): RelatedMR[] => {
  return [...items].sort((a, b) => {
    // 先按项目名称排序
    const projectNameA = a.project?.name || ''
    const projectNameB = b.project?.name || ''
    const nameCompare = projectNameA.localeCompare(projectNameB, 'zh-CN')
    if (nameCompare !== 0) return nameCompare

    // 项目名称相同时，按创建时间排序（新的在前）
    const timeA = new Date(a.mr.created_at).getTime()
    const timeB = new Date(b.mr.created_at).getTime()
    return timeB - timeA
  })
}

// 根据字符串生成一致的颜色
const stringToColor = (str: string): string => {
  // 使用 FNV-1a 哈希算法，分布更均匀
  let hash = 2166136261
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  // 使用黄金角度来确保色相分布更均匀
  const goldenAngle = 137.508
  const hue = Math.abs(hash % 360)
  // 结合黄金角度偏移，进一步打散相近字符串的颜色
  const finalHue = (hue + str.length * goldenAngle) % 360
  return `hsla(${finalHue}, 100%, 30%, 0.8)`
}

interface ViewedMRState {
  [key: string]: boolean
}

// 单个 MR 的批准状态（懒加载）
interface ApprovalItemState {
  loading: boolean
  approved: boolean
  approvedBy: Array<{ id: number; name: string; username: string; avatar_url?: string }>
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
  // 懒加载的批准状态：key → ApprovalItemState
  const [approvalMap, setApprovalMap] = useState<Record<string, ApprovalItemState>>({})

  // 自动 Review 配置状态
  const [autoReviewConfig, setAutoReviewConfig] = useState<AutoReviewConfig>(getDefaultAutoReviewConfig())
  const [autoReviewRunning, setAutoReviewRunning] = useState(false)
  const settingsModalRef = useRef<AutoReviewSettingsModalRef>(null)

  // 检查 MR 是否是新的（未查看过）
  const isNewMR = useCallback((item: RelatedMR): boolean => {
    return !viewedMRs[getMRKey(item)]
  }, [viewedMRs])

  // 并发懒加载所有 MR 的批准状态
  // 注意：此函数需在 loadData 之前定义，因为 loadData 的 useCallback deps 引用它
  const loadApprovalStates = useCallback((items: RelatedMR[]) => {
    // 初始化为 loading 态
    const initialMap: Record<string, ApprovalItemState> = {}
    for (const item of items) {
      if (!item.project) continue
      initialMap[getMRKey(item)] = {
        loading: true,
        approved: false,
        approvedBy: [],
      }
    }
    setApprovalMap(initialMap)

    // 逐个并发请求，完成后独立更新
    for (const item of items) {
      if (!item.project) continue
      const key = getMRKey(item)
      api
        .getMergeRequestApprovalState(item.project.id.toString(), item.mr.iid)
        .then((state) => {
          setApprovalMap((prev) => ({
            ...prev,
            [key]: {
              loading: false,
              approved: state.approved,
              approvedBy: state.approved_by,
            },
          }))
        })
        .catch(() => {
          setApprovalMap((prev) => ({
            ...prev,
            [key]: {
              loading: false,
              approved: false,
              approvedBy: [],
            },
          }))
        })
    }
  }, [])

  const loadData = useCallback(async () => {
    setLoading(true)
    // 列表重新加载时清空批准状态，避免显示旧数据
    setApprovalMap({})
    try {
      const result = mode === 'authored'
        ? await api.listAuthoredMergeRequests('opened')
        : await api.listRelatedMergeRequests('opened')
      // 清理 localStorage 中不再存在的 MR 记录
      cleanupViewedMRs(result, mode)
      // 更新本地状态
      setViewedMRs(getViewedMRs(mode))
      setData(sortMRs(result))
      // 列表加载完成后，懒加载每个 MR 的批准状态
      loadApprovalStates(result)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '加载 MR 列表失败')
    } finally {
      setLoading(false)
    }
  }, [mode, loadApprovalStates])

  useEffect(() => {
    if (open) {
      loadData()
    }
  }, [open, loadData])

  // 加载自动 Review 配置
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await api.getAutoReviewConfig()
        setAutoReviewConfig(config)
      } catch (err) {
        // 如果获取失败，使用默认配置
        setAutoReviewConfig(getDefaultAutoReviewConfig())
      }
    }
    loadConfig()
  }, [])

  // 自动 Review 后台任务（已禁用 - 现由后端调度器处理）
  useEffect(() => {
    // 前端自动审查已禁用，现在由后端调度器处理
    setAutoReviewRunning(false)
  }, [mode])

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
      // 标记为已查看
      saveViewedMR(key, mode)
      setViewedMRs(getViewedMRs(mode))
      // 同步懒加载的批准状态（当前用户已批准）
      setApprovalMap((prev) => ({
        ...prev,
        [key]: { loading: false, approved: true, approvedBy: prev[key]?.approvedBy ?? [] },
      }))
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '批准失败')
    }
  }

  const handleUnapprove = async (item: RelatedMR) => {
    if (!item.project) return
    const key = getMRKey(item)

    try {
      await api.unapproveMergeRequest(
        item.project.id.toString(),
        item.mr.iid
      )
      message.success('已取消批准')
      // 同步懒加载的批准状态（当前用户已取消批准）
      setApprovalMap((prev) => ({
        ...prev,
        [key]: { loading: false, approved: false, approvedBy: prev[key]?.approvedBy ?? [] },
      }))
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '取消批准失败')
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

      // 标记为已查看
      const key = getMRKey(item)
      saveViewedMR(key, mode)
      setViewedMRs(getViewedMRs(mode))
      // 同步懒加载的批准状态
      setApprovalMap((prev) => ({
        ...prev,
        [key]: { loading: false, approved: true, approvedBy: prev[key]?.approvedBy ?? [] },
      }))
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

  // 获取不能合并的原因
  const getMergeDisabledReason = (item: RelatedMR): string | null => {
    if (item.mr.has_conflicts) {
      return '存在合并冲突'
    }
    if (item.mr.merge_status === 'cannot_be_merged') {
      return '无法合并'
    }
    if (item.mr.merge_status === 'checking') {
      return '正在检查合并状态'
    }
    if (item.mr.merge_status === 'unchecked') {
      return '尚未检查合并状态'
    }
    if (item.mr.merge_status !== 'can_be_merged') {
      return `合并状态: ${item.mr.merge_status || '未知'}`
    }
    return null
  }

  const canMerge = (item: RelatedMR): boolean => {
    return !item.mr.has_conflicts && item.mr.merge_status === 'can_be_merged'
  }

  // 已批准且可合并：用于一键合并
  const isApprovedAndMergeable = (item: RelatedMR): boolean => {
    return canMerge(item) && (item.mr.approved_by?.length ?? 0) > 0
  }

  // 一键合并候选列表
  const mergeableItems = useMemo(
    () => data.filter((item) => isApprovedAndMergeable(item)),
    // isApprovedAndMergeable 仅依赖 item 数据，无需纳入依赖
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data]
  )

  const handleMerge = async (item: RelatedMR) => {
    if (!item.project) return false;
    try {
      await api.acceptMergeRequest(
        item.project.id.toString(),
        item.mr.iid,
        {
          should_remove_source_branch: false,
        }
      )
      message.success('合并成功')
      // 乐观更新：立即从列表移除已合并的 MR，避免组件状态复用导致按钮错位
      setData((prev) => prev.filter((x) => getMRKey(x) !== getMRKey(item)))
      return true;
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '合并失败')
      return false;
    }
  }

  // 一键合并：顺序合并所有已批准且可合并的 MR
  const handleMergeAll = async (): Promise<void> => {
    const targets = data.filter(isApprovedAndMergeable)
    if (targets.length === 0) return

    setLoading(true)
    const failedKeys = new Set<string>()
    const mergedKeys: string[] = []

    try {
      for (const item of targets) {
        if (!item.project) continue
        const key = getMRKey(item)
        try {
          await api.acceptMergeRequest(
            item.project.id.toString(),
            item.mr.iid,
            { should_remove_source_branch: false }
          )
          mergedKeys.push(key)
        } catch {
          failedKeys.add(key)
        }
      }

      // 批量移除成功项
      if (mergedKeys.length > 0) {
        const mergedSet = new Set(mergedKeys)
        setData((prev) => prev.filter((x) => !mergedSet.has(getMRKey(x))))
      }

      if (mergedKeys.length > 0 && failedKeys.size === 0) {
        message.success(`已合并 ${mergedKeys.length} 个 MR`)
      } else if (mergedKeys.length > 0 && failedKeys.size > 0) {
        message.warning(`合并 ${mergedKeys.length} 个成功，${failedKeys.size} 个失败`)
      } else {
        message.error('全部合并失败')
      }
    } finally {
      setLoading(false)
    }
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

  // 根据懒加载的批准状态渲染标签
  const renderApprovalTag = (item: RelatedMR) => {
    const key = getMRKey(item)
    const state = approvalMap[key]
    if (!state) return null

    if (state.loading) {
      return <Tag icon={<LoadingOutlined spin />} color="default">批准状态</Tag>
    }

    // authored 模式看其他人是否批准；related 模式看当前用户是否批准
    const isApproved = mode === 'authored'
      ? state.approvedBy.length > 0
      : state.approved

    if (isApproved) {
      // authored 模式下，鼠标悬停显示批准者列表
      if (mode === 'authored' && state.approvedBy.length > 0) {
        return (
          <Tooltip
            title={
              <Space style={{ flexDirection: 'column', gap: 0 }} size={0}>
                {state.approvedBy.map((approver) => (
                  <Text key={approver.username || approver.name}>
                    {approver.name}
                  </Text>
                ))}
              </Space>
            }
          >
            <Tag icon={<CheckCircleOutlined />} color="success">已批准</Tag>
          </Tooltip>
        )
      }
      return <Tag icon={<CheckCircleOutlined />} color="success">已批准</Tag>
    }

    return <Tag icon={<CloseCircleOutlined />} color="default">未批准</Tag>
  }

  return (
    <>
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 32 }}>
            <span>{mode === 'authored' ? '我创建的 Merge Requests' : '与我相关的 Merge Requests'}</span>
            {mode === 'authored' && (
              <Popconfirm
                title="一键合并"
                description={
                  mergeableItems.length > 0
                    ? `将顺序合并 ${mergeableItems.length} 个已批准且可合并的 MR，是否继续？`
                    : '当前没有可合并的 MR（需已批准且无冲突）'
                }
                onConfirm={handleMergeAll}
                okText="确定"
                cancelText="取消"
                disabled={mergeableItems.length === 0}
              >
                <Tooltip title={mergeableItems.length === 0 ? '没有可合并的 MR' : '批量合并已批准的 MR'}>
                  <Button
                    type="primary"
                    size="small"
                    icon={<ThunderboltOutlined />}
                    disabled={mergeableItems.length === 0}
                  >
                    一键合并{mergeableItems.length > 0 ? ` (${mergeableItems.length})` : ''}
                  </Button>
                </Tooltip>
              </Popconfirm>
            )}
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
          rowKey={(item) => getMRKey(item)}
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
                        {renderApprovalTag(item)}
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
                  {mode === 'authored' ? (
                    // 我创建的 MR：显示合并按钮
                    <>
                      {canMerge(item) ? (
                        <MergeButton item={item} handleMerge={handleMerge}/>
                      ): (
                        <Button
                          size="small"
                          type="primary"
                          disabled
                        >
                          <WarningOutlined /> {getMergeDisabledReason(item) || '无法合并'}
                        </Button>
                      )}
                      <Button
                        size="small"
                        onClick={() => handleOpenMR(item)}
                      >
                        打开
                      </Button>
                    </>
                  ) : (
                    // 与我相关的 MR：显示批准相关按钮
                    <>
                      <LoadingButton
                        size="small"
                        onClick={() => handleSendLGTM(item)}
                      >
                        发送LGTM并批准
                      </LoadingButton>
                      {approvalMap[getMRKey(item)]?.approved ? (
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
                    </>
                  )}
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

interface MergeButtonProps {
  item: RelatedMR
  handleMerge: (item: RelatedMR) => Promise<boolean>
}

function MergeButton({ item, handleMerge }: MergeButtonProps) {
  const [loading, setLoading] = useState(false)

  const onConfirm = async () => {
    setLoading(true)
    try {
      await handleMerge(item)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Popconfirm
      title="确认合并"
      description={`确定要将 ${item.mr.source_branch} 合并到 ${item.mr.target_branch} 吗？`}
      onConfirm={onConfirm}
      okText="确定"
      cancelText="取消"
    >
      <Button
        size="small"
        type="primary"
        loading={loading}
      >
        合并
      </Button>
    </Popconfirm>
  )
}

export default RelatedMRModal
