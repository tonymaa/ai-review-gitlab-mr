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
            <List.Item
              actions={[
                item.mr.approved_by_current_user ? (
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
                ),
                <Button
                  size="small"
                  onClick={() => handleOpenMR(item)}
                >
                  打开
                </Button>,
              ]}
            >
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
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {item.project?.name || 'Unknown'} · !{item.mr.iid}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {item.mr.source_branch} → {item.mr.target_branch}
                    </Text>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Spin>
    </Modal>
  )
}

export default RelatedMRModal
