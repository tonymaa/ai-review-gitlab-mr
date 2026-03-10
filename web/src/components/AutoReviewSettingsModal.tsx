/**
 * 自动 Review 设置弹窗组件 - 使用后端API
 */

import { useState, useImperativeHandle, forwardRef } from 'react'
import { Modal as AntModal, Form, Switch, Select, InputNumber, Divider, message, Space, Tag, Button } from 'antd'
import { HistoryOutlined } from '@ant-design/icons'
import { api, type AutoReviewConfig } from '../api/client'
import ProcessedMRHistoryModal from './ProcessedMRHistoryModal'

// ==================== 类型定义 ====================

export interface AutoReviewSettingsModalRef {
  open: () => void
}

// 默认配置
export const getDefaultAutoReviewConfig = (): AutoReviewConfig => ({
  enabled: false,
  target_creators: [],
  interval_seconds: 120,
  target_projects: [],
  auto_approve_keywords: [],
  auto_approve_mode: 'always',
  add_as_comment: true,
})

// ==================== 组件 ====================

interface AutoReviewSettingsModalProps {
  onConfigChange?: (config: AutoReviewConfig) => void
}

export const AutoReviewSettingsModal = forwardRef<AutoReviewSettingsModalRef, AutoReviewSettingsModalProps>(
  ({ onConfigChange }, ref) => {
    const [open, setOpen] = useState(false)
    const [historyModalOpen, setHistoryModalOpen] = useState(false)
    const [config, setConfig] = useState<AutoReviewConfig>(getDefaultAutoReviewConfig())
    const [availableUsers, setAvailableUsers] = useState<string[]>([])
    const [loadingUsers, setLoadingUsers] = useState(false)
    const [loading, setLoading] = useState(false)
    const [form] = Form.useForm()

    // 暴露 open 方法给父组件
    useImperativeHandle(ref, () => ({
      open: () => {
        setOpen(true)
        loadConfig()
        loadAvailableUsers()
      },
    }))

    // 从后端加载配置
    const loadConfig = async () => {
      setLoading(true)
      try {
        const data = await api.getAutoReviewConfig()
        setConfig(data)
        form.setFieldsValue(data)
      } catch (err: any) {
        console.error('加载自动审查配置失败:', err)
        message.error(err.response?.data?.detail || '加载配置失败')
      } finally {
        setLoading(false)
      }
    }

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

    const handleOk = async () => {
      try {
        const values = await form.validateFields()

        // 验证：如果启用但没有配置创建者，提示错误
        if (values.enabled && (!values.target_creators || values.target_creators.length === 0)) {
          message.warning('请至少添加一个 MR 创建者')
          return
        }

        setLoading(true)
        await api.updateAutoReviewConfig(values)

        const newConfig = values as AutoReviewConfig
        setConfig(newConfig)
        onConfigChange?.(newConfig)
        setOpen(false)
        message.success('配置已保存')
      } catch (err: any) {
        console.error('保存配置失败:', err)
        // 表单验证错误不显示消息
        if (!err.errorFields) {
          message.error(err.response?.data?.detail || '保存失败')
        }
      } finally {
        setLoading(false)
      }
    }

    const handleCancel = () => {
      // 取消时恢复表单为当前配置
      form.setFieldsValue(config)
      setOpen(false)
    }

    // 监听配置变化，自动重启任务
    const handleEnabledChange = (checked: boolean) => {
      if (checked && (!config.target_creators || config.target_creators.length === 0)) {
        // 不在这里提示，让表单验证处理
      }
    }

    return (
      <>
        <AntModal
          title={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginRight: '30px' }}>
              <span>自动 Review 并批准设置</span>
              <Button
                type="link"
                size="small"
                icon={<HistoryOutlined />}
                onClick={() => setHistoryModalOpen(true)}
              >
                历史记录
              </Button>
            </div>
          }
          open={open}
          onCancel={handleCancel}
          onOk={handleOk}
          okText="保存"
          cancelText="取消"
          width={550}
          confirmLoading={loading}
          maskClosable={false}
        >
        <Form
          form={form}
          layout="vertical"
          initialValues={config}
        >
          {/* 状态显示 */}
          {(config.is_running || config.last_run_at || config.next_run_at) && (
            <div style={{ marginBottom: 16, padding: 12, background: '#5f5f5f', borderRadius: 4 }}>
              <Space size={4} style={{ width: '100%' }} vertical>
                {config.is_running && <Tag color="green">运行中</Tag>}
                {config.last_run_at && (
                  <div style={{ fontSize: 12, color: '#cecece' }}>
                    上次运行: {new Date(config.last_run_at).toLocaleString('zh-CN')}
                  </div>
                )}
                {config.next_run_at && (
                  <div style={{ fontSize: 12, color: '#cecece' }}>
                    下次运行: {new Date(config.next_run_at).toLocaleString('zh-CN')}
                  </div>
                )}
              </Space>
            </div>
          )}

          <Form.Item
            label="启用自动 Review"
            name="enabled"
            valuePropName="checked"
          >
            <Switch onChange={handleEnabledChange} />
          </Form.Item>

          <Form.Item
            label="MR 创建者"
            name="target_creators"
            tooltip="只自动处理这些用户创建的 MR"
            rules={[{ required: true, message: '请选择至少一个用户' }]}
          >
            <Select
              mode="multiple"
              placeholder="选择用户"
              loading={loadingUsers}
              options={availableUsers.map(user => ({ label: user, value: user }))}
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>

          <Form.Item
            label="目标项目"
            name="target_projects"
            tooltip="留空则处理所有项目，可输入项目ID进行筛选"
          >
            <Select
              mode="tags"
              placeholder="输入项目ID后回车添加"
              options={[]}
              open={false}
            />
          </Form.Item>

          <Form.Item
            label="检查间隔（秒）"
            name="interval_seconds"
            tooltip="每隔多少秒检查一次新的 MR"
            rules={[{ type: 'number', min: 10, max: 3600, message: '间隔必须在 10-3600 秒之间' }]}
          >
            <InputNumber min={10} max={3600} style={{ width: '100%' }} />
          </Form.Item>

          <Divider orientation="left" plain>自动批准设置</Divider>

          <Form.Item
            label="自动批准模式"
            name="auto_approve_mode"
            tooltip="选择何时自动批准 MR"
          >
            <Select
              options={[
                { label: '始终批准', value: 'always' },
                { label: '仅当总结包含关键词时批准', value: 'keyword_only' },
                { label: '从不自动批准', value: 'never' },
              ]}
            />
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) =>
              prevValues.auto_approve_mode !== currentValues.auto_approve_mode
            }
          >
            {({ getFieldValue }) =>
              getFieldValue('auto_approve_mode') === 'keyword_only' ? (
                <Form.Item
                  label="批准关键词"
                  name="auto_approve_keywords"
                  tooltip="AI 总结中包含这些关键词时才自动批准"
                >
                  <Select
                    mode="tags"
                    placeholder="输入关键词后回车添加"
                    options={[]}
                    open={false}
                  />
                </Form.Item>
              ) : null
            }
          </Form.Item>

          <Divider orientation="left" plain>审查设置</Divider>

          <Form.Item
            label="添加为评论"
            name="add_as_comment"
            valuePropName="checked"
            tooltip="将 AI 总结作为评论添加到 MR"
          >
            <Switch />
          </Form.Item>

          <Divider />

          <div style={{ fontSize: 12, color: '#999' }}>
            <p>启用后会自动执行以下操作：</p>
            <ol style={{ paddingLeft: 20, margin: '8px 0' }}>
              <li>每隔指定时间获取与我相关的 MR</li>
              <li>筛选指定创建者（和项目）的 MR</li>
              <li>对新的 MR 调用 AI 总结接口</li>
              <li>将 AI 总结作为评论回复到 MR</li>
              <li>根据批准模式配置自动批准</li>
            </ol>
            <p style={{ marginTop: 8, color: '#faad14' }}>
              注意：自动审查在服务器后端运行，无需保持此页面打开。
            </p>
          </div>
        </Form>
      </AntModal>

      <ProcessedMRHistoryModal
        open={historyModalOpen}
        onClose={() => setHistoryModalOpen(false)}
      />
    </>
  )
}
)
