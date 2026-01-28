/**
 * 顶部导航栏组件
 */

import { type FC, useState, useMemo } from 'react'
import { Layout, Button, Space, Dropdown, Avatar, Typography, Tag, Tooltip } from 'antd'
import {
  SettingOutlined,
  GitlabOutlined,
  UserOutlined,
  LogoutOutlined,
  UnorderedListOutlined,
  ProjectOutlined,
  DownOutlined,
  PlusOutlined,
  DeleteOutlined,
  SunOutlined,
  MoonOutlined,
  GithubOutlined,
} from '@ant-design/icons'
import { useApp } from '../../contexts/AppContext'
import ProjectSelectorModal from './ProjectSelectorModal'
import type { Project } from '../../types'
import type { MenuProps } from 'antd'

const { Header: AntHeader } = Layout
const { Text } = Typography

interface HeaderProps {
  onOpenConnect: () => void
  onOpenConfig: () => void
  onOpenRelatedMR: () => void
}

const Header: FC<HeaderProps> = ({ onOpenConnect, onOpenConfig, onOpenRelatedMR }) => {
  const { isConnected, user, logout, projects, addProject, removeProject, currentProject, setCurrentProject, theme, toggleTheme } = useApp()
  const [projectModalOpen, setProjectModalOpen] = useState(false)

  const handleSelectProject = (project: Project) => {
    addProject(project)
    setCurrentProject(project)
  }

  // 构建项目切换菜单
  const projectMenuItems: MenuProps['items'] = useMemo(() => {
    const items: MenuProps['items'] = [
      {
        key: 'add',
        icon: <PlusOutlined />,
        label: '添加项目',
        onClick: () => setProjectModalOpen(true),
      },
    ]

    if (projects.length > 0) {
      items.push({ type: 'divider' as const })

      projects.forEach(project => {
        items.push({
          key: `project-${project.id}`,
          icon: <ProjectOutlined />,
          label: (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
              <span>{project.name}</span>
              <Space size="small">
                {project.id === currentProject?.id && <Tag color="blue">当前</Tag>}
                <DeleteOutlined
                  style={{ fontSize: 12, color: '#ff4d4f' }}
                  onClick={(e) => {
                    e.stopPropagation()
                    removeProject(project.id)
                  }}
                />
              </Space>
            </div>
          ),
          onClick: () => setCurrentProject(project),
        })
      })
    }

    return items
  }, [projects, currentProject, setCurrentProject, removeProject])

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: (
        <div>
          <div>{user?.username || '用户'}</div>
          <div style={{ fontSize: 12, opacity: 0.7 }}>
            已登录
          </div>
        </div>
      ),
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: async () => {
        await logout()
      },
    },
  ]

  return (
    <>
      <AntHeader style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        height: 48,
      }}>
        {/* 左侧：Logo 和项目名称 */}
        <Space size="middle">
          <GitlabOutlined style={{ fontSize: 20 }} />
          <Text strong style={{ color: 'var(--text-primary)' }}>GitLab AI Review</Text>
          {isConnected && (
            <>
              <div style={{ width: 1, height: 16, background: 'var(--border-color)' }} />
              <Dropdown menu={{ items: projectMenuItems }} trigger={['click']} placement="bottomLeft">
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '4px 12px',
                    borderRadius: 4,
                    background: 'var(--bg-tertiary)',
                    cursor: 'pointer',
                    border: '1px solid var(--border-color)',
                    transition: 'border-color 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#1890ff'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-color)'
                  }}
                >
                  <ProjectOutlined style={{ color: currentProject ? '#1890ff' : 'var(--text-secondary)' }} />
                  <Text style={{ color: currentProject ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                    {currentProject?.name || `选择项目 (${projects.length})`}
                  </Text>
                  <DownOutlined style={{ fontSize: 10, color: 'var(--text-secondary)' }} />
                </div>
              </Dropdown>
            </>
          )}
        </Space>

        {/* 右侧：操作按钮 */}
        <Space size="small">
          {!isConnected && (
            <Button type="primary" size="small" onClick={onOpenConnect}>
              连接 GitLab
            </Button>
          )}

          {isConnected && (
              <Button
                icon={<UnorderedListOutlined />}
                size="small"
                onClick={onOpenRelatedMR}
              >
                与我相关
              </Button>
          )}

          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Avatar
              size="small"
              icon={<UserOutlined />}
              style={{ cursor: 'pointer' }}
            />
          </Dropdown>

          {/* 暂时隐藏主题切换按钮
          <Tooltip title={theme === 'dark' ? '切换到明亮模式' : '切换到暗黑模式'}>
            <Button
              type="text"
              icon={theme === 'dark' ? <MoonOutlined /> : <SunOutlined />}
              size="small"
              onClick={toggleTheme}
            />
          </Tooltip>
          */}

          <Tooltip title="GitHub">
            <a
              href="https://github.com/tonymaa/ai-review-gitlab-mr"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--text-primary)' }}
            >
              <Button type="text" icon={<GithubOutlined />} size="small" />
            </a>
          </Tooltip>

          {isConnected && (
              <Button
                type="text"
                icon={<SettingOutlined />}
                size="small"
                onClick={onOpenConfig}
              />
          )}
        </Space>
      </AntHeader>

      {/* 项目选择模态框 */}
      <ProjectSelectorModal
        open={projectModalOpen}
        onClose={() => setProjectModalOpen(false)}
        onSelectProject={handleSelectProject}
        currentProjectId={currentProject?.id}
      />
    </>
  )
}

export default Header
