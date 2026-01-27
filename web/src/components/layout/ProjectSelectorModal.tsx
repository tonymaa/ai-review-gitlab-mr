/**
 * 项目选择模态框组件
 */

import { type FC, useState, useEffect } from 'react'
import { Modal, List, Input, Typography, Space, Spin, Empty, Tag } from 'antd'
import { SearchOutlined, ProjectOutlined } from '@ant-design/icons'
import type { Project } from '../../types'
import { api } from '../../api/client'

const { Search } = Input
const { Text, Title } = Typography

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

  const loadProjects = async (search?: string) => {
    setLoading(true)
    try {
      const result = await api.listProjects(search)
      setProjects(result)
    } catch (err) {
      console.error('Failed to load projects:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (value: string) => {
    setSearchText(value)
    loadProjects(value || undefined)
  }

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
          onChange={(e) => handleSearch(e.target.value)}
          prefix={<SearchOutlined />}
        />

        <div style={{ maxHeight: 400, overflowY: 'auto' }}>
          <Spin spinning={loading}>
            {projects.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={searchText ? '无匹配项目' : '暂无项目'}
              />
            ) : (
              <List
                dataSource={projects}
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
