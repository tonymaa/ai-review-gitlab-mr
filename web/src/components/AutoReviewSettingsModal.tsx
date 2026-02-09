/**
 * 自动 Review 设置弹窗组件
 */

import { useState, useEffect, useImperativeHandle, forwardRef } from 'react'
import { Modal as AntModal, Form, Switch, Select, InputNumber, Divider, message } from 'antd'
import { api } from '../api/client'

// ==================== 类型定义 ====================

export interface AutoReviewConfig {
  enabled: boolean
  creators: string[]  // MR 创建者用户名列表
  interval: number    // 检查间隔（秒）
}

export interface AutoReviewSettingsModalRef {
  open: () => void
}

const AUTO_REVIEW_CONFIG_KEY = 'auto_review_config'

export const getDefaultAutoReviewConfig = (): AutoReviewConfig => ({
  enabled: false,
  creators: [],
  interval: 120,
})

// ==================== 配置管理 ====================

export const getAutoReviewConfig = (): AutoReviewConfig => {
  try {
    const stored = localStorage.getItem(AUTO_REVIEW_CONFIG_KEY)
    return stored ? { ...getDefaultAutoReviewConfig(), ...JSON.parse(stored) } : getDefaultAutoReviewConfig()
  } catch {
    return getDefaultAutoReviewConfig()
  }
}

export const saveAutoReviewConfig = (config: AutoReviewConfig) => {
  try {
    localStorage.setItem(AUTO_REVIEW_CONFIG_KEY, JSON.stringify(config))
    // 触发自定义事件通知配置更新
    window.dispatchEvent(new CustomEvent('autoReviewConfigChanged', { detail: config }))
  } catch {
    // ignore storage errors
  }
}

// ==================== 组件 ====================

interface AutoReviewSettingsModalProps {
  onConfigChange?: (config: AutoReviewConfig) => void
}

export const AutoReviewSettingsModal = forwardRef<AutoReviewSettingsModalRef, AutoReviewSettingsModalProps>(
  ({ onConfigChange }, ref) => {
    const [open, setOpen] = useState(false)
    const [config, setConfig] = useState<AutoReviewConfig>(getDefaultAutoReviewConfig())
    const [availableUsers, setAvailableUsers] = useState<string[]>([])
    const [loadingUsers, setLoadingUsers] = useState(false)
    const [form] = Form.useForm()

    // 暴露 open 方法给父组件
    useImperativeHandle(ref, () => ({
      open: () => {
        // 打开时重新加载配置和用户列表
        setConfig(getAutoReviewConfig())
        form.setFieldsValue(getAutoReviewConfig())
        setOpen(true)
        loadAvailableUsers()
      },
    }))

    // 监听配置变化事件
    useEffect(() => {
      const handleConfigChange = (e: CustomEvent<AutoReviewConfig>) => {
        setConfig(e.detail)
        onConfigChange?.(e.detail)
      }
      window.addEventListener('autoReviewConfigChanged', handleConfigChange as EventListener)
      return () => {
        window.removeEventListener('autoReviewConfigChanged', handleConfigChange as EventListener)
      }
    }, [onConfigChange])

    // 加载可用用户列表（从 GitLab API 获取）
    const loadAvailableUsers = async () => {
      setLoadingUsers(true)
      try {
        const users = await api.listUsers()
        // 提取用户名作为选项
        const usersName = users.map(u => u.name).sort()
        setAvailableUsers(Array.from(new Set(usersName)))
      } catch (err) {
        console.error('加载用户列表失败:', err)
      } finally {
        setLoadingUsers(false)
      }
    }

    const handleOk = () => {
      form.validateFields().then((values) => {
        const newConfig = values as AutoReviewConfig

        // 验证：如果启用但没有配置创建者，提示错误
        if (newConfig.enabled && (!newConfig.creators || newConfig.creators.length === 0)) {
          message.warning('请至少添加一个 MR 创建者')
          return
        }

        saveAutoReviewConfig(newConfig)
        setConfig(newConfig)
        onConfigChange?.(newConfig)
        setOpen(false)
      })
    }

    const handleCancel = () => {
      // 取消时恢复表单为当前配置
      form.setFieldsValue(config)
      setOpen(false)
    }
    

    return (
      <AntModal
        title="自动 Review 并批准设置"
        open={open}
        onCancel={handleCancel}
        onOk={handleOk}
        okText="保存"
        cancelText="取消"
        width={500}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={config}
        >
          <Form.Item
            label="启用自动 Review"
            name="enabled"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            label="MR 创建者"
            name="creators"
            tooltip="只自动处理这些用户创建的 MR"
            rules={[{ required: true, message: '请选择至少一个用户' }]}
          >
            <Select
              mode="multiple"
              placeholder="选择用户"
              loading={loadingUsers}
              options={availableUsers.map(user => ({ label: user, value: user }))}
              showSearch
            />
          </Form.Item>

          <Form.Item
            label="检查间隔（秒）"
            name="interval"
            tooltip="每隔多少秒检查一次新的 MR"
          >
            <InputNumber min={5} max={300} style={{ width: '100%' }} />
          </Form.Item>

          <Divider />

          <div style={{ fontSize: 12, color: '#999' }}>
            <p>启用后会自动执行以下操作：</p>
            <ol style={{ paddingLeft: 20, margin: '8px 0' }}>
              <li>每隔指定时间获取与我相关的 MR</li>
              <li>筛选指定创建者的 MR</li>
              <li>如果是新建的 MR，调用 AI 总结接口</li>
              <li>将 AI 总结作为评论回复到 MR</li>
              <li>自动批准该 MR</li>
            </ol>
          </div>
        </Form>
      </AntModal>
    )
  }
)
