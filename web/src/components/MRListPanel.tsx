/**
 * MR 列表面板组件
 */

import React, { type FC, useState, useEffect, useMemo } from 'react'
import { List, Tag, Input, Select, Space, Typography, Empty, Spin, Badge, Tooltip, Checkbox } from 'antd'
import {
  ClockCircleOutlined,
  CloseCircleOutlined,
  MergeCellsOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import type { MergeRequest } from '../types'
import { api } from '../api/client'
import { useApp } from '../contexts/AppContext'

const { Search } = Input
const { Option } = Select
const { Text } = Typography

interface MRListPanelProps {
  mergeRequests: MergeRequest[]
  onSelectMR: (mr: MergeRequest) => void
}

// 格式化相对时间（与 CommentPanel 中使用的一致）
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

const MRListPanel: FC<MRListPanelProps> = ({
  mergeRequests,
  onSelectMR,
}) => {
  const {
    currentProject, currentMR, setCurrentMR, setMergeRequests, setError, currentUser,
    mrListFilterRelated, setMrListFilterRelated, mrListFilterState, setMrListFilterState
  } = useApp()
  const [searchText, setSearchText] = useState('')
  const [authorFilter, setAuthorFilter] = useState<string>('')
  const [listLoading, setListLoading] = useState(false)

  // 当项目变化时加载 MR 列表
  useEffect(() => {
    if (currentProject) {
      loadMergeRequests()
    } else {
      // 清空选择
      setCurrentMR(null)
      setMergeRequests([])
    }
  }, [currentProject, mrListFilterState, setCurrentMR, setMergeRequests])

  const loadMergeRequests = async () => {
    if (!currentProject) return

    setListLoading(true)
    try {
      const mrs = await api.listMergeRequests(
        currentProject.id.toString(),
        mrListFilterState
      )
      setMergeRequests(mrs)
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || '加载 MR 列表失败'
      setError(errorMsg)
      console.error('Failed to load MRs:', err)
    } finally {
      setListLoading(false)
    }
  }

  // 获取所有作者列表（去重），并将当前用户排在最前面
  const authors = useMemo(() => {
    const authorSet = new Set<string>()
    mergeRequests.forEach(mr => {
      if (mr.author_name) {
        authorSet.add(mr.author_name)
      }
    })
    let authorList = Array.from(authorSet).sort()

    // 将当前用户排在最前面
    if (currentUser?.name && authorList.includes(currentUser.name)) {
      authorList = authorList.filter(name => name !== currentUser.name)
      authorList.unshift(currentUser.name)
    }

    return authorList
  }, [mergeRequests, currentUser])

  const filteredMRs = mergeRequests.filter(mr => {
    // 搜索文本筛选
    if (searchText) {
      const searchLower = searchText.toLowerCase()
      const matchesSearch =
        mr.title.toLowerCase().includes(searchLower) ||
        mr.author_name.toLowerCase().includes(searchLower) ||
        mr.source_branch.toLowerCase().includes(searchLower) ||
        mr.target_branch.toLowerCase().includes(searchLower)
      if (!matchesSearch) return false
    }

    // "与我相关"筛选（reviewer或assignee包含当前用户）
    if (mrListFilterRelated && currentUser) {
      const isReviewer = mr.reviewers?.some(r => r.name === currentUser.name || r.id === currentUser.id)
      const isAssignee = mr.assignees?.some(a => a.name === currentUser.name || a.id === currentUser.id)
      if (!isReviewer && !isAssignee) return false
    }

    // 作者筛选
    if (authorFilter && mr.author_name !== authorFilter) {
      return false
    }

    return true
  })

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

  const getStateCount = (state: string) => {
    return mergeRequests.filter(mr => mr.state === state).length
  }

  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* 头部：搜索和筛选 */}
      <div style={{
        padding: '12px',
        borderBottom: '1px solid #303030',
      }}>
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Search
            placeholder="搜索 MR..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
          />

          <Select
            value={mrListFilterState}
            onChange={setMrListFilterState}
            style={{ width: '100%' }}
            disabled={!currentProject}
          >
            <Option value="opened">
              <Badge offset={[22, 5]} size='small' count={getStateCount('opened')} showZero>
                  Opened
              </Badge>
            </Option>
            <Option value="merged">
              <Badge offset={[22, 5]} size='small' count={getStateCount('merged')} showZero>
                Merged
              </Badge>
            </Option>
            <Option value="closed">
              <Badge offset={[22, 5]} size='small' count={getStateCount('closed')} showZero>
                Closed
              </Badge>
            </Option>
            <Option value="all">
              <Badge offset={[22, 5]} size='small' count={mergeRequests.length} showZero>
                全部
              </Badge>
            </Option>
          </Select>

          <Select
            placeholder="筛选作者"
            value={authorFilter || undefined}
            onChange={setAuthorFilter}
            style={{ width: '100%' }}
            disabled={!currentProject}
            allowClear
          >
            {authors.map(author => (
              <Option key={author} value={author}>
                {author} {author === currentUser?.name ? '(我)' : ''}
              </Option>
            ))}
          </Select>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Checkbox
              checked={mrListFilterRelated}
              onChange={(e) => setMrListFilterRelated(e.target.checked)}
              disabled={!currentProject || !currentUser}
            >
              与我相关
            </Checkbox>
          </div>
        </Space>
      </div>

      {/* MR 列表 */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        <Spin spinning={listLoading}>
          {!currentProject ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="请先选择项目"
              style={{ marginTop: 60 }}
            />
          ) : filteredMRs.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={searchText ? '没有匹配的 MR' : '暂无 MR'}
              style={{ marginTop: 60 }}
            />
          ) : (
            <List
              dataSource={filteredMRs}
              renderItem={(mr) => (
                <List.Item
                  key={mr.iid}
                  style={{
                    padding: '12px',
                    borderBottom: '1px solid #303030',
                    cursor: 'pointer',
                    backgroundColor: currentMR?.iid === mr.iid ? '#1a3a5c' : 'transparent',
                  }}
                  onClick={() => onSelectMR(mr)}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Text ellipsis style={{ maxWidth: 200 }}>
                          {mr.title}
                        </Text>
                        {mr.approved_by_current_user && (
                          <Tooltip title="已批准">
                            <CheckCircleOutlined style={{ color: '#52c41a' }} />
                          </Tooltip>
                        )}
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={0}>
                        <Space size={4}>
                          {getStateTag(mr.state)}
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            !{mr.iid}
                          </Text>
                        </Space>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {mr.source_branch} → {mr.target_branch}
                        </Text>
                        <Space size={4}>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {mr.author_name}
                          </Text>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            ·
                          </Text>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {formatTimeAgo(mr.created_at)}
                          </Text>
                        </Space>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Spin>
      </div>
    </div>
  )
}

export default MRListPanel
