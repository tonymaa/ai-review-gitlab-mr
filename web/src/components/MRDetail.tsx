/**
 * MR 详情组件
 */

import { FC, useEffect, useState } from 'react'
import { Card, Tag, Space, Typography, Button, message, Spin } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons'
import type { MergeRequest } from '../types'
import { api } from '../api/client'

const { Text, Paragraph } = Typography

interface MRDetailProps {
  project_id: string
  mr: MergeRequest
  onRefresh?: () => void
}

interface ApprovalState {
  approved: boolean
  approved_by: Array<{ id: number; name: string; username: string; avatar_url?: string }>
  approvers_required: number
  approvals_left: number
}

const MRDetail: FC<MRDetailProps> = ({ project_id, mr, onRefresh }) => {
  const [approvalState, setApprovalState] = useState<ApprovalState | null>(null)
  const [loadingApproval, setLoadingApproval] = useState(false)

  useEffect(() => {
    loadApprovalState()
  }, [mr])

  const loadApprovalState = async () => {
    setLoadingApproval(true)
    try {
      const state = await api.getMergeRequestApprovalState(project_id, mr.iid)
      setApprovalState(state)
    } catch (err: any) {
      console.error('获取批准状态失败:', err)
    } finally {
      setLoadingApproval(false)
    }
  }

  const handleApprove = async () => {
    try {
      await api.approveMergeRequest(project_id, mr.iid)
      message.success('已批准')
      loadApprovalState()
      onRefresh?.()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '批准失败')
    }
  }

  const handleUnapprove = async () => {
    try {
      await api.unapproveMergeRequest(project_id, mr.iid)
      message.success('已取消批准')
      loadApprovalState()
      onRefresh?.()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '取消批准失败')
    }
  }

  const getStateIcon = () => {
    switch (mr.state) {
      case 'opened':
        return <SyncOutlined spin={false} style={{ color: '#52c41a' }} />
      case 'closed':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
      case 'merged':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />
      default:
        return null
    }
  }

  const getStateTag = () => {
    switch (mr.state) {
      case 'opened':
        return <Tag color="green" icon={<SyncOutlined />}>Open</Tag>
      case 'closed':
        return <Tag color="red" icon={<CloseCircleOutlined />}>Closed</Tag>
      case 'merged':
        return <Tag color="blue" icon={<CheckCircleOutlined />}>Merged</Tag>
      default:
        return <Tag>{mr.state}</Tag>
    }
  }

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)

    const intervals = {
      年: 31536000,
      月: 2592000,
      周: 604800,
      天: 86400,
      小时: 3600,
      分钟: 60,
    }

    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
      const interval = Math.floor(seconds / secondsInUnit)
      if (interval >= 1) {
        return `${interval} ${unit}前`
      }
    }
    return '刚刚'
  }

  return (
    <Card
      size="small"
      style={{ margin: '8px', borderRadius: 4 }}
      styles={{ body: { padding: '12px' } }}
    >
      {/* 标题和状态 */}
      <div style={{ marginBottom: 8 }}>
        <Space size="small" wrap>
          {getStateTag()}
          <Text strong style={{ fontSize: 14 }}>
            {mr.title}
          </Text>
        </Space>
      </div>

      {/* 作者和分支信息 */}
      <div style={{ marginBottom: 8, fontSize: 12 }}>
        <Space size="small" wrap>
          <Text type="secondary">
            {mr.author_name} requested to merge
          </Text>
          <Tag color="cyan">{mr.source_branch}</Tag>
          <Text type="secondary">into</Text>
          <Tag color="geekblue">{mr.target_branch}</Tag>
          <Text type="secondary">
            <ClockCircleOutlined style={{ marginRight: 4 }} />
            {formatTimeAgo(mr.created_at)}
          </Text>
        </Space>
      </div>

      {/* 描述 */}
      {mr.description && (
        <Paragraph
          style={{
            marginBottom: 8,
            fontSize: 12,
            color: '#d9d9d9',
          }}
          ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
        >
          {mr.description}
        </Paragraph>
      )}

      {/* 批准状态 */}
      <div style={{ marginBottom: 8 }}>
        <Spin spinning={loadingApproval} size="small">
          <Space size="small" wrap>
            {approvalState && (
              <>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  批准:
                </Text>
                {approvalState.approved_by.length > 0 ? (
                  approvalState.approved_by.map((approver) => (
                    <Tag key={approver.id} color="green" style={{ fontSize: 11 }}>
                      {approver.name || approver.username}
                    </Tag>
                  ))
                ) : (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    暂无批准
                  </Text>
                )}
                {approvalState.approvals_left > 0 && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    还需要 {approvalState.approvals_left} 个批准
                  </Text>
                )}
                {mr.state === 'opened' && (
                  <>
                    {approvalState.approved ? (
                      <Button
                        type="default"
                        size="small"
                        onClick={handleUnapprove}
                        style={{ fontSize: 12 }}
                      >
                        取消批准
                      </Button>
                    ) : (
                      <Button
                        type="primary"
                        size="small"
                        onClick={handleApprove}
                        style={{ fontSize: 12 }}
                      >
                        批准
                      </Button>
                    )}
                  </>
                )}
              </>
            )}
          </Space>
        </Spin>
      </div>

      {/* Assignees 和 Reviewers */}
      <div>
        <Space size="middle" wrap>
          {mr.assignees && mr.assignees.length > 0 && (
            <Space size="small">
              <Text type="secondary" style={{ fontSize: 12 }}>
                指派人:
              </Text>
              {mr.assignees.map((assignee) => (
                <Tag key={assignee.id} color="blue" style={{ fontSize: 11 }}>
                  {assignee.name}
                </Tag>
              ))}
            </Space>
          )}
          {mr.reviewers && mr.reviewers.length > 0 && (
            <Space size="small">
              <Text type="secondary" style={{ fontSize: 12 }}>
                审查者:
              </Text>
              {mr.reviewers.map((reviewer) => (
                <Tag key={reviewer.id} color="purple" style={{ fontSize: 11 }}>
                  {reviewer.name}
                </Tag>
              ))}
            </Space>
          )}
        </Space>
      </div>
    </Card>
  )
}

export default MRDetail
