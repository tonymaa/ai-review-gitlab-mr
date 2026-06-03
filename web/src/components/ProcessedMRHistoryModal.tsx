/**
 * 已处理 MR 历史记录弹窗组件
 */

import { type FC, useState, useEffect } from 'react'
import { Modal, List, Tag, Button, Space, Popconfirm, message, Empty, Spin, Tooltip, Typography } from 'antd'
import { DeleteOutlined, ClearOutlined, ReloadOutlined, FileTextOutlined, LinkOutlined } from '@ant-design/icons'
import { api } from '../api/client'

const { Text } = Typography

interface ProcessedMRItem {
  id: number
  project_id: number
  mr_iid: number
  summary: string | null
  processed_at: string
  web_url?: string
  title?: string
  review_round: number
  review_status: string | null
}

interface ProcessedMRHistoryModalProps {
  open: boolean
  onClose: () => void
}

const ProcessedMRHistoryModal: FC<ProcessedMRHistoryModalProps> = ({ open, onClose }) => {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<ProcessedMRItem[]>([])

  const loadData = async () => {
    setLoading(true)
    try {
      const result = await api.getProcessedHistory(100)
      setData(result)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '加载历史记录失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) {
      loadData()
    }
  }, [open])

  const handleDeleteItem = async (id: number) => {
    try {
      await api.deleteProcessedHistoryItem(id)
      message.success('已删除')
      loadData()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '删除失败')
    }
  }

  const handleClearAll = async () => {
    try {
      await api.clearProcessedHistory()
      message.success('已清空所有记录')
      loadData()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string }
      message.error(error.response?.data?.detail || error.message || '清空失败')
    }
  }

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN')
  }

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginRight: '30px' }}>
          <span>已处理的 MR 历史记录</span>
          <Space>
            <Tooltip title="刷新">
              <Button
                type="text"
                size="small"
                icon={<ReloadOutlined />}
                onClick={loadData}
              />
            </Tooltip>
            <Popconfirm
              title="确认清空"
              description="确定要清空所有历史记录吗？此操作不可恢复。"
              onConfirm={handleClearAll}
              okText="确定"
              cancelText="取消"
            >
              <Button
                type="text"
                size="small"
                danger
                icon={<ClearOutlined />}
              >
                清空全部
              </Button>
            </Popconfirm>
          </Space>
        </div>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={700}
    >
      <Spin spinning={loading}>
        {data.length === 0 ? (
          <Empty description="暂无历史记录" />
        ) : (
          <List
            dataSource={data}
            renderItem={(item) => (
              <List.Item
                actions={[
                  ...(item.web_url ? [
                    <Tooltip key="open" title="在 GitLab 中打开">
                      <Button
                        type="text"
                        size="small"
                        icon={<LinkOutlined />}
                        onClick={() => window.open(item.web_url, '_blank')}
                      />
                    </Tooltip>,
                  ] : []),
                  <Popconfirm
                    key="delete"
                    title="确认删除"
                    description="确定要删除这条记录吗？"
                    onConfirm={() => handleDeleteItem(item.id)}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                    />
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  avatar={<FileTextOutlined style={{ fontSize: 20, color: '#1890ff' }} />}
                  title={
                    <Space>
                      <Tag color="blue">项目 {item.project_id}</Tag>
                      <Tag>!{item.mr_iid}</Tag>
                      <Tag color="purple">Round {item.review_round}</Tag>
                      {item.review_status === 'approved' ? (
                        <Tag color="green">已批准</Tag>
                      ) : item.review_status === 'not_approved' ? (
                        <Tag color="orange">未批准</Tag>
                      ) : (
                        <Tag color="default">未知</Tag>
                      )}
                      <Tag color="green">{formatDateTime(item.processed_at)}</Tag>
                    </Space>
                  }
                  description={
                    item.title ? (
                      <div
                        style={{
                          fontSize: 13,
                          color: '#acacac',
                          fontWeight: 500,
                        }}
                      >
                        {item.title}
                      </div>
                    ) : null
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Spin>
    </Modal>
  )
}

export default ProcessedMRHistoryModal
