# -*- coding: utf-8 -*-
"""
子任务3：大模型 API 接入与密钥管理（最小化调用）
密钥规范：API Key 只存于 .env（被 .gitignore 排除），运行时经环境变量读取，禁止硬编码。
用法：先把 .env.example 复制为 .env 并填入真实 Key，再运行本脚本。
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE, ".env"))

api_key = os.environ.get("ZHIPU_API_KEY")
if not api_key or "xxxx" in api_key:
    raise SystemExit("未配置 API Key：请复制 .env.example 为 .env 并填入真实 ZHIPU_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url=os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"),
)

resp = client.chat.completions.create(
    model=os.environ.get("ZHIPU_MODEL", "glm-4-flash"),
    messages=[
        {"role": "system", "content": "你是一个简洁的助手。"},
        {"role": "user", "content": "用一句话说明什么是 NL2SQL。"},
    ],
)
print("模型返回:", resp.choices[0].message.content)
print("token 用量:", resp.usage.total_tokens)
