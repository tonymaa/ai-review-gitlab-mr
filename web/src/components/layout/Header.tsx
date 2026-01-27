/**
 * 顶部导航栏组件
 */

import { type FC, useState } from 'react'
import { Layout, Button, Space, Dropdown, Avatar, Typography } from 'antd'
import {
  SettingOutlined,
  GitlabOutlined,
  UserOutlined,
  LogoutOutlined,
  UnorderedListOutlined,
  ProjectOutlined,
  DownOutlined,
} from '@ant-design/icons'
import { useApp } from '../../contexts/AppContext'
import ProjectSelectorModal from './ProjectSelectorModal'
import type { Project } from '../../types'

const { Header: AntHeader } = Layout
const { Text } = Typography

interface HeaderProps {
  onOpenConnect: () => void
  onOpenConfig: () => void
  onOpenRelatedMR: () => void
}

const Header: FC<HeaderProps> = ({ onOpenConnect, onOpenConfig, onOpenRelatedMR }) => {
  const { isConnected, currentUser, currentProject, setCurrentProject } = useApp()
  const [projectModalOpen, setProjectModalOpen] = useState(false)

  const handleSelectProject = (project: Project) => {
    setCurrentProject(project)
  }

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: (
        <div>
          <div>{currentUser?.name || '用户'}</div>
          <div style={{ fontSize: 12, opacity: 0.7 }}>
            @{currentUser?.username || 'user'}
          </div>
        </div>
      ),
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'disconnect',
      icon: <LogoutOutlined />,
      label: '断开连接',
      onClick: () => {
        window.location.reload()
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
          <Text strong style={{ color: '#fff' }}>GitLab AI Review</Text>
          {isConnected && (
            <>
              <div style={{ width: 1, height: 16, background: '#303030' }} />
              <div
                onClick={() => setProjectModalOpen(true)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 12px',
                  borderRadius: 4,
                  background: '#1f1f1f',
                  cursor: 'pointer',
                  border: '1px solid #303030',
                  transition: 'border-color 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = '#1890ff'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = '#303030'
                }}
              >
                <ProjectOutlined style={{ color: currentProject ? '#1890ff' : '#888' }} />
                <Text style={{ color: currentProject ? '#fff' : '#888' }}>
                  {currentProject?.name || '选择项目'}
                </Text>
                <DownOutlined style={{ fontSize: 10, color: '#888' }} />
              </div>
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
            <>
              <Button
                icon={<UnorderedListOutlined />}
                size="small"
                onClick={onOpenRelatedMR}
              >
                与我相关
              </Button>

              <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
                <Avatar
                  size="small"
                  src={currentUser?.avatar_url}
                  icon={<UserOutlined />}
                  style={{ cursor: 'pointer' }}
                />
              </Dropdown>

              <Button
                type="text"
                icon={<SettingOutlined />}
                size="small"
                onClick={onOpenConfig}
              />
            </>
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
