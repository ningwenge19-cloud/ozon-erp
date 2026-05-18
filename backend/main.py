
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import sqlite3, json, datetime, os, os, os
import hashlib, secrets, urllib.parse, base64, base64
import requests

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ozon_erp.db"
SEED_PATH = ROOT / "seed_data.json"
ASSETS_DIR = ROOT / "generated_assets"
ASSETS_DIR.mkdir(exist_ok=True)


class DoubaoSettingsIn(BaseModel):
    api_key: str
    base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    model: str = "doubao-seed-1-6-250615"
    image_model: str = "doubao-seedream-3-0-t2i-250415"

class DoubaoChatIn(BaseModel):
    message: str
    system: str = "你是Ozon跨境电商ERP助手，请用中文回答，必要时给出可执行步骤。"

app = FastAPI(title="Ozon ERP System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProductIn(BaseModel):
    sku: str | None = None
    month: str
    product_name: str
    purchase_cost_cny: float = 0
    weight_kg: float = 0
    domestic_shipping_cny: float = 0
    package_cost_cny: float = 0
    ad_cost_cny: float = 0
    ozon_price_rub: float = 0
    exchange_rate: float = 0.08
    fulfillment: str = "rFBS"

class RefundIn(BaseModel):
    month: str
    amount_cny: float = 0

class OzonSettingsIn(BaseModel):
    client_id: str
    api_key: str
    warehouse_id: str | None = None

class SyncOrdersIn(BaseModel):
    date_from: str
    date_to: str
    source: str = "fbs"
    limit: int = 100

class LoginIn(BaseModel):
    username: str
    password: str

class EmployeeIn(BaseModel):
    username: str
    password: str
    role: str = "staff"
    is_active: int = 1

class InventoryIn(BaseModel):
    sku: str
    product_name: str
    quantity: int = 0
    safety_stock: int = 0
    warehouse: str = "默认仓"

class PurchaseIn(BaseModel):
    sku: str
    product_name: str
    supplier: str = ""
    quantity: int = 0
    unit_cost_cny: float = 0
    status: str = "待采购"

class TranslateIn(BaseModel):
    chinese_title: str

class ListingIn(BaseModel):
    product_name: str
    category: str = ""
    brand: str = ""
    price_rub: float = 0
    weight_kg: float = 0
    description: str = ""
    images: list[str] = []

class Ali1688In(BaseModel):
    keyword: str
    limit: int = 20

class Open豆包SettingsIn(BaseModel):
    api_key: str
    model: str = "gpt-4o-mini"
    image_model: str = "doubao-seedream-3-0-t2i-250415"

class 豆包ChatIn(BaseModel):
    message: str
    context_type: str = "general"

class 豆包TitleIn(BaseModel):
    product_name: str
    category: str = ""
    keywords: str = ""

class 豆包ListingIn(BaseModel):
    product_name: str
    category: str = ""
    selling_points: str = ""
    price_rub: float = 0

class CustomerMessageIn(BaseModel):
    platform: str = "Ozon"
    chat_id: str = ""
    order_id: str = ""
    customer_name: str = ""
    product_name: str = ""
    message_text: str
    status: str = "未回复"

class CustomerReplyIn(BaseModel):
    message_id: int
    reply_text: str
    send_to_ozon: int = 0

class Smart1688SearchIn(BaseModel):
    keyword: str
    target_price_rub: float = 0
    target_weight_kg: float = 0
    max_purchase_price_cny: float = 0
    min_profit_rate: float = 0.25
    limit: int = 20

class 豆包ProductCopyIn(BaseModel):
    product_name: str
    category: str = ""
    material: str = ""
    size: str = ""
    color: str = ""
    target_customer: str = ""
    selling_points: str = ""

class 豆包ProductImageIn(BaseModel):
    product_name: str
    category: str = ""
    selling_points: str = ""
    image_type: str = "main"  # main, lifestyle, detail, comparison
    size: str = "1024x1024"
    quality: str = "medium"

class SupplierCandidateIn(BaseModel):
    keyword: str
    title: str
    price_cny: float
    shipping_cny: float = 0
    monthly_sales: int = 0
    repurchase_rate: float = 0
    shop_score: float = 0
    location: str = ""
    url: str = ""

class 豆包ReplyIn(BaseModel):
    message_id: int
    tone: str = "礼貌专业"


def hash_password(password: str) -> str:
    salt = "ozon_saas_erp_v1"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def seed_admin():
    c = sqlite3.connect(DB_PATH)
    cur = c.cursor()
    exists = cur.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not exists:
        cur.execute(
            "INSERT INTO users(username,password_hash,role,is_active,created_at) VALUES(?,?,?,?,?)",
            ("admin", hash_password("admin123"), "admin", 1, datetime.datetime.now().isoformat())
        )
        c.commit()
    c.close()

def require_role(token: Optional[str], roles=("admin","manager","staff")):
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")
    c = conn()
    row = c.execute("""
        SELECT u.id,u.username,u.role,u.is_active
        FROM sessions s JOIN users u ON s.user_id=u.id
        WHERE s.token=?
    """, (token,)).fetchone()
    c.close()
    if not row or not row["is_active"]:
        raise HTTPException(status_code=401, detail="登录已失效")
    if row["role"] not in roles:
        raise HTTPException(status_code=403, detail="权限不足")
    return dict(row)

def simple_ru_title(chinese_title: str) -> str:
    dictionary = {
        "帐篷": "Палатка туристическая",
        "露营": "кемпинг",
        "户外": "для отдыха на природе",
        "耳机": "Наушники",
        "手机壳": "Чехол для телефона",
        "玩具": "Игрушка",
        "收纳": "Органайзер",
        "厨房": "для кухни",
        "宠物": "для домашних животных",
        "儿童": "детский",
    }
    result = chinese_title
    for zh, ru in dictionary.items():
        result = result.replace(zh, ru)
    if result == chinese_title:
        result = chinese_title + " / Автоматический русский заголовок"
    return result[:180]



def pg_conn():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return None
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    except Exception as e:
        print("Postgres connection failed:", e)
        return None

def pg_execute(sql, params=None, fetch=False):
    c = pg_conn()
    if not c:
        return None
    try:
        cur = c.cursor()
        cur.execute(sql, params or ())
        result = cur.fetchall() if fetch else None
        c.commit()
        cur.close()
        c.close()
        return result
    except Exception as e:
        print("Postgres execute failed:", e)
        try:
            c.rollback()
            c.close()
        except Exception:
            pass
        return None

def save_order_to_pg(order):
    pg_execute("""
        insert into orders (
            posting_number, order_status, sku, product_name, quantity,
            sale_price, logistics_cost, commission, profit, customer_name,
            tracking_number, created_at
        ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
    """, (
        str(order.get("posting_number") or ""),
        str(order.get("status") or ""),
        str(order.get("sku") or ""),
        str(order.get("product_name") or ""),
        int(order.get("quantity") or 0),
        float(order.get("price_rub") or order.get("sale_price") or 0),
        float(order.get("logistics_cost") or 0),
        float(order.get("commission") or 0),
        float(order.get("profit") or 0),
        str(order.get("customer_name") or ""),
        str(order.get("tracking_number") or "")
    ))

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    cur = c.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT,
        month TEXT,
        product_name TEXT,
        category TEXT,
        fulfillment TEXT,
        purchase_cost_cny REAL,
        weight_kg REAL,
        domestic_shipping_cny REAL,
        package_cost_cny REAL,
        ad_cost_cny REAL,
        ozon_price_rub REAL,
        exchange_rate REAL,
        cny_price REAL,
        commission_rate REAL,
        platform_commission REAL,
        logistics_channel TEXT,
        logistics_fee REAL,
        total_cost REAL,
        net_profit REAL,
        profit_rate REAL,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS refunds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        month TEXT UNIQUE,
        amount_cny REAL DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ozon_settings (
        id INTEGER PRIMARY KEY CHECK (id=1),
        client_id TEXT,
        api_key TEXT,
        warehouse_id TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ozon_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        posting_number TEXT UNIQUE,
        order_id TEXT,
        status TEXT,
        in_process_at TEXT,
        shipment_date TEXT,
        product_name TEXT,
        sku TEXT,
        offer_id TEXT,
        quantity INTEGER,
        price_rub REAL,
        month TEXT,
        raw_json TEXT,
        synced_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT DEFAULT 'staff',
        is_active INTEGER DEFAULT 1,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE,
        product_name TEXT,
        quantity INTEGER DEFAULT 0,
        safety_stock INTEGER DEFAULT 0,
        warehouse TEXT DEFAULT '默认仓',
        updated_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT,
        product_name TEXT,
        supplier TEXT,
        quantity INTEGER,
        unit_cost_cny REAL,
        total_cost_cny REAL,
        status TEXT,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ozon_listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT,
        ru_title TEXT,
        category TEXT,
        brand TEXT,
        price_rub REAL,
        weight_kg REAL,
        description TEXT,
        payload_json TEXT,
        status TEXT DEFAULT '草稿',
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ai_settings (
        id INTEGER PRIMARY KEY CHECK (id=1),
        api_key TEXT,
        model TEXT DEFAULT 'gpt-4o-mini',
        image_model TEXT DEFAULT 'doubao-seedream-3-0-t2i-250415'
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ai_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        context_type TEXT,
        user_message TEXT,
        ai_response TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS customer_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT DEFAULT 'Ozon',
        chat_id TEXT,
        order_id TEXT,
        customer_name TEXT,
        product_name TEXT,
        message_text TEXT,
        translated_text TEXT,
        ai_reply TEXT,
        reply_text TEXT,
        status TEXT DEFAULT '未回复',
        created_at TEXT,
        replied_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customer_service_settings (
        id INTEGER PRIMARY KEY CHECK (id=1),
        auto_ai_reply INTEGER DEFAULT 0,
        allow_direct_ozon_send INTEGER DEFAULT 0,
        ozon_chat_list_path TEXT DEFAULT '',
        ozon_chat_send_path TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS supplier_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT,
        title TEXT,
        price_cny REAL,
        shipping_cny REAL,
        monthly_sales INTEGER,
        repurchase_rate REAL,
        shop_score REAL,
        location TEXT,
        url TEXT,
        ai_score REAL,
        estimated_profit REAL,
        estimated_profit_rate REAL,
        reason TEXT,
        created_at TEXT
    )
    """)


    try:
        cur.execute("ALTER TABLE ai_settings ADD COLUMN image_model TEXT DEFAULT 'doubao-seedream-3-0-t2i-250415'")
    except Exception:
        pass
    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_ai_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT,
        category TEXT,
        asset_type TEXT,
        title_ru TEXT,
        features_json TEXT,
        description_ru TEXT,
        image_prompt TEXT,
        image_path TEXT,
        created_at TEXT
    )
    """)
    c.commit()
    seed_admin()
    c.close()

def load_seed():
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

SEED = load_seed()

def detect_category(product_name: str) -> str:
    name = product_name or ""
    for item in SEED["keyword_map"]:
        if item["keyword"] in name:
            return item["category"]
    return "未匹配"

def commission_rate(category: str, price_rub: float, fulfillment: str) -> float:
    mode = "rfbs" if fulfillment.lower() == "rfbs" else "fbp"
    for row in SEED["commissions"]:
        if row["category"] == category:
            if price_rub <= 1500:
                return row[f"le1500_{mode}"] / 100
            elif price_rub <= 5000:
                return row[f"le5000_{mode}"] / 100
            else:
                return row[f"gt5000_{mode}"] / 100
    return 0

def best_logistics(weight_kg: float, price_rub: float):
    candidates = []
    for row in SEED["logistics"]:
        if row["min_weight_kg"] <= weight_kg <= row["max_weight_kg"] and row["min_price_rub"] <= price_rub <= row["max_price_rub"]:
            fee = row["ticket_fee"] + weight_kg * 1000 * row["price_per_gram"]
            candidates.append((fee, row["channel"]))
    if not candidates:
        return 0, "无匹配"
    fee, channel = sorted(candidates, key=lambda x: x[0])[0]
    return round(fee, 2), channel

def calculate(p: ProductIn):
    category = detect_category(p.product_name)
    cny_price = p.ozon_price_rub * p.exchange_rate
    rate = commission_rate(category, p.ozon_price_rub, p.fulfillment)
    platform_commission = cny_price * rate
    logistics_fee, logistics_channel = best_logistics(p.weight_kg, p.ozon_price_rub)
    total_cost = p.purchase_cost_cny + p.domestic_shipping_cny + p.package_cost_cny + p.ad_cost_cny + platform_commission + logistics_fee
    net_profit = cny_price - total_cost
    profit_rate = net_profit / cny_price if cny_price else 0
    return {
        "sku": p.sku or "",
        "month": p.month,
        "product_name": p.product_name,
        "category": category,
        "fulfillment": p.fulfillment,
        "purchase_cost_cny": p.purchase_cost_cny,
        "weight_kg": p.weight_kg,
        "domestic_shipping_cny": p.domestic_shipping_cny,
        "package_cost_cny": p.package_cost_cny,
        "ad_cost_cny": p.ad_cost_cny,
        "ozon_price_rub": p.ozon_price_rub,
        "exchange_rate": p.exchange_rate,
        "cny_price": round(cny_price, 2),
        "commission_rate": round(rate, 4),
        "platform_commission": round(platform_commission, 2),
        "logistics_channel": logistics_channel,
        "logistics_fee": logistics_fee,
        "total_cost": round(total_cost, 2),
        "net_profit": round(net_profit, 2),
        "profit_rate": round(profit_rate, 4),
    }

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/meta")
def meta():
    return {
        "categories": sorted({x["category"] for x in SEED["commissions"]}),
        "fulfillment": ["rFBS", "FBP"],
        "logistics_count": len(SEED["logistics"]),
        "commission_count": len(SEED["commissions"]),
        "keyword_count": len(SEED["keyword_map"]),
    }

@app.post("/api/calc")
def calc(p: ProductIn):
    return calculate(p)

@app.post("/api/products")
def add_product(p: ProductIn):
    row = calculate(p)
    c = conn()
    cur = c.cursor()
    cur.execute("""
    INSERT INTO products (
        sku, month, product_name, category, fulfillment, purchase_cost_cny, weight_kg,
        domestic_shipping_cny, package_cost_cny, ad_cost_cny, ozon_price_rub, exchange_rate,
        cny_price, commission_rate, platform_commission, logistics_channel, logistics_fee,
        total_cost, net_profit, profit_rate, created_at
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        row["sku"], row["month"], row["product_name"], row["category"], row["fulfillment"],
        row["purchase_cost_cny"], row["weight_kg"], row["domestic_shipping_cny"],
        row["package_cost_cny"], row["ad_cost_cny"], row["ozon_price_rub"], row["exchange_rate"],
        row["cny_price"], row["commission_rate"], row["platform_commission"], row["logistics_channel"],
        row["logistics_fee"], row["total_cost"], row["net_profit"], row["profit_rate"],
        datetime.datetime.now().isoformat()
    ))
    c.commit()
    row["id"] = cur.lastrowid
    c.close()
    return row

@app.get("/api/products")
def list_products():
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM products ORDER BY id DESC").fetchall()]
    c.close()
    return rows

@app.delete("/api/products/{product_id}")
def delete_product(product_id: int):
    c = conn()
    c.execute("DELETE FROM products WHERE id=?", (product_id,))
    c.commit()
    c.close()
    return {"ok": True}

@app.post("/api/refunds")
def set_refund(r: RefundIn):
    c = conn()
    c.execute("""
    INSERT INTO refunds(month, amount_cny) VALUES(?,?)
    ON CONFLICT(month) DO UPDATE SET amount_cny=excluded.amount_cny
    """, (r.month, r.amount_cny))
    c.commit()
    c.close()
    return {"ok": True}

@app.get("/api/operations")
def operations():
    c = conn()
    products = c.execute("SELECT * FROM products").fetchall()
    refunds = {x["month"]: x["amount_cny"] for x in c.execute("SELECT * FROM refunds").fetchall()}
    result = {}
    for p in products:
        m = p["month"] or "未填写"
        if m not in result:
            result[m] = {
                "month": m, "orders": 0, "sales": 0, "refund": refunds.get(m, 0),
                "ad_cost": 0, "purchase_cost": 0, "logistics_cost": 0,
                "platform_fee": 0, "net_profit": 0, "profit_rate": 0
            }
        x = result[m]
        x["orders"] += 1
        x["sales"] += p["cny_price"] or 0
        x["ad_cost"] += p["ad_cost_cny"] or 0
        x["purchase_cost"] += p["purchase_cost_cny"] or 0
        x["logistics_cost"] += p["logistics_fee"] or 0
        x["platform_fee"] += p["platform_commission"] or 0

    for m, x in result.items():
        x["refund"] = refunds.get(m, x["refund"])
        x["net_profit"] = x["sales"] - x["refund"] - x["ad_cost"] - x["purchase_cost"] - x["logistics_cost"] - x["platform_fee"]
        x["profit_rate"] = x["net_profit"] / x["sales"] if x["sales"] else 0
        for k in ["sales","refund","ad_cost","purchase_cost","logistics_cost","platform_fee","net_profit"]:
            x[k] = round(x[k], 2)
        x["profit_rate"] = round(x["profit_rate"], 4)
    c.close()
    return list(sorted(result.values(), key=lambda x: x["month"], reverse=True))


def get_ozon_settings():
    c = conn()
    row = c.execute("SELECT client_id, api_key, warehouse_id FROM ozon_settings WHERE id=1").fetchone()
    c.close()
    if not row or not row["client_id"] or not row["api_key"]:
        raise HTTPException(status_code=400, detail="请先在系统设置中填写 Ozon Client-Id 和 API-Key")
    return dict(row)

def ozon_headers(settings):
    return {
        "Client-Id": settings["client_id"],
        "Api-Key": settings["api_key"],
        "Content-Type": "application/json"
    }

def ozon_post(path, payload):
    settings = get_ozon_settings()
    url = "https://api-seller.ozon.ru" + path
    try:
        resp = requests.post(url, headers=ozon_headers(settings), json=payload, timeout=30)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Ozon API连接失败: {e}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

def month_from_date(date_text):
    if not date_text:
        return ""
    return date_text[:7]

@app.get("/api/ozon/settings")
def read_ozon_settings():
    c = conn()
    row = c.execute("SELECT client_id, warehouse_id FROM ozon_settings WHERE id=1").fetchone()
    c.close()
    if not row:
        return {"client_id": "", "api_key_set": False, "warehouse_id": ""}
    return {"client_id": row["client_id"] or "", "api_key_set": True, "warehouse_id": row["warehouse_id"] or ""}

@app.post("/api/ozon/settings")
def save_ozon_settings(s: OzonSettingsIn):
    c = conn()
    c.execute("""
    INSERT INTO ozon_settings(id, client_id, api_key, warehouse_id) VALUES(1,?,?,?)
    ON CONFLICT(id) DO UPDATE SET client_id=excluded.client_id, api_key=excluded.api_key, warehouse_id=excluded.warehouse_id
    """, (s.client_id.strip(), s.api_key.strip(), (s.warehouse_id or "").strip()))
    c.commit()
    c.close()
    return {"ok": True}

@app.post("/api/ozon/test")
def test_ozon_connection():
    # Ozon does not have a universal ping endpoint, so product list is used as a lightweight permission test.
    data = ozon_post("/v3/product/list", {"filter": {"visibility": "ALL"}, "last_id": "", "limit": 1})
    return {"ok": True, "sample": data}

@app.post("/api/ozon/sync-products")
def sync_ozon_products():
    # Returns a simple product list sample from Ozon. Full import can be extended to write to local products.
    return ozon_post("/v3/product/list", {"filter": {"visibility": "ALL"}, "last_id": "", "limit": 100})

@app.post("/api/ozon/sync-orders")
def sync_ozon_orders(req: SyncOrdersIn):
    path = "/v3/posting/fbs/list" if req.source.lower() == "fbs" else "/v2/posting/fbo/list"
    if req.source.lower() == "fbs":
        payload = {
            "dir": "ASC",
            "filter": {
                "since": req.date_from + "T00:00:00Z",
                "to": req.date_to + "T23:59:59Z"
            },
            "limit": req.limit,
            "offset": 0,
            "with": {
                "analytics_data": True,
                "barcodes": True,
                "financial_data": True,
                "translit": True
            }
        }
    else:
        payload = {
            "dir": "ASC",
            "filter": {
                "since": req.date_from + "T00:00:00Z",
                "to": req.date_to + "T23:59:59Z"
            },
            "limit": req.limit,
            "offset": 0,
            "with": {
                "analytics_data": True,
                "financial_data": True
            }
        }
    data = ozon_post(path, payload)
    rows = data.get("result", {}).get("postings", []) if isinstance(data.get("result"), dict) else data.get("result", [])
    c = conn()
    added = 0
    for posting in rows:
        posting_number = str(posting.get("posting_number") or posting.get("order_id") or "")
        status = posting.get("status", "")
        in_process_at = posting.get("in_process_at") or posting.get("created_at") or ""
        shipment_date = posting.get("shipment_date") or ""
        products = posting.get("products") or []
        if not products:
            products = [{"name": "", "sku": "", "offer_id": "", "quantity": 1, "price": 0}]
        for p in products:
            key = posting_number + "-" + str(p.get("sku") or p.get("offer_id") or p.get("name") or "")
            name = p.get("name") or p.get("product_name") or ""
            price_rub = float(p.get("price") or 0)
            month = month_from_date(in_process_at or shipment_date)
            raw = json.dumps({"posting": posting, "product": p}, ensure_ascii=False)
            c.execute("""
            INSERT OR REPLACE INTO ozon_orders
            (posting_number, order_id, status, in_process_at, shipment_date, product_name, sku, offer_id, quantity, price_rub, month, raw_json, synced_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                key, str(posting.get("order_id") or ""), status, in_process_at, shipment_date, name,
                str(p.get("sku") or ""), str(p.get("offer_id") or ""), int(p.get("quantity") or 1),
                price_rub, month, raw, datetime.datetime.now().isoformat()
            ))
            added += 1
            save_order_to_pg({
                "posting_number": key,
                "status": status,
                "product_name": name,
                "sku": str(p.get("sku") or ""),
                "quantity": int(p.get("quantity") or 1),
                "price_rub": price_rub,
                "tracking_number": posting.get("tracking_number") or ""
            })
    c.commit()
    c.close()
    return {"ok": True, "synced_items": added, "source": req.source, "raw_count": len(rows)}

@app.get("/api/ozon/orders")
def list_ozon_orders():
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM ozon_orders ORDER BY id DESC LIMIT 500").fetchall()]
    c.close()
    return rows


@app.post("/api/auth/login")
def login(data: LoginIn):
    c = conn()
    row = c.execute("SELECT * FROM users WHERE username=? AND is_active=1", (data.username,)).fetchone()
    if not row or row["password_hash"] != hash_password(data.password):
        c.close()
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = secrets.token_hex(24)
    c.execute("INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)", (token, row["id"], datetime.datetime.now().isoformat()))
    c.commit()
    c.close()
    return {"token": token, "username": row["username"], "role": row["role"]}

@app.get("/api/auth/me")
def me(token: Optional[str] = None):
    return require_role(token)

@app.get("/api/employees")
def employees(token: Optional[str] = None):
    require_role(token, ("admin",))
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT id,username,role,is_active,created_at FROM users ORDER BY id DESC").fetchall()]
    c.close()
    return rows

@app.post("/api/employees")
def add_employee(e: EmployeeIn, token: Optional[str] = None):
    require_role(token, ("admin",))
    c = conn()
    c.execute(
        "INSERT INTO users(username,password_hash,role,is_active,created_at) VALUES(?,?,?,?,?)",
        (e.username, hash_password(e.password), e.role, e.is_active, datetime.datetime.now().isoformat())
    )
    c.commit()
    c.close()
    return {"ok": True}

@app.post("/api/inventory")
def save_inventory(i: InventoryIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    c = conn()
    c.execute("""
    INSERT INTO inventory(sku,product_name,quantity,safety_stock,warehouse,updated_at)
    VALUES(?,?,?,?,?,?)
    ON CONFLICT(sku) DO UPDATE SET product_name=excluded.product_name, quantity=excluded.quantity,
    safety_stock=excluded.safety_stock, warehouse=excluded.warehouse, updated_at=excluded.updated_at
    """, (i.sku, i.product_name, i.quantity, i.safety_stock, i.warehouse, datetime.datetime.now().isoformat()))
    c.commit()
    c.close()
    return {"ok": True}

@app.get("/api/inventory")
def list_inventory(token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM inventory ORDER BY id DESC").fetchall()]
    c.close()
    return rows

@app.post("/api/purchases")
def add_purchase(p: PurchaseIn, token: Optional[str] = None):
    require_role(token, ("admin","manager"))
    c = conn()
    c.execute("""
    INSERT INTO purchases(sku,product_name,supplier,quantity,unit_cost_cny,total_cost_cny,status,created_at)
    VALUES(?,?,?,?,?,?,?,?)
    """, (p.sku, p.product_name, p.supplier, p.quantity, p.unit_cost_cny, p.quantity*p.unit_cost_cny, p.status, datetime.datetime.now().isoformat()))
    c.commit()
    c.close()
    return {"ok": True}

@app.get("/api/purchases")
def list_purchases(token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM purchases ORDER BY id DESC").fetchall()]
    c.close()
    return rows

@app.post("/api/translate/ru-title")
def translate_ru_title(t: TranslateIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    return {"ru_title": simple_ru_title(t.chinese_title)}

@app.post("/api/ozon/listings")
def create_listing(l: ListingIn, token: Optional[str] = None):
    require_role(token, ("admin","manager"))
    ru_title = simple_ru_title(l.product_name)
    payload = {
        "name": ru_title,
        "category": l.category,
        "brand": l.brand or "Нет бренда",
        "price": str(l.price_rub),
        "weight": l.weight_kg,
        "description": l.description,
        "images": l.images,
        "note": "这是Ozon Listing草稿数据。正式发布前需要补充Ozon类目ID、属性ID、图片URL、尺寸等必填字段。"
    }
    c = conn()
    c.execute("""
    INSERT INTO ozon_listings(product_name,ru_title,category,brand,price_rub,weight_kg,description,payload_json,status,created_at)
    VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (l.product_name, ru_title, l.category, l.brand, l.price_rub, l.weight_kg, l.description, json.dumps(payload, ensure_ascii=False), "草稿", datetime.datetime.now().isoformat()))
    c.commit()
    c.close()
    return {"ok": True, "ru_title": ru_title, "payload": payload}

@app.get("/api/ozon/listings")
def list_listings(token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM ozon_listings ORDER BY id DESC").fetchall()]
    c.close()
    return rows

@app.post("/api/1688/search")
def search_1688(a: Ali1688In, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    encoded = urllib.parse.quote(a.keyword)
    return {
        "keyword": a.keyword,
        "status": "接口占位已完成",
        "message": "1688官方开放平台/采集接口需要单独申请授权。当前先生成可打开的1688搜索链接，后续接入授权后可直接返回商品价格、图片、店铺、销量。",
        "search_url": f"https://s.1688.com/selloffer/offer_search.htm?keywords={encoded}",
        "items": []
    }


def get_ai_settings():
    c = conn()
    row = c.execute("SELECT api_key, model, image_model FROM ai_settings WHERE id=1").fetchone()
    c.close()
    if not row or not row["api_key"]:
        raise HTTPException(status_code=400, detail="请先在豆包设置中填写 Open豆包 API Key")
    return dict(row)

def call_doubao(messages, temperature=0.4):
    settings = get_ai_settings()
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    headers = {
        "Authorization": "Bearer " + settings["api_key"],
        "Content-Type": "application/json"
    }
    payload = {
    "model": settings["model"] or "doubao-seed-1-6-250615",
    "messages": messages,
    "temperature": temperature
}
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Open豆包 API连接失败: {e}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    return data["choices"][0]["message"]["content"]

def save_ai_log(context_type, user_message, ai_response):
    c = conn()
    c.execute(
        "INSERT INTO ai_logs(context_type,user_message,ai_response,created_at) VALUES(?,?,?,?)",
        (context_type, user_message, ai_response, datetime.datetime.now().isoformat())
    )
    c.commit()
    c.close()

@app.post("/api/ai/settings")
def save_ai_settings(s: Open豆包SettingsIn, token: Optional[str] = None):
    require_role(token, ("admin",))
    c = conn()
    c.execute("""
    INSERT INTO ai_settings(id, api_key, model, image_model) VALUES(1,?,?,?)
    ON CONFLICT(id) DO UPDATE SET api_key=excluded.api_key, model=excluded.model, image_model=excluded.image_model
    """, (s.api_key.strip(), s.model.strip() or "gpt-4o-mini", s.image_model.strip() or "doubao-seedream-3-0-t2i-250415"))
    c.commit()
    c.close()
    return {"ok": True}

@app.get("/api/ai/settings")
def read_ai_settings(token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    c = conn()
    row = c.execute("SELECT model, image_model, api_key FROM ai_settings WHERE id=1").fetchone()
    c.close()
    if not row:
        return {"model": "gpt-4o-mini", "image_model": "doubao-seedream-3-0-t2i-250415", "api_key_set": False}
    return {"model": row["model"] or "gpt-4o-mini", "image_model": row["image_model"] or "doubao-seedream-3-0-t2i-250415", "api_key_set": bool(row["api_key"])}

@app.post("/api/ai/chat")
def ai_chat(req: 豆包ChatIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    system = """你是一个Ozon跨境电商ERP助手。请用中文回答，重点帮助用户做利润分析、商品选品、库存采购、Ozon俄语Listing、物流费用、佣金和运营决策。回答要具体、可执行。"""
    answer = call_doubao([
        {"role": "system", "content": system},
        {"role": "user", "content": req.message}
    ])
    save_ai_log(req.context_type, req.message, answer)
    return {"answer": answer}

@app.post("/api/ai/ru-title")
def ai_ru_title(req: 豆包TitleIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    prompt = f"""请为Ozon平台生成一个俄语商品标题。
要求：
1. 俄语自然、适合Ozon搜索
2. 不夸大、不使用违禁词
3. 长度控制在180字符以内
4. 只输出标题，不要解释

商品名：{req.product_name}
类目：{req.category}
关键词：{req.keywords}
"""
    answer = call_doubao([{"role": "user", "content": prompt}], temperature=0.3)
    save_ai_log("ru_title", prompt, answer)
    return {"ru_title": answer.strip()}

@app.post("/api/ai/listing")
def ai_listing(req: 豆包ListingIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    prompt = f"""请为Ozon生成商品Listing文案，输出JSON格式：
{{
  "title_ru": "俄语标题",
  "description_ru": "俄语描述",
  "bullet_points_ru": ["卖点1","卖点2","卖点3","卖点4","卖点5"],
  "search_keywords_ru": ["关键词1","关键词2","关键词3"]
}}

商品名称：{req.product_name}
类目：{req.category}
卖点：{req.selling_points}
售价卢布：{req.price_rub}
"""
    answer = call_doubao([{"role": "user", "content": prompt}], temperature=0.35)
    save_ai_log("listing", prompt, answer)
    return {"listing": answer}

@app.get("/api/ai/logs")
def ai_logs(token: Optional[str] = None):
    require_role(token, ("admin","manager"))
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM ai_logs ORDER BY id DESC LIMIT 100").fetchall()]
    c.close()
    return rows


def try_translate_to_zh(text: str) -> str:
    # If 豆包 API is configured, translate. Otherwise return original.
    try:
        answer = call_doubao([
            {"role": "system", "content": "你是俄语/中文客服翻译助手。请把客户消息翻译成简体中文，只输出译文。"},
            {"role": "user", "content": text}
        ], temperature=0.1)
        return answer.strip()
    except Exception:
        return text

def build_customer_reply(message_row, tone="礼貌专业"):
    prompt = f"""你是Ozon跨境电商客服助手。
请根据客户问题生成俄语回复。
要求：
1. 语气：{tone}
2. 不承诺无法确认的时效
3. 不引导客户离开Ozon平台
4. 不发送外部联系方式
5. 如果信息不足，请礼貌说明会尽快核实
6. 只输出俄语回复

订单号：{message_row.get("order_id","")}
商品：{message_row.get("product_name","")}
客户消息：{message_row.get("message_text","")}
中文理解：{message_row.get("translated_text","")}
"""
    try:
        return call_doubao([{"role": "user", "content": prompt}], temperature=0.35).strip()
    except Exception:
        return "Здравствуйте! Спасибо за сообщение. Мы проверим информацию по вашему вопросу и ответим вам как можно скорее."

@app.post("/api/customer/messages")
def add_customer_message(m: CustomerMessageIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    translated = try_translate_to_zh(m.message_text)
    c = conn()
    cur = c.cursor()
    cur.execute("""
    INSERT INTO customer_messages(platform,chat_id,order_id,customer_name,product_name,message_text,translated_text,status,created_at)
    VALUES(?,?,?,?,?,?,?,?,?)
    """, (m.platform, m.chat_id, m.order_id, m.customer_name, m.product_name, m.message_text, translated, m.status, datetime.datetime.now().isoformat()))
    msg_id = cur.lastrowid
    row = dict(c.execute("SELECT * FROM customer_messages WHERE id=?", (msg_id,)).fetchone())
    ai_reply = build_customer_reply(row)
    c.execute("UPDATE customer_messages SET ai_reply=? WHERE id=?", (ai_reply, msg_id))
    c.commit()
    c.close()
    return {"ok": True, "id": msg_id, "translated_text": translated, "ai_reply": ai_reply}

@app.get("/api/customer/messages")
def list_customer_messages(status: Optional[str] = None, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    c = conn()
    if status:
        rows = [dict(x) for x in c.execute("SELECT * FROM customer_messages WHERE status=? ORDER BY id DESC", (status,)).fetchall()]
    else:
        rows = [dict(x) for x in c.execute("SELECT * FROM customer_messages ORDER BY id DESC LIMIT 300").fetchall()]
    c.close()
    return rows

@app.post("/api/customer/ai-reply")
def ai_customer_reply(req: 豆包ReplyIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    c = conn()
    row = c.execute("SELECT * FROM customer_messages WHERE id=?", (req.message_id,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(status_code=404, detail="消息不存在")
    rowd = dict(row)
    ai_reply = build_customer_reply(rowd, req.tone)
    c.execute("UPDATE customer_messages SET ai_reply=? WHERE id=?", (ai_reply, req.message_id))
    c.commit()
    c.close()
    return {"ai_reply": ai_reply}

@app.post("/api/customer/reply")
def reply_customer(req: CustomerReplyIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    c = conn()
    row = c.execute("SELECT * FROM customer_messages WHERE id=?", (req.message_id,)).fetchone()
    if not row:
        c.close()
        raise HTTPException(status_code=404, detail="消息不存在")
    rowd = dict(row)

    send_result = {"sent_to_ozon": False, "message": "已保存为本地回复"}
    if req.send_to_ozon:
        # Ozon customer chat direct API is kept configurable because availability depends on seller permissions.
        settings = c.execute("SELECT * FROM customer_service_settings WHERE id=1").fetchone()
        path = settings["ozon_chat_send_path"] if settings else ""
        if not path:
            c.close()
            raise HTTPException(status_code=400, detail="尚未配置Ozon聊天发送API路径，或当前店铺没有聊天API权限")
        try:
            payload = {"chat_id": rowd.get("chat_id"), "text": req.reply_text}
            result = ozon_post(path, payload)
            send_result = {"sent_to_ozon": True, "result": result}
        except Exception as e:
            c.close()
            raise HTTPException(status_code=502, detail=f"Ozon发送失败：{e}")

    c.execute(
        "UPDATE customer_messages SET reply_text=?, status='已回复', replied_at=? WHERE id=?",
        (req.reply_text, datetime.datetime.now().isoformat(), req.message_id)
    )
    c.commit()
    c.close()
    return {"ok": True, **send_result}

@app.post("/api/customer/sync-ozon")
def sync_ozon_customer_messages(token: Optional[str] = None):
    require_role(token, ("admin","manager"))
    c = conn()
    settings = c.execute("SELECT * FROM customer_service_settings WHERE id=1").fetchone()
    path = settings["ozon_chat_list_path"] if settings else ""
    if not path:
        c.close()
        raise HTTPException(status_code=400, detail="尚未配置Ozon聊天列表API路径，或当前店铺没有聊天API权限")
    data = ozon_post(path, {})
    # Generic parser: adapt if Ozon returns a different structure for your seller account.
    items = data.get("result", {}).get("messages", []) if isinstance(data.get("result"), dict) else data.get("result", [])
    count = 0
    for item in items:
        chat_id = str(item.get("chat_id") or item.get("dialog_id") or "")
        text = item.get("text") or item.get("message") or ""
        if not text:
            continue
        translated = try_translate_to_zh(text)
        c.execute("""
        INSERT INTO customer_messages(platform,chat_id,order_id,customer_name,product_name,message_text,translated_text,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)
        """, ("Ozon", chat_id, str(item.get("order_id") or ""), item.get("customer_name") or "", item.get("product_name") or "", text, translated, "未回复", datetime.datetime.now().isoformat()))
        count += 1
    c.commit()
    c.close()
    return {"ok": True, "synced": count, "raw": data}

@app.post("/api/customer/settings")
def save_customer_service_settings(data: dict, token: Optional[str] = None):
    require_role(token, ("admin",))
    c = conn()
    c.execute("""
    INSERT INTO customer_service_settings(id,auto_ai_reply,allow_direct_ozon_send,ozon_chat_list_path,ozon_chat_send_path)
    VALUES(1,?,?,?,?)
    ON CONFLICT(id) DO UPDATE SET auto_ai_reply=excluded.auto_ai_reply,
    allow_direct_ozon_send=excluded.allow_direct_ozon_send,
    ozon_chat_list_path=excluded.ozon_chat_list_path,
    ozon_chat_send_path=excluded.ozon_chat_send_path
    """, (
        int(data.get("auto_ai_reply",0)),
        int(data.get("allow_direct_ozon_send",0)),
        data.get("ozon_chat_list_path",""),
        data.get("ozon_chat_send_path","")
    ))
    c.commit()
    c.close()
    return {"ok": True}


def score_supplier_candidate(item, target_price_rub=0, exchange_rate=0.08, target_weight_kg=0, min_profit_rate=0.25):
    price = float(item.get("price_cny") or 0)
    shipping = float(item.get("shipping_cny") or 0)
    sales = int(item.get("monthly_sales") or 0)
    repurchase = float(item.get("repurchase_rate") or 0)
    shop = float(item.get("shop_score") or 0)
    sale_cny = float(target_price_rub or 0) * exchange_rate
    # Rough ERP cost estimate: purchase + domestic freight + estimated international logistics + estimated commission
    logistics = (target_weight_kg or 0) * 1000 * 0.0364 + 3.12
    commission = sale_cny * 0.14
    total_cost = price + shipping + logistics + commission
    profit = sale_cny - total_cost if sale_cny else 0
    profit_rate = profit / sale_cny if sale_cny else 0

    score = 0
    score += min(sales / 1000, 1) * 25
    score += min(repurchase / 30, 1) * 20
    score += min(shop / 5, 1) * 20
    if sale_cny:
        score += max(min(profit_rate / max(min_profit_rate, 0.01), 1), 0) * 25
    if price > 0:
        score += 10

    reasons = []
    if sales >= 500: reasons.append("销量较好")
    if repurchase >= 10: reasons.append("复购率较好")
    if shop >= 4.5: reasons.append("店铺评分较高")
    if profit_rate >= min_profit_rate: reasons.append("利润率达标")
    if not reasons: reasons.append("需要人工复核")

    return round(score, 2), round(profit, 2), round(profit_rate, 4), "、".join(reasons)

@app.post("/api/1688/smart-search")
def smart_1688_search(req: Smart1688SearchIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    # 当前版本先生成“智能采购候选框架”。正式接入1688开放平台/第三方API后，把真实商品数据写入 supplier_candidates 即可。
    # 为了让系统可直接演示，这里基于用户关键词生成可评估的候选模板。
    search_url = "https://s.1688.com/selloffer/offer_search.htm?keywords=" + urllib.parse.quote(req.keyword)
    demo_items = [
        {"keyword": req.keyword, "title": req.keyword + " 源头厂家款", "price_cny": max(req.max_purchase_price_cny or 20, 1), "shipping_cny": 6, "monthly_sales": 900, "repurchase_rate": 18, "shop_score": 4.8, "location": "浙江义乌", "url": search_url},
        {"keyword": req.keyword, "title": req.keyword + " 低价批发款", "price_cny": max((req.max_purchase_price_cny or 20) * 0.85, 1), "shipping_cny": 10, "monthly_sales": 420, "repurchase_rate": 9, "shop_score": 4.5, "location": "广东广州", "url": search_url},
        {"keyword": req.keyword, "title": req.keyword + " 高品质升级款", "price_cny": max((req.max_purchase_price_cny or 20) * 1.25, 1), "shipping_cny": 8, "monthly_sales": 260, "repurchase_rate": 15, "shop_score": 4.9, "location": "浙江杭州", "url": search_url}
    ]
    results = []
    c = conn()
    for item in demo_items:
        score, profit, profit_rate, reason = score_supplier_candidate(
            item,
            target_price_rub=req.target_price_rub,
            target_weight_kg=req.target_weight_kg,
            min_profit_rate=req.min_profit_rate
        )
        item.update({"ai_score": score, "estimated_profit": profit, "estimated_profit_rate": profit_rate, "reason": reason})
        results.append(item)
        c.execute("""
        INSERT INTO supplier_candidates(keyword,title,price_cny,shipping_cny,monthly_sales,repurchase_rate,shop_score,location,url,ai_score,estimated_profit,estimated_profit_rate,reason,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            item["keyword"], item["title"], item["price_cny"], item["shipping_cny"], item["monthly_sales"],
            item["repurchase_rate"], item["shop_score"], item["location"], item["url"], item["ai_score"],
            item["estimated_profit"], item["estimated_profit_rate"], item["reason"], datetime.datetime.now().isoformat()
        ))
    c.commit()
    c.close()
    results.sort(key=lambda x: x["ai_score"], reverse=True)
    return {
        "keyword": req.keyword,
        "search_url": search_url,
        "mode": "demo_scoring_framework",
        "notice": "已完成智能采购筛选框架。接入1688开放平台或第三方采集API后，可自动读取真实商品价格、销量、店铺评分并排序。",
        "best": results[0] if results else None,
        "items": results
    }

@app.post("/api/1688/candidates")
def add_supplier_candidate(item: SupplierCandidateIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    score, profit, profit_rate, reason = score_supplier_candidate(item.dict())
    c = conn()
    c.execute("""
    INSERT INTO supplier_candidates(keyword,title,price_cny,shipping_cny,monthly_sales,repurchase_rate,shop_score,location,url,ai_score,estimated_profit,estimated_profit_rate,reason,created_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (item.keyword,item.title,item.price_cny,item.shipping_cny,item.monthly_sales,item.repurchase_rate,item.shop_score,item.location,item.url,score,profit,profit_rate,reason,datetime.datetime.now().isoformat()))
    c.commit()
    c.close()
    return {"ok": True, "ai_score": score, "reason": reason}

@app.get("/api/1688/candidates")
def list_supplier_candidates(token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM supplier_candidates ORDER BY ai_score DESC, id DESC LIMIT 200").fetchall()]
    c.close()
    return rows


def call_openai_image(prompt: str, size="1024x1024", quality="medium"):
    settings = get_ai_settings()
    # Open豆包 Image API returns base64-encoded image data.
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    headers = {
        "Authorization": "Bearer " + settings["api_key"],
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.get("image_model") or "doubao-seedream-3-0-t2i-250415",
        "prompt": prompt,
        "size": size or "1024x1024",
        "quality": quality or "medium",
        "n": 1,
        "output_format": "png",
        "response_format": "b64_json"
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"图片生成API连接失败: {e}")
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    item = data.get("data", [{}])[0]
    b64 = item.get("b64_json")
    if not b64 and item.get("url"):
        img_resp = requests.get(item["url"], timeout=60)
        if img_resp.status_code >= 400:
            raise HTTPException(status_code=502, detail="图片URL下载失败")
        b64 = base64.b64encode(img_resp.content).decode("utf-8")
    if not b64:
        raise HTTPException(status_code=502, detail="图片生成接口没有返回图片数据")
    return b64

def product_image_prompt(req: 豆包ProductImageIn):
    type_map = {
        "main": "clean e-commerce main product image on pure white background, centered product, realistic lighting, no logo, no watermark, no text",
        "lifestyle": "realistic lifestyle scene showing the product in use, natural lighting, premium e-commerce style, no watermark, no readable text",
        "detail": "close-up detail product image showing material, texture and functional details, clean background, no watermark, no text",
        "comparison": "comparison style product image showing advantages visually, clean modern e-commerce composition, no brand logos, no readable text"
    }
    scene = type_map.get(req.image_type, type_map["main"])
    return f"""Create a high-quality commercial product image for an Ozon marketplace listing.

Product: {req.product_name}
Category: {req.category}
Key selling points: {req.selling_points}
Image type: {req.image_type}
Style requirements: {scene}
Important rules:
- Realistic product photography style
- No brand logo unless provided by user
- No copyrighted characters
- No misleading medical/safety claims
- No text on image unless explicitly requested
- Suitable for marketplace listing
"""

@app.post("/api/ai/product-copy")
def ai_product_copy(req: 豆包ProductCopyIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    prompt = f"""你是Ozon跨境电商商品运营专家。请根据商品信息生成适合Ozon上传的商品内容。
请输出JSON，字段必须包含：
{{
  "title_ru": "俄语商品标题，180字符以内",
  "features_zh": ["中文特点1","中文特点2","中文特点3","中文特点4","中文特点5"],
  "features_ru": ["俄语卖点1","俄语卖点2","俄语卖点3","俄语卖点4","俄语卖点5"],
  "description_zh": "中文商品描述",
  "description_ru": "俄语商品描述",
  "search_keywords_ru": ["俄语关键词1","俄语关键词2","俄语关键词3","俄语关键词4","俄语关键词5"],
  "image_prompt_main": "英文主图生成提示词",
  "image_prompt_lifestyle": "英文场景图生成提示词"
}}

商品名称：{req.product_name}
类目：{req.category}
材质：{req.material}
尺寸：{req.size}
颜色：{req.color}
目标客户：{req.target_customer}
卖点补充：{req.selling_points}

要求：
1. 不夸大功效，不写虚假承诺
2. 不使用侵权品牌词
3. 适合Ozon俄罗斯消费者
4. 图片提示词要适合电商主图和场景图
"""
    answer = call_doubao([{"role": "user", "content": prompt}], temperature=0.35)
    c = conn()
    c.execute("""
    INSERT INTO product_ai_assets(product_name,category,asset_type,features_json,created_at)
    VALUES(?,?,?,?,?)
    """, (req.product_name, req.category, "copy", answer, datetime.datetime.now().isoformat()))
    c.commit()
    c.close()
    save_ai_log("product_copy", prompt, answer)
    return {"content": answer}

@app.post("/api/ai/product-image")
def ai_product_image(req: 豆包ProductImageIn, token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    prompt = product_image_prompt(req)
    b64, img_ext = call_doubao_image(prompt, req.size)
    filename = f"product_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}.{img_ext}"
    path = ASSETS_DIR / filename
    path.write_bytes(base64.b64decode(b64))
    url_path = f"/generated-assets/{filename}"
    c = conn()
    c.execute("""
    INSERT INTO product_ai_assets(product_name,category,asset_type,image_prompt,image_path,created_at)
    VALUES(?,?,?,?,?,?)
    """, (req.product_name, req.category, req.image_type, prompt, url_path, datetime.datetime.now().isoformat()))
    c.commit()
    c.close()
    return {"image_url": url_path, "prompt": prompt}

@app.get("/api/ai/product-assets")
def list_product_assets(token: Optional[str] = None):
    require_role(token, ("admin","manager","staff"))
    c = conn()
    rows = [dict(x) for x in c.execute("SELECT * FROM product_ai_assets ORDER BY id DESC LIMIT 200").fetchall()]
    c.close()
    return rows


@app.get("/api/pro/orders")
def pro_orders(token: Optional[str] = None):
    rows = pg_execute("""
        select id, posting_number, order_status, sku, product_name, quantity,
               sale_price, logistics_cost, commission, profit, customer_name,
               tracking_number, created_at
        from orders
        order by created_at desc
        limit 500
    """, fetch=True)
    if rows is not None:
        return rows
    c = conn()
    local = [dict(x) for x in c.execute("select * from ozon_orders order by id desc limit 500").fetchall()]
    c.close()
    return local

@app.get("/api/pro/orders/{posting_number}")
def pro_order_detail(posting_number: str, token: Optional[str] = None):
    rows = pg_execute("""
        select * from orders where posting_number=%s order by created_at desc limit 1
    """, (posting_number,), fetch=True)
    if rows:
        return {"source": "postgres", "order": rows[0]}
    c = conn()
    row = c.execute("select * from ozon_orders where posting_number like ? order by id desc limit 1", (f"%{posting_number}%",)).fetchone()
    c.close()
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"source": "local", "order": dict(row)}

@app.get("/api/pro/dashboard")
def pro_dashboard(token: Optional[str] = None):
    rows = pg_execute("""
        select
          count(*)::int as orders,
          coalesce(sum(sale_price),0)::float as sales,
          coalesce(sum(profit),0)::float as profit,
          coalesce(sum(quantity),0)::int as quantity
        from orders
    """, fetch=True)
    if rows is not None and rows:
        total = rows[0]
        top = pg_execute("""
            select product_name, sku, count(*)::int as orders, coalesce(sum(sale_price),0)::float as sales
            from orders
            group by product_name, sku
            order by sales desc
            limit 10
        """, fetch=True) or []
        recent = pg_execute("""
            select posting_number, order_status, product_name, sku, quantity, sale_price, created_at
            from orders
            order by created_at desc
            limit 10
        """, fetch=True) or []
        return {"summary": total, "top_products": top, "recent_orders": recent}

    c = conn()
    local = [dict(x) for x in c.execute("select * from ozon_orders order by id desc limit 50").fetchall()]
    c.close()
    sales = sum(float(x.get("price_rub") or 0) for x in local)
    return {
        "summary": {"orders": len(local), "sales": sales, "profit": 0, "quantity": sum(int(x.get("quantity") or 0) for x in local)},
        "top_products": [],
        "recent_orders": local[:10]
    }


def get_doubao_settings():
    env_key = os.environ.get("DOUBAO_API_KEY") or os.environ.get("ARK_API_KEY") or ""
    env_model = os.environ.get("DOUBAO_MODEL") or "doubao-seed-1-6-250615"
    env_image_model = os.environ.get("DOUBAO_IMAGE_MODEL") or "doubao-seedream-3-0-t2i-250415"
    env_base = os.environ.get("DOUBAO_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
    try:
        c = conn()
        c.execute("""
        CREATE TABLE IF NOT EXISTS doubao_settings (
            id INTEGER PRIMARY KEY CHECK (id=1),
            api_key TEXT,
            base_url TEXT DEFAULT 'https://ark.cn-beijing.volces.com/api/v3',
            model TEXT DEFAULT 'doubao-seed-1-6-250615',
            image_model TEXT DEFAULT 'doubao-seedream-3-0-t2i-250415'
        )
        """)
        try:
            c.execute("ALTER TABLE doubao_settings ADD COLUMN image_model TEXT DEFAULT 'doubao-seedream-3-0-t2i-250415'")
        except Exception:
            pass
        row = c.execute("SELECT api_key, base_url, model, image_model FROM doubao_settings WHERE id=1").fetchone()
        c.close()
        if row:
            return {
                "api_key": env_key or row["api_key"] or "",
                "base_url": row["base_url"] or env_base,
                "model": row["model"] or env_model,
                "image_model": row["image_model"] or env_image_model,
            }
    except Exception as e:
        print("get_doubao_settings failed:", e)
    return {"api_key": env_key, "base_url": env_base, "model": env_model, "image_model": env_image_model}

def call_doubao(messages, temperature=0.35):
    s = get_doubao_settings()
    if not s.get("api_key"):
        raise HTTPException(status_code=400, detail="未配置豆包 API Key。请在豆包助手页面或 Railway Variables 中配置 DOUBAO_API_KEY。")
    url = (s.get("base_url") or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/") + "/chat/completions"
    headers = {"Authorization": "Bearer " + s["api_key"], "Content-Type": "application/json"}
    payload = {"model": "ep-20260518230413-wm6nv", "messages": messages, "temperature": temperature}
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    return data["choices"][0]["message"]["content"]

def call_doubao_image(prompt: str, size="1024x1024"):
    s = get_doubao_settings()
    if not s.get("api_key"):
        raise HTTPException(status_code=400, detail="未配置豆包 API Key。请先保存豆包配置。")
    url = (s.get("base_url") or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/") + "/images/generations"
    headers = {"Authorization": "Bearer " + s["api_key"], "Content-Type": "application/json"}
    payload = {
        "model": s.get("image_model") or "doubao-seedream-3-0-t2i-250415",
        "prompt": prompt,
        "size": size or "1024x1024",
        "response_format": "b64_json"
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    if resp.status_code >= 400:
        safe = prompt.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")[:900]
        svg = "<svg xmlns='http://www.w3.org/2000/svg' width='1024' height='1024'><rect width='100%' height='100%' fill='#f8fafc'/><rect x='72' y='72' width='880' height='880' rx='42' fill='white' stroke='#dbeafe' stroke-width='8'/><text x='512' y='180' text-anchor='middle' font-size='46' font-family='Arial' fill='#1e3a8a'>豆包商品图提示词</text><foreignObject x='130' y='250' width='760' height='560'><div xmlns='http://www.w3.org/1999/xhtml' style='font-size:26px;line-height:1.5;font-family:Arial;color:#0f172a;'>" + safe + "</div></foreignObject><text x='512' y='900' text-anchor='middle' font-size='24' font-family='Arial' fill='#64748b'>请确认火山方舟图片模型权限后可直接生成真实图片</text></svg>"
        return base64.b64encode(svg.encode("utf-8")).decode("utf-8"), "svg"
    data = resp.json()
    item = data.get("data", [{}])[0]
    b64 = item.get("b64_json")
    if not b64 and item.get("url"):
        img_resp = requests.get(item["url"], timeout=60)
        img_resp.raise_for_status()
        b64 = base64.b64encode(img_resp.content).decode("utf-8")
    if not b64:
        raise HTTPException(status_code=502, detail="豆包图片接口没有返回图片数据")
    return b64, "png"


@app.get("/api/doubao/settings")
def doubao_settings_get(token: Optional[str] = None):
    s = get_doubao_settings()
    return {"api_key_set": bool(s.get("api_key")), "base_url": s.get("base_url"), "model": s.get("model"), "image_model": s.get("image_model")}

@app.post("/api/doubao/settings")
def doubao_settings_save(s: DoubaoSettingsIn, token: Optional[str] = None):
    c = conn()
    c.execute("""
    CREATE TABLE IF NOT EXISTS doubao_settings (
        id INTEGER PRIMARY KEY CHECK (id=1),
        api_key TEXT,
        base_url TEXT DEFAULT 'https://ark.cn-beijing.volces.com/api/v3',
        model TEXT DEFAULT 'doubao-seed-1-6-250615',
        image_model TEXT DEFAULT 'doubao-seedream-3-0-t2i-250415'
    )
    """)
    try:
        c.execute("ALTER TABLE doubao_settings ADD COLUMN image_model TEXT DEFAULT 'doubao-seedream-3-0-t2i-250415'")
    except Exception:
        pass
    c.execute("""
    INSERT INTO doubao_settings(id, api_key, base_url, model, image_model)
    VALUES(1,?,?,?,?)
    ON CONFLICT(id) DO UPDATE SET api_key=excluded.api_key, base_url=excluded.base_url, model=excluded.model, image_model=excluded.image_model
    """, (s.api_key.strip(), s.base_url.strip() or "https://ark.cn-beijing.volces.com/api/v3", s.model.strip() or "doubao-seed-1-6-250615", s.image_model.strip() or "doubao-seedream-3-0-t2i-250415"))
    c.commit()
    c.close()
    return {"ok": True}

@app.post("/api/doubao/chat")
def doubao_chat(req: DoubaoChatIn, token: Optional[str] = None):
    answer = call_doubao([{"role":"system","content":req.system},{"role":"user","content":req.message}])
    return {"answer": answer}

@app.post("/api/doubao/customer-reply")
def doubao_customer_reply(data: dict, token: Optional[str] = None):
    msg = data.get("message") or data.get("customer_message") or ""
    if not msg:
        raise HTTPException(status_code=400, detail="请填写客户消息")
    prompt = f"""你是Ozon跨境电商客服助手。请根据客户消息生成俄语回复。
要求：礼貌专业；不承诺无法确认的时效；不引导客户离开Ozon；不发送外部联系方式；只输出俄语回复。
客户消息：{msg}
订单信息：{data.get("order_info") or ""}
"""
    return {"reply": call_doubao([{"role":"user","content":prompt}], temperature=0.3)}

frontend_path = ROOT.parent / "frontend"
app.mount("/generated-assets", StaticFiles(directory=str(ASSETS_DIR)), name="generated_assets")

if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
