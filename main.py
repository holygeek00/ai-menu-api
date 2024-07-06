import base64
import requests
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import openai
import io
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import List

# 加载环境变量
load_dotenv()

# 获取API密钥
openai_api_key = os.getenv('OPENAI_API_KEY')
openai.api_key = openai_api_key

app = FastAPI()

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源。你可以根据需要更改此设置以限制来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
)


class TranslationRequest(BaseModel):
    target_language: str


def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')


async def call_openai_api(base64_image: str, target_language: str):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }

    # 调用OpenAI Vision API识别图片内容并翻译
    payload = {
        "model": "gpt-4o-2024-05-13",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"You are the master of menu translate, help me with the task below. The following is an image of a menu of your language and you are also expert of {target_language}, you also have background of food. Please extract all the text and just translate all of them to {target_language}."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 2000
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    response_json = response.json()
    translated_text = response_json['choices'][0]['message']['content'].strip()

    return translated_text


@app.post("/upload/")
async def upload_image(file: UploadFile = File(...), target_language: str = Form(...)):
    try:
        # 读取上传的图片文件
        image_bytes = await file.read()
        base64_image = encode_image(image_bytes)

        # 调用异步函数处理API请求
        translated_text = await call_openai_api(base64_image, target_language)

        return JSONResponse(content={
            "translated_text": translated_text
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# 启动服务的命令（在命令行中运行）
# uvicorn main:app --reload
