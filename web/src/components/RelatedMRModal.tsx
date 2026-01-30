/**
 * 与我相关的 MR 弹窗组件
 */

import { type FC, useState, useEffect, useCallback } from 'react'
import { Modal, List, Tag, Avatar, Space, Typography, Spin, Button, Tooltip, message } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  MergeCellsOutlined,
  MessageOutlined,
  LinkOutlined,
  ExportOutlined,
} from '@ant-design/icons'
import type { RelatedMR } from '../types'
import { api } from '../api/client'
import { useApp } from '../contexts/AppContext'

const { Text } = Typography

const VIEWED_MR_KEY = 'viewed_mr_items'

interface ViewedMRState {
  [key: string]: boolean
}

interface RelatedMRModalProps {
  open: boolean
  onClose: () => void
}

// 获取 MR 的唯一标识 key
const getMRKey = (item: RelatedMR): string => {
  return `${item.mr.project_id}_${item.mr.iid}`
}

// 从 localStorage 读取已查看的 MR 状态
const getViewedMRs = (): ViewedMRState => {
  try {
    const stored = localStorage.getItem(VIEWED_MR_KEY)
    return stored ? JSON.parse(stored) : {}
  } catch {
    return {}
  }
}

// 保存已查看的 MR 状态到 localStorage
const saveViewedMR = (key: string) => {
  try {
    const viewed = getViewedMRs()
    viewed[key] = true
    localStorage.setItem(VIEWED_MR_KEY, JSON.stringify(viewed))
  } catch {
    // ignore storage errors
  }
}

// 清理 localStorage 中不再存在的 MR 记录
const cleanupViewedMRs = (currentItems: RelatedMR[]) => {
  try {
    const viewed = getViewedMRs()
    const currentKeys = new Set(currentItems.map(getMRKey))
    const cleaned: ViewedMRState = {}

    for (const [key, value] of Object.entries(viewed)) {
      if (currentKeys.has(key)) {
        cleaned[key] = value
      }
    }

    localStorage.setItem(VIEWED_MR_KEY, JSON.stringify(cleaned))
  } catch {
    // ignore storage errors
  }
}

const RelatedMRModal: FC<RelatedMRModalProps> = ({ open, onClose }) => {
  const { setCurrentProject, setCurrentMR } = useApp()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<RelatedMR[]>([])
  const [viewedMRs, setViewedMRs] = useState<ViewedMRState>({})

  // 检查 MR 是否是新的（未查看过）
  const isNewMR = useCallback((item: RelatedMR): boolean => {
    return !viewedMRs[getMRKey(item)]
  }, [viewedMRs])

  useEffect(() => {
    if (open) {
      loadData()
    }
  }, [open])

  const loadData = async () => {
    setLoading(true)
    try {
      const result = await api.listRelatedMergeRequests('opened')
      // 清理 localStorage 中不再存在的 MR 记录
      cleanupViewedMRs(result)
      // 更新本地状态
      setViewedMRs(getViewedMRs())
      setData(result)
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || '加载 MR 列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleOpenMR = async (item: RelatedMR) => {
    if (!item.project) return

    // 标记为已查看
    const key = getMRKey(item)
    saveViewedMR(key)
    setViewedMRs(getViewedMRs())

    // 切换项目
    setCurrentProject(item.project)

    // 设置当前 MR
    setCurrentMR(item.mr)

    onClose()
  }

  const handleApprove = async (item: RelatedMR) => {
    if (!item.project) return

    try {
      await api.approveMergeRequest(
        item.project.id.toString(),
        item.mr.iid
      )
      message.success('已批准')
      // 标记为已查看
      const key = getMRKey(item)
      saveViewedMR(key)
      setViewedMRs(getViewedMRs())
      // 重新加载数据
      loadData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || '批准失败')
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
      // 重新加载数据
      loadData()
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || '取消批准失败')
    }
  }

  const handleSendLGTM = async (item: RelatedMR) => {
    if (!item.project) return

    try {
      await api.createMergeRequestNote(
        item.project.id.toString(),
        item.mr.iid,
        { body: 'lgtm' }
      )
      message.success('已发送 lgtm')
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || '发送失败')
    }
  }

  const handleCopyLink = async (item: RelatedMR) => {
    try {
      await navigator.clipboard.writeText(item.mr.web_url)
      message.success('链接已复制到剪贴板')
    } catch (err) {
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
    <Modal
      title="与我相关的 Merge Requests"
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
                        {item.mr.approved_by_current_user && (
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
                          <Tag color="purple" style={{ fontSize: 11, margin: 0 }}>
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
                  <Button
                    size="small"
                    onClick={() => handleSendLGTM(item)}
                  >
                    发送 lgtm
                  </Button>
                  {item.mr.approved_by_current_user ? (
                    <Button
                      size="small"
                      danger
                      onClick={() => handleUnapprove(item)}
                    >
                      取消批准
                    </Button>
                  ) : (
                    <Button
                      size="small"
                      type="primary"
                      onClick={() => handleApprove(item)}
                    >
                      批准
                    </Button>
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
  )
}

export default RelatedMRModal
