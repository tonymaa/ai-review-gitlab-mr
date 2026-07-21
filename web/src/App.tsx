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
import AuthModal from './components/layout/AuthModal'
import WhatsNewModal from './components/WhatsNewModal'
import { getLastSeenReleaseId } from './utils/whatsNew'
import { api } from './api/client'

const { Content } = Layout

function AppContent() {
  const {
    isAuthenticated,
    loading,
    error,
    setError,
    connectGitLab,
    checkAuth,
  } = useApp()

  const [connectModalOpen, setConnectModalOpen] = useState(false)
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false)
  const [relatedMROpen, setRelatedMROpen] = useState(false)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [whatsNewOpen, setWhatsNewOpen] = useState(false)
  // 是否有未读的 release（用于 Header 红点提示）
  const [hasUnseenRelease, setHasUnseenRelease] = useState(false)
  const [initializing, setInitializing] = useState(true)

  // 初始化：检查认证状态
  useEffect(() => {
    const initApp = async () => {
      try {
        await checkAuth()
      } catch (err) {
        console.error('Failed to check auth:', err)
      } finally {
        setInitializing(false)
      }
    }

    initApp()
  }, [checkAuth])

  // 初始化：检查 GitLab 配置并自动连接（仅在已认证后）
  useEffect(() => {
    if (!isAuthenticated) return

    const initGitLab = async () => {
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
      }
    }

    initGitLab()
  }, [isAuthenticated, connectGitLab])

  // 如果未认证，显示登录模态框
  useEffect(() => {
    if (!initializing && !isAuthenticated) {
      setAuthModalOpen(true)
    }
  }, [initializing, isAuthenticated])

  // 显示错误消息
  useEffect(() => {
    if (error) {
      message.error(error)
      setError(null)
    }
  }, [error, setError])

  // 启动时检查是否有未读的 release
  // 首次访问（无 lastSeenId）不自动弹窗，只允许手动触发
  useEffect(() => {
    let cancelled = false
    api.getWhatsNewLatest()
      .then((r) => {
        if (cancelled || !r) return
        const lastSeen = getLastSeenReleaseId()
        if (lastSeen === null) {
          // 首次访问：不弹，仅记录为"已读当前版本"，避免以后重复弹
          // 但 Header 按钮仍可手动触发
          return
        }
        if (r.id !== lastSeen) {
          setHasUnseenRelease(true)
          setWhatsNewOpen(true)
        }
      })
      .catch(() => {
        // 静默失败
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleCloseWhatsNew = () => {
    setWhatsNewOpen(false)
    setHasUnseenRelease(false)
  }

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
    <Layout style={{ minHeight: '100vh', width: '100vw' }} className="app-layout">
      {isAuthenticated ? (
        <>
          <Header
            onOpenConnect={() => setConnectModalOpen(true)}
            onOpenConfig={() => setConfigDrawerOpen(true)}
            onOpenRelatedMR={() => setRelatedMROpen(true)}
            onOpenWhatsNew={() => setWhatsNewOpen(true)}
            hasUnseenRelease={hasUnseenRelease}
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
        </>
      ) : (
        <div style={{
          height: 'calc(100vh - 48px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: 16,
        }}>
          <Spin size="large" tip="加载中..." />
        </div>
      )}

      <AuthModal
        open={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
      />

      <WhatsNewModal open={whatsNewOpen} onClose={handleCloseWhatsNew} />

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
