/**
 * 配置抽屉组件 - 支持多 AI Provider 配置
 */

import { type FC, useState, useEffect } from 'react'
import { Drawer, Form, Input, Select, Button, Space, Typography, Divider, message, Spin, Modal, Card, List, Tag, Popconfirm } from 'antd'
import { api } from '../../api/client'
import type { AIProvider, AIConfig, GitLabConfig } from '../../types'

const { Title } = Typography
const { Option } = Select

interface ConfigDrawerProps {
  open: boolean
  onClose: () => void
}

interface ProviderFormData {
  name: string;
  provider_type: 'openai' | 'ollama';
  openai?: {
    api_key?: string;
    base_url?: string;
    model?: string;
    temperature?: number;
    max_tokens?: number;
  };
  ollama?: {
    base_url?: string;
    model?: string;
  };
}

const ConfigDrawer: FC<ConfigDrawerProps> = ({ open, onClose }) => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [providers, setProviders] = useState<AIProvider[]>([])
  const [activeProviderId, setActiveProviderId] = useState<number | null>(null)
  const [providerModalOpen, setProviderModalOpen] = useState(false)
  const [editingProvider, setEditingProvider] = useState<AIProvider | null>(null)
  const [providerForm] = Form.useForm()

  // 加载配置
  useEffect(() => {
    if (open) {
      loadConfig()
    }
  }, [open])

  const loadConfig = async () => {
    setLoading(true)
    try {
      const config = await api.getConfig()

      // 处理可能为空的情况
      if (!config.gitlab || !config.ai || !config.providers) {
        console.warn('Config not fully loaded:', config)
      }

      // 设置 GitLab 配置
      form.setFieldsValue({
        gitlab_url: config.gitlab?.url || '',
        gitlab_token: config.gitlab?.token || '',
        gitlab_default_project_id: config.gitlab?.default_project_id || '',
      })

      // 设置 AI 配置
      form.setFieldsValue({
        review_rules: config.ai?.review_rules?.join('\n') || '',
        summary_prompt: config.ai?.summary_prompt || '',
      })

      // 设置 Providers
      setProviders(config.providers?.providers || [])
      setActiveProviderId(config.providers?.active_provider_id || null)
    } catch (err) {
      console.error('Failed to load config:', err)
      message.error('加载配置失败')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)

      // 将审查规则从字符串转换为数组
      const rulesArray = values.review_rules
        ? values.review_rules.split('\n').filter((r: string) => r.trim())
        : []

      await api.updateConfig({
        gitlab: {
          url: values.gitlab_url,
          token: values.gitlab_token,
          default_project_id: values.gitlab_default_project_id || undefined,
        },
        ai: {
          active_provider_id: activeProviderId,
          review_rules: rulesArray,
          summary_prompt: values.summary_prompt ?? undefined,
        },
      })

      message.success('配置已保存')
      onClose()
    } catch (err) {
      console.error('Failed to save config:', err)
      message.error('保存配置失败')
    } finally {
      setSaving(false)
    }
  }

  // 编辑 Provider 时填充表单
  useEffect(() => {
    if (providerModalOpen && editingProvider) {
      // 填充基础字段
      const formValues: Record<string, unknown> = {
        name: editingProvider.name,
        provider_type: editingProvider.provider_type,
      }

      // 根据 provider 类型填充对应字段
      if (editingProvider.provider_type === 'openai' && editingProvider.openai) {
        formValues.openai_api_key = editingProvider.openai.api_key
        formValues.openai_base_url = editingProvider.openai.base_url
        formValues.openai_model = editingProvider.openai.model
        formValues.openai_temperature = editingProvider.openai.temperature
        formValues.openai_max_tokens = editingProvider.openai.max_tokens
      } else if (editingProvider.provider_type === 'ollama' && editingProvider.ollama) {
        formValues.ollama_base_url = editingProvider.ollama.base_url
        formValues.ollama_model = editingProvider.ollama.model
      }

      providerForm.setFieldsValue(formValues)
    } else if (!providerModalOpen) {
      // 关闭模态框时重置表单
      providerForm.resetFields()
    }
  }, [providerModalOpen, editingProvider, providerForm])

  // Provider 相关操作
  const handleAddProvider = () => {
    setEditingProvider(null)
    setProviderModalOpen(true)
  }

  const handleEditProvider = (provider: AIProvider) => {
    setEditingProvider(provider)
    setProviderModalOpen(true)
  }

  const handleDeleteProvider = async (provider: AIProvider) => {
    try {
      await api.deleteAIProvider(provider.id)
      message.success('Provider 已删除')
      loadConfig()
    } catch (err) {
      console.error('Failed to delete provider:', err)
      message.error('删除 Provider 失败')
    }
  }

  const handleActivateProvider = async (providerId: number) => {
    try {
      await api.activateAIProvider(providerId)
      message.success('Provider 已激活')
      loadConfig()
    } catch (err) {
      console.error('Failed to activate provider:', err)
      message.error('激活 Provider 失败')
    }
  }

  const handleProviderModalSave = async (values: ProviderFormData) => {
    try {
      const providerData = {
        name: values.name,
        provider_type: values.provider_type,
        openai: values.provider_type === 'openai' ? {
          api_key: values.openai_api_key || '',
          base_url: values.openai_base_url || undefined,
          model: values.openai_model || 'gpt-4',
          temperature: values.openai_temperature ?? 0.3,
          max_tokens: values.openai_max_tokens || 10000,
        } : undefined,
        ollama: values.provider_type === 'ollama' ? {
          base_url: values.ollama_base_url || 'http://localhost:11434',
          model: values.ollama_model || 'codellama',
        } : undefined,
      }

      if (editingProvider) {
        await api.updateAIProvider(editingProvider.id, providerData)
        message.success('Provider 已更新')
      } else {
        await api.createAIProvider(providerData)
        message.success('Provider 已创建')
      }

      setProviderModalOpen(false)
      setEditingProvider(null)
      loadConfig()
    } catch (err) {
      console.error('Failed to save provider:', err)
      message.error('保存 Provider 失败')
    }
  }

  const getProviderTypeLabel = (type: string) => {
    switch (type) {
      case 'openai':
        return 'OpenAI'
      case 'ollama':
        return 'Ollama'
      default:
        return type
    }
  }

  const renderProviderIcon = (type: string) => {
    switch (type) {
      case 'openai':
        return <Tag color="blue">OpenAI</Tag>
      case 'ollama':
        return <Tag color="green">Ollama</Tag>
      default:
        return null
    }
  }

  return (
    <Drawer
      title="配置"
      placement="right"
      width={600}
      open={open}
      onClose={onClose}
      footer={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
保存</Button>
        </Space>
      }
    >
      <Spin spinning={loading}>
        <Form
          form={form}
          layout="vertical"
          autoComplete="off"
        >
          {/* GitLab 配置 */}
          <Title level={5}>GitLab 配置</Title>
          <Form.Item label="服务器 URL" name="gitlab_url">
            <Input placeholder="https://gitlab.com" />
          </Form.Item>
          <Form.Item label="访问令牌" name="gitlab_token">
            <Input.Password />
          </Form.Item>

          <Divider />

          {/* AI Provider 配置 */}
          <Title level={5}>AI Provider 配置</Title>
          <div style={{ marginBottom: 16 }}>
            <Button type="dashed" onClick={handleAddProvider} style={{ width: '100%' }}>
              添加 Provider
            </Button>
          </div>

          <List
            dataSource={providers}
            renderItem={(provider) => (
              <List.Item
                key={provider.id}
                actions={[
                  <Button
                    type="link"
                    size="small"
                    onClick={() => handleEditProvider(provider)}
                  >
                    编辑
                  </Button>,
                  <Popconfirm
                    title="确定删除此 Provider?"
                    onConfirm={() => handleDeleteProvider(provider)}
                  >
                    <Button type="link" size="small" danger>
                      删除
                    </Button>
                  </Popconfirm>,
                ]}
                style={{
                  backgroundColor: activeProviderId === provider.id ? '#3e3e3e' : undefined,
                  borderLeft: activeProviderId === provider.id ? '2px solid #1890ff' : undefined,
                }}
              >
                <List.Item.Meta
                  avatar={renderProviderIcon(provider.provider_type)}
                  title={
                    <Space>
                      <span>{provider.name}</span>
                      {activeProviderId === provider.id && (
                        <Tag color="blue" style={{ marginLeft: 8 }}>当前激活</Tag>
                      )}
                    </Space>
                  }
                  description={`${getProviderTypeLabel(provider.provider_type)} - ${provider.provider_type === 'openai' ? provider.openai?.model : provider.ollama?.model}`}
                />
                <Button
                  type="primary"
                  size="small"
                  disabled={activeProviderId === provider.id}
                  onClick={() => handleActivateProvider(provider.id)}
                >
                  激活
                </Button>
              </List.Item>
            )}
          />

          <Divider />

          {/* 全局 AI 设置 */}
          <Title level={5}>审查规则</Title>
          <Form.Item
            label="审查规则"
            name="review_rules"
            tooltip="每行一条规则"
          >
            <Input.TextArea
              rows={6}
              placeholder="检查代码是否符合PEP8规范&#10;检查是否有潜在的安全漏洞"
            />
          </Form.Item>

          <Form.Item
            label="AI 总结提示词"
            name="summary_prompt"
            tooltip="支持变量: {mr_title}, {source_branch}, {target_branch}, {description}, {files_changed}, {diff_content}。留空使用默认提示词。"
          >
            <Input.TextArea
              rows={4}
              placeholder="请总结以下 Merge Request 的改动：&#10;&#10;标题: {mr_title}&#10;分支: {source_branch} → {target_branch}&#10;&#10;{diff_content}&#10;&#10;请用中文总结主要变更点："
            />
          </Form.Item>
        </Form>
      </Spin>

      {/* Provider 编辑模态框 */}
      <Modal
        title={editingProvider ? '编辑 Provider' : '添加 Provider'}
        open={providerModalOpen}
        onCancel={() => {
          setProviderModalOpen(false)
          setEditingProvider(null)
        }}
        onOk={() => providerForm.submit()}
      >
        <Form
          form={providerForm}
          layout="vertical"
          onFinish={handleProviderModalSave}
        >
          <Form.Item
            label="名称"
            name="name"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="例如: OpenAI GPT-4" />
          </Form.Item>

          <Form.Item
            label="类型"
            name="provider_type"
            rules={[{ required: true, message: '请选择类型' }]}
          >
            <Select onChange={(value) => {
              // 切换类型时只重置 provider 特定字段，保留 name 和 provider_type
              const fieldsToReset = value === 'openai'
                ? ['openai_api_key', 'openai_base_url', 'openai_model', 'openai_temperature', 'openai_max_tokens']
                : ['ollama_base_url', 'ollama_model']
              providerForm.resetFields(fieldsToReset)
            }}>
              <Option value="openai">OpenAI</Option>
              <Option value="ollama">Ollama</Option>
            </Select>
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, curr) => prev.provider_type !== curr.provider_type}>
            {({ getFieldValue }) => {
              const providerType = getFieldValue('provider_type')
              return providerType === 'openai' ? (
                <>
                  <Form.Item
                    label="API Key"
                    name="openai_api_key"
                    rules={[{ required: true, message: '请输入 API Key' }]}
                  >
                    <Input.Password placeholder="sk-..." />
                  </Form.Item>

                  <Form.Item label="Base URL (可选)" name="openai_base_url">
                    <Input placeholder="自定义 API 端点" />
                  </Form.Item>

                  <Form.Item
                    label="模型"
                    name="openai_model"
                    rules={[{ required: true, message: '请输入模型名称' }]}
                  >
                    <Input placeholder="gpt-4" />
                  </Form.Item>

                  <Form.Item label="温度" name="openai_temperature" initialValue={0.3}>
                    <Input type="number" step={0.1} min={0} max={2} />
                  </Form.Item>

                  <Form.Item label="最大 Tokens" name="openai_max_tokens" initialValue={10000}>
                    <Input type="number" />
                  </Form.Item>
                </>
              ) : providerType === 'ollama' ? (
                <>
                  <Form.Item
                    label="Base URL"
                    name="ollama_base_url"
                    rules={[{ required: true, message: '请输入 Base URL' }]}
                  >
                    <Input placeholder="http://localhost:11434" />
                  </Form.Item>

                  <Form.Item
                    label="模型"
                    name="ollama_model"
                    rules={[{ required: true, message: '请输入模型名称' }]}
                  >
                    <Input placeholder="codellama" />
                  </Form.Item>
                </>
              ) : null
            }}
          </Form.Item>
        </Form>
      </Modal>
    </Drawer>
  )
}

export default ConfigDrawer
