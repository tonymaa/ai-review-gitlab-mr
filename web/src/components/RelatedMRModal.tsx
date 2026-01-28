/**
 * 与我相关的 MR 弹窗组件
 */

import { FC, useState, useEffect } from 'react'
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
import type { RelatedMR, MergeRequest } from '../types'
import { api } from '../api/client'
import { useApp } from '../contexts/AppContext'

const { Text } = Typography

interface RelatedMRModalProps {
  open: boolean
  onClose: () => void
}

const RelatedMRModal: FC<RelatedMRModalProps> = ({ open, onClose }) => {
  const { setCurrentProject, setCurrentMR } = useApp()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<RelatedMR[]>([])

  useEffect(() => {
    if (open) {
      loadData()
    }
  }, [open])

  const loadData = async () => {
    setLoading(true)
    try {
      const result = await api.listRelatedMergeRequests('opened')
      setData(result)
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || '加载 MR 列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleOpenMR = async (item: RelatedMR) => {
    if (!item.project) return

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
