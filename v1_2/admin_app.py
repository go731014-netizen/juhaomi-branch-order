import pandas as pd
import streamlit as st
from common import config, get_rows, insert_row, patch_row, load_stores, load_products, shipped_totals, derived_status

st.set_page_config(page_title="揪好覓｜管理者中心", page_icon="🔐", layout="wide")
st.title("🔐 揪好覓｜管理者中心")
st.caption("全部門市叫貨・分批出貨・出貨歷史・商品管理")

password = st.secrets.get("ADMIN_PASSWORD", "")
if not password:
    st.error("請先在 Streamlit Secrets 設定 ADMIN_PASSWORD。")
    st.stop()
if not st.session_state.get("admin_ok", False):
    with st.form("admin_login"):
        entered = st.text_input("管理者密碼", type="password")
        login = st.form_submit_button("登入管理者中心", type="primary")
    if login:
        if entered == password:
            st.session_state["admin_ok"] = True
            st.rerun()
        else:
            st.error("密碼不正確。")
    st.stop()
if st.button("登出管理者"):
    st.session_state["admin_ok"] = False
    st.rerun()

url, key = config(admin=True)
try:
    stores = load_stores(url, key)
    products = load_products(url, key, active_only=False)
    orders = get_rows(url, key, "restock_requests", {"select": "*", "order": "id.desc", "limit": "1000"})
    shipments = get_rows(url, key, "shipment_records", {
        "select": "id,restock_request_id,quantity,note,shipped_by,shipped_at", "order": "shipped_at.desc", "limit": "3000"
    })
except Exception as e:
    st.error("讀取管理資料失敗。請確認管理者金鑰及資料表；若 shipment_records 尚未建立，請先執行隨附 SQL。")
    st.code(str(e))
    st.stop()

store_map = {s["id"]: s["store_name"] for s in stores}
product_map = {p["id"]: p["product_name"] for p in products}
totals = shipped_totals(shipments)

tab_orders, tab_ship, tab_history, tab_products = st.tabs(["📋 全部叫貨紀錄", "🚚 登記出貨", "🧾 出貨歷史", "🛠️ 商品管理"])

with tab_orders:
    rows = []
    for o in orders:
        requested = float(o.get("requested_quantity") or 0)
        shipped = totals.get(o["id"], 0.0)
        rows.append({
            "叫貨單號": o.get("id"), "門市": store_map.get(o.get("store_id"), "未知門市"),
            "商品": product_map.get(o.get("product_id"), f"商品 #{o.get('product_id')}"),
            "叫貨數量": requested, "累計出貨": shipped,
            "剩餘未出貨": max(0, requested - shipped),
            "出貨狀態": derived_status(requested, shipped),
            "原叫貨狀態": o.get("status"), "叫貨備註": o.get("note"), "申請時間": o.get("created_at")
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有叫貨紀錄。")
    st.caption("出貨狀態依每筆出貨紀錄累計計算；原本叫貨狀態欄位保留，不會因新增出貨而被覆寫。")

with tab_ship:
    pending = []
    for o in orders:
        requested = float(o.get("requested_quantity") or 0)
        shipped = totals.get(o["id"], 0.0)
        remaining = max(0.0, requested - shipped)
        if remaining > 1e-9:
            label = (f"#{o['id']}｜{store_map.get(o.get('store_id'), '未知門市')}｜"
                     f"{product_map.get(o.get('product_id'), '未知商品')}｜剩餘 {remaining:g}")
            pending.append((label, o, remaining))
    if not pending:
        st.success("目前沒有待出貨或部分出貨的叫貨項目。")
    else:
        labels = [x[0] for x in pending]
        selected_label = st.selectbox("選擇要出貨的叫貨項目", labels)
        _, order, remaining = next(x for x in pending if x[0] == selected_label)
        requested = float(order.get("requested_quantity") or 0)
        already = totals.get(order["id"], 0.0)
        st.write(f"**門市：** {store_map.get(order.get('store_id'), '未知門市')}")
        st.write(f"**商品：** {product_map.get(order.get('product_id'), '未知商品')}")
        st.write(f"**原叫貨數量：** {requested:g}　｜　**累計已出：** {already:g}　｜　**剩餘：** {remaining:g}")
        with st.form("shipment_form", clear_on_submit=True):
            qty = st.number_input("本次實際出貨數量", min_value=0.01, max_value=float(remaining), value=float(remaining), step=1.0)
            shipped_by = st.text_input("出貨人員（選填）")
            note = st.text_area("本次出貨備註（選填）", placeholder="例如：先出 6 件，其餘待補／缺貨／商品更換")
            submit_ship = st.form_submit_button("確認登記本次出貨", type="primary")
        if submit_ship:
            if qty <= 0 or qty > remaining + 1e-9:
                st.error(f"出貨數量必須大於 0，且不可超過剩餘數量 {remaining:g}。")
            else:
                try:
                    insert_row(url, key, "shipment_records", {
                        "restock_request_id": order["id"], "quantity": float(qty),
                        "note": note.strip() or None, "shipped_by": shipped_by.strip() or None
                    })
                    st.success("本次出貨已登記，歷史紀錄已保留。")
                    st.rerun()
                except Exception as e:
                    st.error("出貨登記失敗，請確認 shipment_records 資料表及欄位。")
                    st.code(str(e))

with tab_history:
    if shipments:
        rows = []
        order_map = {o["id"]: o for o in orders}
        for s in shipments:
            o = order_map.get(s.get("restock_request_id"), {})
            rows.append({
                "出貨紀錄編號": s.get("id"), "叫貨單號": s.get("restock_request_id"),
                "門市": store_map.get(o.get("store_id"), "未知門市"),
                "商品": product_map.get(o.get("product_id"), "未知商品"),
                "本次出貨數量": s.get("quantity"), "出貨時間": s.get("shipped_at"),
                "出貨人員": s.get("shipped_by"), "出貨備註": s.get("note")
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("目前還沒有出貨紀錄。")

with tab_products:
    st.subheader("商品清單")
    if products:
        st.dataframe(pd.DataFrame([{
            "商品編號": p.get("product_code"), "商品名稱": p.get("product_name"),
            "條碼": p.get("barcode"), "單位": p.get("unit"), "啟用中": p.get("is_active")
        } for p in products]), use_container_width=True, hide_index=True)
        opts = {f"{p.get('product_code')}｜{p.get('product_name')}｜ID {p['id']}": p for p in products}
        selected_label = st.selectbox("選擇商品修改", list(opts.keys()))
        item = opts[selected_label]
        with st.form("edit_product"):
            name = st.text_input("商品名稱", value=item.get("product_name") or "")
            barcode = st.text_input("商品條碼", value=item.get("barcode") or "")
            unit = st.text_input("單位", value=item.get("unit") or "個")
            min_stock = st.number_input("最低庫存欄位（僅保留舊資料，不在門市端顯示）", min_value=0, value=int(item.get("min_stock") or 0))
            active = st.checkbox("啟用商品（啟用後門市可叫貨）", value=bool(item.get("is_active")))
            save = st.form_submit_button("儲存商品修改")
        if save:
            try:
                patch_row(url, key, "products", {"id": f"eq.{item['id']}"}, {
                    "product_name": name.strip(), "barcode": barcode.strip() or None,
                    "unit": unit.strip(), "min_stock": int(min_stock), "is_active": active
                })
                st.success("商品資料已更新。")
                st.rerun()
            except Exception as e:
                st.error("商品修改失敗。")
                st.code(str(e))
    else:
        st.info("目前沒有商品。")
