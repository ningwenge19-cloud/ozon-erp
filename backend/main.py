
import os
import json
import sqlite3
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ozon_erp.db"
FRONTEND_DIR = ROOT.parent / "frontend"

APP_NAME = "Ozon SaaS ERP"
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-in-railway")
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_BASE_URL = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "")
DOUBAO_IMAGE_MODEL = os.getenv("DOUBAO_IMAGE_MODEL", "doubao-seedream-3-0-t2i-250415")
OZON_CLIENT_ID = os.getenv("OZON_CLIENT_ID", "")
OZON_API_KEY = os.getenv("OZON_API_KEY", "")

app = FastAPI(title=APP_NAME, version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def hash_password(password: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return salt, digest

def verify_password(password: str, salt: str, digest: str):
    _, candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, digest)

def b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def sign_token(payload: dict):
    header = {"alg": "HS256", "typ": "JWT"}
    payload = dict(payload)
    payload["exp"] = int((datetime.utcnow() + timedelta(days=7)).timestamp())
    signing_input = b64url(json.dumps(header, separators=(",", ":")).encode()) + "." + b64url(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + b64url(signature)

def decode_token(token: str):
    import base64
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = header_b64 + "." + payload_b64
        expected = b64url(hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, sig_b64):
            raise ValueError("bad signature")
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if payload.get("exp", 0) < int(datetime.utcnow().timestamp()):
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")

def init_db():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ai_settings(
        id INTEGER PRIMARY KEY CHECK(id=1),
        api_key TEXT,
        base_url TEXT,
        model TEXT,
        image_model TEXT,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS ozon_settings(
        user_id INTEGER PRIMARY KEY,
        client_id TEXT,
        api_key TEXT,
        sync_type TEXT DEFAULT 'FBS / rFBS订单',
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        month TEXT,
        order_no TEXT,
        status TEXT,
        product TEXT,
        sku TEXT,
        quantity INTEGER DEFAULT 1,
        price_rub REAL DEFAULT 0,
        cost_cny REAL DEFAULT 0,
        shipping_cny REAL DEFAULT 0,
        commission_rate REAL DEFAULT 0.15,
        profit_cny REAL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        category TEXT,
        cost_cny REAL DEFAULT 0,
        weight_kg REAL DEFAULT 0,
        price_rub REAL DEFAULT 0,
        stock INTEGER DEFAULT 0,
        status TEXT DEFAULT 'draft',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tickets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        customer TEXT,
        message TEXT,
        status TEXT DEFAULT 'open',
        ai_reply TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audit_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        detail TEXT,
        created_at TEXT NOT NULL
    );
    """)
    # default admin only if no users
    row = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()
    if row["n"] == 0:
        salt, digest = hash_password("admin123456")
        c.execute(
            "INSERT INTO users(username,email,password_salt,password_hash,role,status,created_at) VALUES(?,?,?,?,?,?,?)",
            ("admin", "admin@example.com", salt, digest, "admin", "active", now_iso())
        )
    if not c.execute("SELECT id FROM ai_settings WHERE id=1").fetchone():
        c.execute(
            "INSERT INTO ai_settings(id,api_key,base_url,model,image_model,updated_at) VALUES(1,?,?,?,?,?)",
            (DOUBAO_API_KEY, DOUBAO_BASE_URL, DOUBAO_MODEL, DOUBAO_IMAGE_MODEL, now_iso())
        )
    c.commit()
    c.close()

init_db()

class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: str
    password: str = Field(min_length=6)

class LoginIn(BaseModel):
    account: str
    password: str

class AISettingsIn(BaseModel):
    api_key: str = ""
    base_url: str = DOUBAO_BASE_URL
    model: str = ""
    image_model: str = DOUBAO_IMAGE_MODEL

class ChatIn(BaseModel):
    message: str
    system: str = "你是Ozon跨境电商ERP助手，请用中文回答，给出可执行步骤。"

class ProductIn(BaseModel):
    title: str
    category: str = ""
    cost_cny: float = 0
    weight_kg: float = 0
    price_rub: float = 0
    stock: int = 0
    status: str = "draft"

class OrderIn(BaseModel):
    month: str = ""
    order_no: str
    status: str = ""
    product: str = ""
    sku: str = ""
    quantity: int = 1
    price_rub: float = 0
    cost_cny: float = 0
    shipping_cny: float = 0
    commission_rate: float = 0.15

class OzonSettingsIn(BaseModel):
    client_id: str = ""
    api_key: str = ""
    sync_type: str = "FBS / rFBS订单"

def current_user(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    payload = decode_token(authorization.split(" ", 1)[1])
    c = conn()
    user = c.execute("SELECT id,username,email,role,status,created_at FROM users WHERE id=?", (payload["uid"],)).fetchone()
    c.close()
    if not user or user["status"] != "active":
        raise HTTPException(status_code=403, detail="账号不可用")
    return dict(user)

def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user

def log_action(user_id: Optional[int], action: str, detail: str = ""):
    c = conn()
    c.execute("INSERT INTO audit_logs(user_id,action,detail,created_at) VALUES(?,?,?,?)", (user_id, action, detail, now_iso()))
    c.commit()
    c.close()

@app.post("/api/auth/register")
def register(data: RegisterIn):
    c = conn()
    if c.execute("SELECT id FROM users WHERE username=? OR email=?", (data.username, data.email)).fetchone():
        c.close()
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")
    salt, digest = hash_password(data.password)
    c.execute(
        "INSERT INTO users(username,email,password_salt,password_hash,role,status,created_at) VALUES(?,?,?,?,?,?,?)",
        (data.username, data.email, salt, digest, "user", "active", now_iso())
    )
    uid = c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    c.commit()
    c.close()
    token = sign_token({"uid": uid, "role": "user"})
    return {"token": token, "user": {"id": uid, "username": data.username, "email": data.email, "role": "user"}}

@app.post("/api/auth/login")
def login(data: LoginIn):
    c = conn()
    user = c.execute("SELECT * FROM users WHERE username=? OR email=?", (data.account, data.account)).fetchone()
    c.close()
    if not user or not verify_password(data.password, user["password_salt"], user["password_hash"]):
        raise HTTPException(status_code=400, detail="账号或密码错误")
    if user["status"] != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")
    token = sign_token({"uid": user["id"], "role": user["role"]})
    return {"token": token, "user": {"id": user["id"], "username": user["username"], "email": user["email"], "role": user["role"]}}

@app.get("/api/me")
def me(user=Depends(current_user)):
    return user

@app.get("/api/health")
def health():
    return {"ok": True, "app": APP_NAME, "time": now_iso()}

@app.get("/api/dashboard")
def dashboard(user=Depends(current_user)):
    c = conn()
    uid = user["id"]
    order_stats = c.execute("SELECT COUNT(*) n, COALESCE(SUM(price_rub),0) sales, COALESCE(SUM(profit_cny),0) profit FROM orders WHERE user_id=?", (uid,)).fetchone()
    product_count = c.execute("SELECT COUNT(*) n FROM products WHERE user_id=?", (uid,)).fetchone()["n"]
    ticket_count = c.execute("SELECT COUNT(*) n FROM tickets WHERE user_id=? AND status='open'", (uid,)).fetchone()["n"]
    recent = [dict(x) for x in c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 8", (uid,)).fetchall()]
    c.close()
    return {
        "orders": order_stats["n"],
        "sales_rub": round(order_stats["sales"], 2),
        "profit_cny": round(order_stats["profit"], 2),
        "products": product_count,
        "open_tickets": ticket_count,
        "recent_orders": recent
    }

@app.get("/api/admin/overview")
def admin_overview(admin=Depends(require_admin)):
    c = conn()
    users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
    orders = c.execute("SELECT COUNT(*) n FROM orders").fetchone()["n"]
    products = c.execute("SELECT COUNT(*) n FROM products").fetchone()["n"]
    logs = [dict(x) for x in c.execute("""
        SELECT audit_logs.*, users.username FROM audit_logs 
        LEFT JOIN users ON users.id=audit_logs.user_id
        ORDER BY audit_logs.id DESC LIMIT 20
    """).fetchall()]
    c.close()
    return {"users": users, "orders": orders, "products": products, "logs": logs}

@app.get("/api/admin/users")
def admin_users(admin=Depends(require_admin)):
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT id,username,email,role,status,created_at FROM users ORDER BY id DESC").fetchall()]
    c.close()
    return rows

@app.post("/api/admin/users/{uid}/role")
def admin_set_role(uid: int, payload: Dict[str, str], admin=Depends(require_admin)):
    role = payload.get("role")
    if role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="role 只能是 admin 或 user")
    c = conn()
    c.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
    c.commit()
    c.close()
    log_action(admin["id"], "set_role", f"user={uid}, role={role}")
    return {"ok": True}

@app.post("/api/admin/users/{uid}/status")
def admin_set_status(uid: int, payload: Dict[str, str], admin=Depends(require_admin)):
    status = payload.get("status")
    if status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="status 只能是 active 或 disabled")
    c = conn()
    c.execute("UPDATE users SET status=? WHERE id=?", (status, uid))
    c.commit()
    c.close()
    log_action(admin["id"], "set_status", f"user={uid}, status={status}")
    return {"ok": True}

@app.get("/api/ai/settings")
def get_ai_settings(user=Depends(current_user)):
    c = conn()
    row = c.execute("SELECT api_key,base_url,model,image_model FROM ai_settings WHERE id=1").fetchone()
    c.close()
    api_key = (row["api_key"] if row else "") or DOUBAO_API_KEY
    return {
        "api_key_set": bool(api_key),
        "base_url": (row["base_url"] if row else "") or DOUBAO_BASE_URL,
        "model": (row["model"] if row else "") or DOUBAO_MODEL,
        "image_model": (row["image_model"] if row else "") or DOUBAO_IMAGE_MODEL
    }

@app.post("/api/ai/settings")
def save_ai_settings(data: AISettingsIn, admin=Depends(require_admin)):
    c = conn()
    c.execute("""
        INSERT INTO ai_settings(id,api_key,base_url,model,image_model,updated_at)
        VALUES(1,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
        api_key=excluded.api_key,
        base_url=excluded.base_url,
        model=excluded.model,
        image_model=excluded.image_model,
        updated_at=excluded.updated_at
    """, (data.api_key, data.base_url, data.model, data.image_model, now_iso()))
    c.commit()
    c.close()
    log_action(admin["id"], "save_ai_settings", "updated doubao settings")
    return {"ok": True}

@app.get("/api/doubao/settings")
def public_doubao_settings():
    c = conn()
    row = c.execute("SELECT api_key,base_url,model,image_model FROM ai_settings WHERE id=1").fetchone()
    c.close()
    api_key = (row["api_key"] if row else "") or DOUBAO_API_KEY
    return {
        "api_key_set": bool(api_key),
        "base_url": (row["base_url"] if row else "") or DOUBAO_BASE_URL,
        "model": (row["model"] if row else "") or DOUBAO_MODEL,
        "image_model": (row["image_model"] if row else "") or DOUBAO_IMAGE_MODEL
    }

def get_ai_config():
    c = conn()
    row = c.execute("SELECT api_key,base_url,model,image_model FROM ai_settings WHERE id=1").fetchone()
    c.close()
    return {
        "api_key": (row["api_key"] if row else "") or DOUBAO_API_KEY,
        "base_url": (row["base_url"] if row else "") or DOUBAO_BASE_URL,
        "model": (row["model"] if row else "") or DOUBAO_MODEL,
        "image_model": (row["image_model"] if row else "") or DOUBAO_IMAGE_MODEL,
    }

def call_doubao_text(prompt: str, system: str = "") -> str:
    cfg = get_ai_config()
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="未配置豆包 API Key，请管理员在 AI 设置中配置。")
    if not cfg["model"]:
        raise HTTPException(status_code=400, detail="未配置豆包文字模型 endpoint。")

    # Responses API format shown in Volcengine Ark console
    url = cfg["base_url"].rstrip("/") + "/responses"
    headers = {
        "Authorization": "Bearer " + cfg["api_key"],
        "Content-Type": "application/json"
    }
    text = (system + "\n\n" if system else "") + prompt
    payload = {
        "model": cfg["model"],
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": text}
                ]
            }
        ]
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()

    if data.get("output_text"):
        return data["output_text"]

    try:
        return data["output"][0]["content"][0]["text"]
    except Exception:
        return json.dumps(data, ensure_ascii=False, indent=2)

@app.post("/api/doubao/chat")
def doubao_chat(data: ChatIn, user=Depends(current_user)):
    answer = call_doubao_text(data.message, data.system)
    log_action(user["id"], "doubao_chat", data.message[:100])
    return {"answer": answer}

@app.post("/api/ai/listing")
def ai_listing(payload: Dict[str, Any], user=Depends(current_user)):
    prompt = f"""
请为 Ozon 平台生成商品 Listing：
商品名：{payload.get('product_name','')}
类目：{payload.get('category','')}
关键词/卖点：{payload.get('keywords') or payload.get('selling_points','')}
价格：{payload.get('price_rub','')} 卢布

要求：
1. 输出俄语标题
2. 输出俄语五点卖点
3. 输出中文运营建议
4. 标题适合 Ozon 搜索
"""
    return {"listing": call_doubao_text(prompt, "你是Ozon商品运营专家。")}

@app.post("/api/ai/title")
def ai_title(payload: Dict[str, Any], user=Depends(current_user)):
    prompt = f"请为Ozon生成一个俄语商品标题。商品：{payload.get('product_name','')}，类目：{payload.get('category','')}，关键词：{payload.get('keywords','')}"
    return {"title": call_doubao_text(prompt, "你是Ozon俄语标题优化专家。")}

@app.get("/api/products")
def list_products(user=Depends(current_user)):
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM products WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()]
    c.close()
    return rows

@app.post("/api/products")
def create_product(data: ProductIn, user=Depends(current_user)):
    c = conn()
    c.execute("""
        INSERT INTO products(user_id,title,category,cost_cny,weight_kg,price_rub,stock,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)
    """, (user["id"], data.title, data.category, data.cost_cny, data.weight_kg, data.price_rub, data.stock, data.status, now_iso()))
    c.commit()
    c.close()
    return {"ok": True}

@app.delete("/api/products/{pid}")
def delete_product(pid: int, user=Depends(current_user)):
    c = conn()
    c.execute("DELETE FROM products WHERE id=? AND user_id=?", (pid, user["id"]))
    c.commit()
    c.close()
    return {"ok": True}

@app.get("/api/orders")
def list_orders(user=Depends(current_user)):
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 300", (user["id"],)).fetchall()]
    c.close()
    return rows

@app.post("/api/orders")
def create_order(data: OrderIn, user=Depends(current_user)):
    profit = data.price_rub * 0.078 - data.cost_cny - data.shipping_cny - data.price_rub * 0.078 * data.commission_rate
    c = conn()
    c.execute("""
        INSERT INTO orders(user_id,month,order_no,status,product,sku,quantity,price_rub,cost_cny,shipping_cny,commission_rate,profit_cny,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (user["id"], data.month, data.order_no, data.status, data.product, data.sku, data.quantity, data.price_rub, data.cost_cny, data.shipping_cny, data.commission_rate, round(profit,2), now_iso()))
    c.commit()
    c.close()
    return {"ok": True, "profit_cny": round(profit, 2)}

@app.post("/api/ozon/settings")
def save_ozon_settings(data: OzonSettingsIn, user=Depends(current_user)):
    c = conn()
    c.execute("""
        INSERT INTO ozon_settings(user_id,client_id,api_key,sync_type,updated_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET client_id=excluded.client_id,api_key=excluded.api_key,sync_type=excluded.sync_type,updated_at=excluded.updated_at
    """, (user["id"], data.client_id, data.api_key, data.sync_type, now_iso()))
    c.commit()
    c.close()
    return {"ok": True}

@app.get("/api/ozon/settings")
def get_ozon_settings(user=Depends(current_user)):
    c = conn()
    row = c.execute("SELECT client_id,api_key,sync_type FROM ozon_settings WHERE user_id=?", (user["id"],)).fetchone()
    c.close()
    if not row:
        return {"client_id": "", "api_key_set": False, "sync_type": "FBS / rFBS订单"}
    return {"client_id": row["client_id"], "api_key_set": bool(row["api_key"]), "sync_type": row["sync_type"]}

@app.post("/api/ozon/sync-demo")
def ozon_sync_demo(user=Depends(current_user)):
    # Safe demo import, no real Ozon API dependency.
    samples = [
        {"month":"2026-05","order_no":"DEMO-1001","status":"delivering","product":"Палатка туристическая 4 места","sku":"TENT-4P","quantity":1,"price_rub":1542,"cost_cny":58,"shipping_cny":42,"commission_rate":0.15},
        {"month":"2026-05","order_no":"DEMO-1002","status":"awaiting_deliver","product":"Багажный бокс 600 л","sku":"BOX-600","quantity":1,"price_rub":1677,"cost_cny":72,"shipping_cny":55,"commission_rate":0.15},
        {"month":"2026-05","order_no":"DEMO-1003","status":"cancelled","product":"Плащ дождевик туристический","sku":"RAIN-01","quantity":2,"price_rub":498,"cost_cny":18,"shipping_cny":16,"commission_rate":0.15},
    ]
    c = conn()
    for x in samples:
        profit = x["price_rub"]*0.078 - x["cost_cny"] - x["shipping_cny"] - x["price_rub"]*0.078*x["commission_rate"]
        c.execute("""
            INSERT INTO orders(user_id,month,order_no,status,product,sku,quantity,price_rub,cost_cny,shipping_cny,commission_rate,profit_cny,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (user["id"], x["month"], x["order_no"], x["status"], x["product"], x["sku"], x["quantity"], x["price_rub"], x["cost_cny"], x["shipping_cny"], x["commission_rate"], round(profit,2), now_iso()))
    c.commit()
    c.close()
    return {"ok": True, "imported": len(samples)}

@app.get("/api/tickets")
def list_tickets(user=Depends(current_user)):
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM tickets WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()]
    c.close()
    return rows

@app.post("/api/tickets")
def create_ticket(payload: Dict[str, str], user=Depends(current_user)):
    c = conn()
    c.execute("INSERT INTO tickets(user_id,customer,message,status,created_at) VALUES(?,?,?,?,?)", (user["id"], payload.get("customer","客户"), payload.get("message",""), "open", now_iso()))
    c.commit()
    c.close()
    return {"ok": True}

@app.post("/api/tickets/{tid}/ai-reply")
def ticket_ai_reply(tid: int, user=Depends(current_user)):
    c = conn()
    row = c.execute("SELECT * FROM tickets WHERE id=? AND user_id=?", (tid, user["id"])).fetchone()
    if not row:
        c.close()
        raise HTTPException(status_code=404, detail="消息不存在")
    prompt = f"请帮我用中文生成一段适合跨境电商客服的回复，客户消息：{row['message']}"
    reply = call_doubao_text(prompt, "你是跨境电商客服专家，回复要礼貌、简洁、可执行。")
    c.execute("UPDATE tickets SET ai_reply=? WHERE id=?", (reply, tid))
    c.commit()
    c.close()
    return {"reply": reply}

# Mount frontend last
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
