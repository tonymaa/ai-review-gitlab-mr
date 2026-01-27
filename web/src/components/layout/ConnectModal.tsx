/**
 * 连接 GitLab 弹窗组件
 */

import { FC, useState } from 'react'
import { Modal, Form, Input, message, Typography } from 'antd'
import { useApp } from '../../contexts/AppContext'

const { Title, Text } = Typography

interface ConnectModalProps {
  open: boolean
  onClose: () => void
}

const ConnectModal: FC<ConnectModalProps> = ({ open, onClose }) => {
  const { connectGitLab, setCurrentProject } = useApp()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)

  const handleConnect = async () => {
    try {
      const values = await form.validateFields()
      setLoading(true)

      await connectGitLab(values.url, values.token)

      message.success('连接成功！')

      // 如果有默认项目 ID，加载项目
      if (values.default_project_id) {
        const { api } = await import('../../api/client')
        try {
          const project = await api.getProject(values.default_project_id)
          setCurrentProject(project)
        } catch (err) {
          console.error('Failed to load default project:', err)
        }
      }

      onClose()
    } catch (err: any) {
      console.error('Connect failed:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      title="连接到 GitLab"
      onOk={handleConnect}
      onCancel={onClose}
      okText="连接"
      cancelText="取消"
      confirmLoading={loading}
      width={500}
    >
      <div style={{ marginBottom: 24 }}>
        <Title level={5} style={{ margin: 0 }}>GitLab 服务器配置</Title>
        <Text type="secondary">请输入您的 GitLab 服务器地址和访问令牌</Text>
      </div>

      <Form
        form={form}
        layout="vertical"
        autoComplete="off"
      >
        <Form.Item
          label="GitLab URL"
          name="url"
          rules={[{ required: true, message: '请输入 GitLab 服务器地址' }]}
        >
          <Input
            placeholder="https://gitlab.com"
            prefix="https://"
          />
        </Form.Item>

        <Form.Item
          label="访问令牌 (Token)"
          name="token"
          rules={[{ required: true, message: '请输入访问令牌' }]}
          extra="在 GitLab 用户设置中生成个人访问令牌"
        >
          <Input.Password placeholder="glpat-xxxxxxxxxxxx" />
        </Form.Item>

        <Form.Item
          label="默认项目 ID (可选)"
          name="default_project_id"
          extra="连接后自动加载此项目"
        >
          <Input placeholder="123 或 group/project" />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default ConnectModal
