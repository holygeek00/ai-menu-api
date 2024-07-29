import base64
import requests
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from datetime import datetime

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


class UserStatsRequest(BaseModel):
    user_id: str


def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')


async def call_openai_api(base64_image: str, target_language: str):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }

    # 调用OpenAI Vision API识别图片内容并翻译
    payload = {
        "model": "gpt-4o-mini-2024-07-18",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f''' 
                        You are a professional translator specializing in menu translations. Your task is to translate a given menu from its original language into the specified target language. Here's how to proceed:

                        First, I will provide you with the menu to be translated:

                        The target language for this translation is:

                        <target_language>
                        {target_language}
                        </target_language>

                        Please follow these guidelines when translating the menu:

                        1. Translate all text in the menu, including dish names, descriptions, and any additional information.
                        2. Preserve the original structure and formatting of the menu as much as possible.
                        3. If there are any culturally specific terms or dishes that don't have a direct translation, provide a brief explanation in parentheses after the translated term.
                        4. Keep any prices or numerical information unchanged.
                        5. If there are any special characters or symbols used in the original menu (e.g., for spicy dishes or vegetarian options), maintain them in the translation.
                        6. For dish names that are proper nouns or have a specific cultural significance, you may choose to keep them in the original language and provide a translation or explanation in parentheses.

                        Once you have completed the translation, please provide the translated menu in its entirety, maintaining the original structure and formatting as closely as possible.

                        If you encounter any terms or phrases that you're unsure about, please indicate this by placing [UNCERTAIN] after the translated term, and provide your best attempt at a translation.

                        Please begin your translation now.
                        '''
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

# 数据库初始化


def init_db():
    conn = sqlite3.connect('usage_stats.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


init_db()


def log_usage(user_id, action):
    conn = sqlite3.connect('usage_stats.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO usage_stats (user_id, action)
        VALUES (?, ?)
    ''', (user_id, action))
    conn.commit()
    conn.close()


@app.post("/upload/")
async def upload_image(file: UploadFile = File(...), target_language: str = Form(...), user_id: str = Form(...)):
    try:
        # 读取上传的图片文件
        image_bytes = await file.read()
        base64_image = encode_image(image_bytes)

        # 调用异步函数处理API请求
        translated_text = await call_openai_api(base64_image, target_language)

        # 记录用户行为
        log_usage(user_id, "upload_and_translate")

        return JSONResponse(content={
            "translated_text": translated_text
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/user/stats/")
async def get_user_stats(request: UserStatsRequest):
    try:
        conn = sqlite3.connect('usage_stats.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT action, COUNT(*), MIN(timestamp), MAX(timestamp)
            FROM usage_stats
            WHERE user_id = ?
            GROUP BY action
        ''', (request.user_id,))
        rows = cursor.fetchall()
        conn.close()

        stats = [{
            "action": row[0],
            "count": row[1],
            "first_use": row[2],
            "last_use": row[3]
        } for row in rows]

        return JSONResponse(content={
            "user_id": request.user_id,
            "stats": stats
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/stats/total")
async def get_total_stats():
    try:
        conn = sqlite3.connect('usage_stats.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT action, COUNT(*), MIN(timestamp), MAX(timestamp)
            FROM usage_stats
            GROUP BY action
        ''')
        rows = cursor.fetchall()
        conn.close()

        stats = [{
            "action": row[0],
            "count": row[1],
            "first_use": row[2],
            "last_use": row[3]
        } for row in rows]

        return JSONResponse(content={
            "total_stats": stats
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# 启动服务的命令（在命令行中运行）
# uvicorn main:app --reload
