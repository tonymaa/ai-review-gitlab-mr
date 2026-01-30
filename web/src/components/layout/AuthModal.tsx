/**
 * 登录/注册模态框组件
 */

import { type FC, useState, useMemo } from 'react'
import { Modal, Form, Input, Button, Tabs, message } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useApp } from '../../contexts/AppContext'



interface AuthModalProps {
  open: boolean
  onClose: () => void
}

const AuthModal: FC<AuthModalProps> = ({ open, onClose }) => {
  const { login, register, allowRegistration } = useApp()
  const [loading, setLoading] = useState(false)
  const [loginForm] = Form.useForm()
  const [registerForm] = Form.useForm()

  const handleLogin = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.username, values.password)
      message.success('登录成功')
      loginForm.resetFields()
      onClose()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (values: { username: string; password: string; confirmPassword: string }) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致')
      return
    }

    setLoading(true)
    try {
      await register(values.username, values.password)
      message.success('注册成功')
      registerForm.resetFields()
      onClose()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '注册失败')
    } finally {
      setLoading(false)
    }
  }

  // 根据配置动态生成 Tab 项
  const tabItems = useMemo(() => {
    const items = [
      {
        key: 'login',
        label: '登录',
        children: (
          <Form
            form={loginForm}
            onFinish={handleLogin}
            autoComplete="off"
            style={{ marginTop: 24 }}
          >
            <Form.Item
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input
                prefix={<UserOutlined />}
                placeholder="用户名"
                size="large"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="密码"
                size="large"
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
              >
                登录
              </Button>
            </Form.Item>
          </Form>
        ),
      },
    ]

    // 只有允许注册时才显示注册选项卡
    if (allowRegistration) {
      items.push({
        key: 'register',
        label: '注册',
        children: (
          <Form
            form={registerForm}
            onFinish={handleRegister}
            autoComplete="off"
            style={{ marginTop: 24 }}
          >
            <Form.Item
              name="username"
              rules={[
                { required: true, message: '请输入用户名' },
                { min: 3, message: '用户名至少3个字符' },
                { max: 50, message: '用户名最多50个字符' },
              ]}
            >
              <Input
                prefix={<UserOutlined />}
                placeholder="用户名"
                size="large"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6个字符' },
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="密码"
                size="large"
              />
            </Form.Item>

            <Form.Item
              name="confirmPassword"
              dependencies={['password']}
              rules={[
                { required: true, message: '请确认密码' },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue('password') === value) {
                      return Promise.resolve()
                    }
                    return Promise.reject(new Error('两次输入的密码不一致'))
                  },
                }),
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="确认密码"
                size="large"
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                size="large"
              >
                注册
              </Button>
            </Form.Item>
          </Form>
        ),
      })
    }

    return items
  }, [allowRegistration, loading, handleLogin, handleRegister])

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      title={null}
      width={400}
      centered
      maskClosable={false}
      closable={false}
      keyboard={false}
    >
      <Tabs
        defaultActiveKey="login"
        centered
        items={tabItems}
      />
    </Modal>
  )
}

export default AuthModal
