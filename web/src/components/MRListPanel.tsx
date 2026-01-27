/**
 * MR 列表面板组件
 */

import { type FC, useState, useEffect } from 'react'
import { List, Tag, Input, Select, Space, Typography, Empty, Spin, Badge, Tooltip } from 'antd'
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

const MRListPanel: FC<MRListPanelProps> = ({
  mergeRequests,
  onSelectMR,
}) => {
  const { currentProject, setCurrentMR, setMergeRequests } = useApp()
  const [searchText, setSearchText] = useState('')
  const [stateFilter, setStateFilter] = useState<'opened' | 'closed' | 'merged' | 'all'>('opened')
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
  }, [currentProject, stateFilter, setCurrentMR, setMergeRequests])

  const loadMergeRequests = async () => {
    if (!currentProject) return

    setListLoading(true)
    try {
      const mrs = await api.listMergeRequests(
        currentProject.id.toString(),
        stateFilter
      )
      setMergeRequests(mrs)
    } catch (err) {
      console.error('Failed to load MRs:', err)
    } finally {
      setListLoading(false)
    }
  }

  const filteredMRs = mergeRequests.filter(mr => {
    if (!searchText) return true
    const searchLower = searchText.toLowerCase()
    return (
      mr.title.toLowerCase().includes(searchLower) ||
      mr.author_name.toLowerCase().includes(searchLower) ||
      mr.source_branch.toLowerCase().includes(searchLower) ||
      mr.target_branch.toLowerCase().includes(searchLower)
    )
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
            value={stateFilter}
            onChange={setStateFilter}
            style={{ width: '100%' }}
            disabled={!currentProject}
          >
            <Option value="opened">
              <Badge count={getStateCount('opened')} showZero>
                打开中
              </Badge>
            </Option>
            <Option value="merged">
              <Badge count={getStateCount('merged')} showZero>
                已合并
              </Badge>
            </Option>
            <Option value="closed">
              <Badge count={getStateCount('closed')} showZero>
                已关闭
              </Badge>
            </Option>
            <Option value="all">
              <Badge count={mergeRequests.length} showZero>
                全部
              </Badge>
            </Option>
          </Select>
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
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {mr.author_name}
                        </Text>
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
