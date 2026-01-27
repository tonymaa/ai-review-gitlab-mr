/**
 * GitLab AI Review - 主应用组件
 */

import { useEffect, useState } from 'react'
import { Layout, message, Spin } from 'antd'
import { AppProvider, useApp } from './contexts/AppContext'
import Header from './components/layout/Header'
import MainLayout from './components/layout/MainLayout'
import ConnectModal from './components/layout/ConnectModal'
import ConfigDrawer from './components/layout/ConfigDrawer'
import RelatedMRModal from './components/RelatedMRModal'
import { api } from './api/client'

const { Content } = Layout

function AppContent() {
  const {
    isConnected,
    loading,
    error,
    setError,
    connectGitLab,
  } = useApp()

  const [connectModalOpen, setConnectModalOpen] = useState(false)
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false)
  const [relatedMROpen, setRelatedMROpen] = useState(false)
  const [initializing, setInitializing] = useState(true)

  // 初始化：检查配置并自动连接
  useEffect(() => {
    const initApp = async () => {
      try {
        const config = await api.getConfig()
        // 检查配置是否存在且有效
        if (config && config.gitlab && config.gitlab.url && config.gitlab.token) {
          try {
            await connectGitLab(config.gitlab.url, config.gitlab.token)
          } catch {
            // 自动连接失败，显示连接对话框
            setConnectModalOpen(true)
          }
        } else {
          setConnectModalOpen(true)
        }
      } catch (err) {
        console.error('Failed to load config:', err)
        // 配置加载失败，显示连接对话框
        setConnectModalOpen(true)
      } finally {
        setInitializing(false)
      }
    }

    initApp()
  }, [connectGitLab])

  // 显示错误消息
  useEffect(() => {
    if (error) {
      message.error(error)
      setError(null)
    }
  }, [error, setError])

  if (initializing) {
    return (
      <div style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <Spin size="large" tip="初始化中..." />
      </div>
    )
  }

  return (
    <Layout style={{ minHeight: '100vh', background: '#000' }}>
      <Header
        onOpenConnect={() => setConnectModalOpen(true)}
        onOpenConfig={() => setConfigDrawerOpen(true)}
        onOpenRelatedMR={() => setRelatedMROpen(true)}
      />

      <Content style={{ padding: '0' }}>
        <MainLayout />
      </Content>

      <ConnectModal
        open={connectModalOpen}
        onClose={() => setConnectModalOpen(false)}
      />

      <ConfigDrawer
        open={configDrawerOpen}
        onClose={() => setConfigDrawerOpen(false)}
      />

      <RelatedMRModal
        open={relatedMROpen}
        onClose={() => setRelatedMROpen(false)}
      />

      {loading && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
        }}>
          <Spin size="large" tip="加载中..." />
        </div>
      )}
    </Layout>
  )
}

function App() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  )
}

export default App
