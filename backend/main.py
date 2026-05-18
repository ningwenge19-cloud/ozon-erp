
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import sqlite3, json, datetime, os

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "ozon_erp.db"
SEED_PATH = ROOT / "seed_data.json"

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
    c.commit()
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

frontend_path = ROOT.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


def call_doubao(messages, temperature=0.35):
    s = get_doubao_settings()
    if not s.get("api_key"):
        raise HTTPException(status_code=400, detail="未配置豆包 API Key。请先在 Railway Variables 配置 DOUBAO_API_KEY。")

    url = (s.get("base_url") or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/") + "/responses"
    headers = {
        "Authorization": "Bearer " + s["api_key"],
        "Content-Type": "application/json"
    }

    user_text = messages[-1]["content"] if messages else "你好"
  payload = {
    "model": s.get("model") or "ep-20260519003414-pf6vx",
    "input": [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": user_text}
            ]
        }
    ]
}
    "temperature": temperature
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
        return str(data)

