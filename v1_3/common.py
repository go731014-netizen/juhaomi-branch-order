import requests
import streamlit as st

UNITS = ["個", "包", "盒", "袋", "瓶", "罐", "斤", "公斤", "箱", "組", "支", "件"]
TEMPERATURES = ["冷凍", "冷藏", "常溫"]


def config(admin=False):
    url = st.secrets.get("SUPABASE_URL", "").rstrip("/")
    key_name = "SUPABASE_SERVICE_ROLE_KEY" if admin else "SUPABASE_ANON_KEY"
    key = st.secrets.get(key_name, "")
    if not url or not key:
        st.error(f"請在 Streamlit Secrets 設定 SUPABASE_URL 與 {key_name}。")
        st.stop()
    return url, key


def headers(key, prefer="return=representation"):
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def get_rows(url, key, table, params=None):
    r = requests.get(f"{url}/rest/v1/{table}", headers=headers(key), params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def insert_row(url, key, table, data):
    r = requests.post(f"{url}/rest/v1/{table}", headers=headers(key), json=data, timeout=30)
    r.raise_for_status()
    return r.json()


def patch_row(url, key, table, filters, data):
    r = requests.patch(
        f"{url}/rest/v1/{table}", headers=headers(key, "return=minimal"),
        params=filters, json=data, timeout=30
    )
    r.raise_for_status()


def load_stores(url, key):
    return get_rows(url, key, "stores", {"select": "id,store_name", "order": "id"})


def load_products(url, key, active_only=True):
    params = {
        "select": "id,product_code,product_name,barcode,unit,min_stock,is_active,created_at,temperature",
        "order": "product_name"
    }
    if active_only:
        params["is_active"] = "eq.true"
    return get_rows(url, key, "products", params)


def shipped_totals(shipments):
    totals = {}
    for row in shipments:
        request_id = row.get("restock_request_id")
        totals[request_id] = totals.get(request_id, 0.0) + float(row.get("quantity") or 0)
    return totals


def derived_status(requested, shipped):
    requested = float(requested or 0)
    shipped = float(shipped or 0)
    if shipped <= 0:
        return "待出貨"
    if shipped + 1e-9 < requested:
        return "部分出貨"
    return "已出貨"


def temperature_of(product):
    value = (product or {}).get("temperature") or "常溫"
    return value if value in TEMPERATURES else "常溫"
