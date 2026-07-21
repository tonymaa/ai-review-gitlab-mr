/**
 * What's New 弹窗：首次看到新 GitHub Release 时展示更新内容
 */

import { type FC, useEffect, useState } from 'react'
import { Modal, Tag, Typography, Space, Button, Spin } from 'antd'
import { ExportOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import { api, type WhatsNewRelease } from '../api/client'

const { Text, Link } = Typography

const STORAGE_KEY = 'last_seen_release_id'

const getLastSeenId = (): number | null => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return null
    const n = Number.parseInt(stored, 10)
    return Number.isNaN(n) ? null : n
  } catch {
    return null
  }
}

const markSeen = (id: number): void => {
  try {
    localStorage.setItem(STORAGE_KEY, String(id))
  } catch {
    // ignore
  }
}

interface WhatsNewModalProps {
  // 强制显示（用于调试或手动触发），不传则按 localStorage 判断
  forceOpen?: boolean
}

const WhatsNewModal: FC<WhatsNewModalProps> = ({ forceOpen }) => {
  // 懒初始化 loading：只有会发起请求时才置为 true，避免 effect 内同步 setState
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(() => {
    if (forceOpen) return true
    // 首次访问（无 lastSeenId）不弹窗也不请求
    return getLastSeenId() !== null
  })
  const [release, setRelease] = useState<WhatsNewRelease | null>(null)

  useEffect(() => {
    // 强制打开时直接拉数据展示
    if (forceOpen) {
      let cancelled = false
      api.getWhatsNewLatest()
        .then((r) => {
          if (cancelled || !r) return
          setRelease(r)
          setOpen(true)
        })
        .catch(() => {
          // 静默失败
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
      return () => {
        cancelled = true
      }
    }

    // 首次访问（无 lastSeenId）不弹窗，避免噪音
    const lastSeen = getLastSeenId()
    if (lastSeen === null) return

    let cancelled = false
    api.getWhatsNewLatest()
      .then((r) => {
        if (cancelled || !r) return
        // 只有比上次见过的新才弹
        if (r.id !== lastSeen) {
          setRelease(r)
          setOpen(true)
        }
      })
      .catch(() => {
        // 静默失败，不打扰用户
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [forceOpen])

  const handleClose = () => {
    if (release) {
      markSeen(release.id)
    }
    setOpen(false)
  }

  return (
    <Modal
      title={
        release ? (
          <Space>
            <span>🎉 有新版本啦</span>
            <Tag color="blue">{release.tag_name}</Tag>
            <Text type="secondary" style={{ fontSize: 12, fontWeight: 'normal' }}>
              {release.published_at?.slice(0, 10)}
            </Text>
          </Space>
        ) : (
          '🎉 有新版本啦'
        )
      }
      open={open}
      onCancel={handleClose}
      width={640}
      footer={
        <Space>
          {release && (
            <Link href={release.html_url} target="_blank" rel="noreferrer">
              <Button icon={<ExportOutlined />}>在 GitHub 查看</Button>
            </Link>
          )}
          <Button type="primary" onClick={handleClose}>
            知道了
          </Button>
        </Space>
      }
    >
      <Spin spinning={loading}>
        {release && (
          <>
            <Typography.Title level={4}>{release.name}</Typography.Title>
            <div className="whats-new-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
              <ReactMarkdown>{release.body || '本次发布没有额外说明'}</ReactMarkdown>
            </div>
          </>
        )}
      </Spin>
    </Modal>
  )
}

export default WhatsNewModal
