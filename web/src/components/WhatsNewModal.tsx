/**
 * What's New 弹窗：展示 GitHub Release notes
 *
 * 受控组件：由父级通过 open 控制显示。首次打开时拉取数据。
 * 关闭时调用 onClose，并把当前 release id 写入 localStorage 标记为已读。
 */

import { type FC, useEffect, useState, useCallback } from 'react'
import { Modal, Tag, Typography, Space, Button, Spin } from 'antd'
import { ExportOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import { api, type WhatsNewRelease } from '../api/client'
import { markReleaseSeen } from '../utils/whatsNew'

const { Text, Link } = Typography

interface WhatsNewModalProps {
  open: boolean
  onClose: () => void
}

const WhatsNewModal: FC<WhatsNewModalProps> = ({ open, onClose }) => {
  const [release, setRelease] = useState<WhatsNewRelease | null>(null)
  const [loading, setLoading] = useState(false)
  const [fetched, setFetched] = useState(false)

  const fetchLatest = useCallback(async () => {
    setLoading(true)
    try {
      const r = await api.getWhatsNewLatest()
      setRelease(r)
      setFetched(true)
    } catch {
      // 静默失败
    } finally {
      setLoading(false)
    }
  }, [])

  // 首次打开时拉取
  useEffect(() => {
    if (open && !fetched) {
      fetchLatest()
    }
  }, [open, fetched, fetchLatest])

  const handleClose = () => {
    if (release) {
      markReleaseSeen(release.id)
    }
    onClose()
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
        {release ? (
          <>
            <Typography.Title level={4}>{release.name}</Typography.Title>
            <div className="whats-new-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
              <ReactMarkdown>{release.body || '本次发布没有额外说明'}</ReactMarkdown>
            </div>
          </>
        ) : !loading ? (
          <Text type="secondary">暂无可显示的更新信息</Text>
        ) : null}
      </Spin>
    </Modal>
  )
}

export default WhatsNewModal
