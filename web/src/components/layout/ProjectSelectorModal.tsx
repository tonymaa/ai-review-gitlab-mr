/**
 * 项目选择模态框组件
 */

import { type FC, useState, useEffect, useMemo } from 'react'
import { Modal, List, Input, Typography, Space, Spin, Empty, Tag, message } from 'antd'
import { SearchOutlined, ProjectOutlined } from '@ant-design/icons'
import type { Project } from '../../types'
import { api } from '../../api/client'

const { Search } = Input
const { Text } = Typography

interface ProjectSelectorModalProps {
  open: boolean
  onClose: () => void
  onSelectProject: (project: Project) => void
  currentProjectId?: number
}

const ProjectSelectorModal: FC<ProjectSelectorModalProps> = ({
  open,
  onClose,
  onSelectProject,
  currentProjectId,
}) => {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const [searchText, setSearchText] = useState('')

  // 加载项目列表
  useEffect(() => {
    if (open) {
      loadProjects()
    }
  }, [open])

  const loadProjects = async () => {
    setLoading(true)
    try {
      const result = await api.listProjects()
      setProjects(result)
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || '加载项目列表失败')
    } finally {
      setLoading(false)
    }
  }

  // 本地过滤项目
  const filteredProjects = useMemo(() => {
    if (!searchText) return projects
    const searchLower = searchText.toLowerCase()
    return projects.filter(project =>
      project.name.toLowerCase().includes(searchLower) ||
      project.path_with_namespace.toLowerCase().includes(searchLower) ||
      (project.description && project.description.toLowerCase().includes(searchLower))
    )
  }, [projects, searchText])

  const handleSelect = (project: Project) => {
    onSelectProject(project)
    onClose()
  }

  return (
    <Modal
      title="选择项目"
      open={open}
      onCancel={onClose}
      footer={null}
      width={600}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Search
          placeholder="搜索项目..."
          allowClear
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          prefix={<SearchOutlined />}
        />

        <div style={{ maxHeight: 400, overflowY: 'auto' }}>
          <Spin spinning={loading}>
            {filteredProjects.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={searchText ? '无匹配项目' : '暂无项目'}
              />
            ) : (
              <List
                dataSource={filteredProjects}
                renderItem={(project) => (
                  <List.Item
                    key={project.id}
                    style={{
                      cursor: 'pointer',
                      padding: '12px',
                      borderRadius: 4,
                      background: project.id === currentProjectId ? '#1f1f1f' : 'transparent',
                      border: project.id === currentProjectId ? '1px solid #1890ff' : '1px solid transparent',
                    }}
                    onClick={() => handleSelect(project)}
                  >
                    <List.Item.Meta
                      avatar={<ProjectOutlined style={{ fontSize: 24, color: '#1890ff' }} />}
                      title={
                        <Space>
                          <Text strong>{project.name}</Text>
                          {project.id === currentProjectId && (
                            <Tag color="blue">当前</Tag>
                          )}
                        </Space>
                      }
                      description={
                        <Space direction="vertical" size={0}>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {project.path_with_namespace}
                          </Text>
                          {project.description && (
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {project.description}
                            </Text>
                          )}
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Spin>
        </div>
      </Space>
    </Modal>
  )
}

export default ProjectSelectorModal
