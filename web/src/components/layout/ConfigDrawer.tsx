/**
 * 配置抽屉组件
 */

import { type FC, useState, useEffect } from 'react'
import { Drawer, Form, Input, Select, Button, Space, Typography, Divider, message, Spin } from 'antd'
import { api } from '../../api/client'

const { Title } = Typography
const { Option } = Select

interface ConfigDrawerProps {
  open: boolean
  onClose: () => void
}

const ConfigDrawer: FC<ConfigDrawerProps> = ({ open, onClose }) => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

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
      if (!config.gitlab || !config.ai) {
        console.warn('Config not fully loaded:', config)
      }

      form.setFieldsValue({
        // GitLab
        gitlab_url: config.gitlab?.url || '',
        gitlab_token: config.gitlab?.token || '',
        gitlab_default_project_id: config.gitlab?.default_project_id || '',

        // AI
        ai_provider: config.ai?.provider || 'openai',
        openai_api_key: config.ai?.openai?.api_key || '',
        openai_base_url: config.ai?.openai?.base_url || '',
        openai_model: config.ai?.openai?.model || 'gpt-4',
        openai_temperature: config.ai?.openai?.temperature ?? 0.3,
        openai_max_tokens: config.ai?.openai?.max_tokens ?? 2000,
        ollama_base_url: config.ai?.ollama?.base_url || 'http://localhost:11434',
        ollama_model: config.ai?.ollama?.model || 'codellama',
        review_rules: config.ai?.review_rules?.join('\n') || '',
        summary_prompt: config.ai?.summary_prompt || '',
      })
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
          provider: values.ai_provider,
          openai: {
            api_key: values.openai_api_key,
            base_url: values.openai_base_url || undefined,
            model: values.openai_model,
            temperature: values.openai_temperature,
            max_tokens: values.openai_max_tokens,
          },
          ollama: {
            base_url: values.ollama_base_url,
            model: values.ollama_model,
          },
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

  return (
    <Drawer
      title="配置"
      placement="right"
      width={500}
      open={open}
      onClose={onClose}
      footer={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
            保存
          </Button>
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
          <Form.Item
            label="服务器 URL"
            name="gitlab_url"
          >
            <Input placeholder="https://gitlab.com" />
          </Form.Item>

          <Form.Item
            label="访问令牌"
            name="gitlab_token"
          >
            <Input.Password />
          </Form.Item>


          <Divider />

          {/* AI 配置 */}
          <Title level={5}>AI 审查配置</Title>
          <Form.Item
            label="AI 提供商"
            name="ai_provider"
          >
            <Select>
              <Option value="openai">OpenAI</Option>
              <Option value="ollama">Ollama</Option>
            </Select>
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, curr) => prev.ai_provider !== curr.ai_provider}>
            {({ getFieldValue }) => {
              const provider = getFieldValue('ai_provider')
              return provider === 'openai' ? (
                <>
                  <Form.Item
                    label="API Key"
                    name="openai_api_key"
                  >
                    <Input.Password placeholder="sk-..." />
                  </Form.Item>

                  <Form.Item
                    label="Base URL (可选)"
                    name="openai_base_url"
                  >
                    <Input placeholder="自定义 API 端点" />
                  </Form.Item>

                  <Form.Item
                    label="模型"
                    name="openai_model"
                  >
                    <Input placeholder="gpt-4" />
                  </Form.Item>

                  <Form.Item
                    label="温度"
                    name="openai_temperature"
                  >
                    <Input type="number" step={0.1} min={0} max={2} />
                  </Form.Item>

                  <Form.Item
                    label="最大 Tokens"
                    name="openai_max_tokens"
                  >
                    <Input type="number" />
                  </Form.Item>
                </>
              ) : provider === 'ollama' ? (
                <>
                  <Form.Item
                    label="Base URL"
                    name="ollama_base_url"
                  >
                    <Input placeholder="http://localhost:11434" />
                  </Form.Item>

                  <Form.Item
                    label="模型"
                    name="ollama_model"
                  >
                    <Input placeholder="codellama" />
                  </Form.Item>
                </>
              ) : null
            }}
          </Form.Item>

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
              placeholder="请总结以下 Merge Request 的改动：\n\n标题: {mr_title}\n分支: {source_branch} → {target_branch}\n\n{diff_content}\n\n请用中文总结主要变更点："
            />
          </Form.Item>
        </Form>
      </Spin>
    </Drawer>
  )
}

export default ConfigDrawer
