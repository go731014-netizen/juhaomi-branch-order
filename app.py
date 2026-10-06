import streamlit as st
import sqlite3
import json
from datetime import datetime

st.set_page_config(page_title="揪好覓叫貨", page_icon="🛒")

B = ["文萊","裕誠","鳳山","美術","恆春"]
C = sqlite3.connect("order.db", check_same_thread=False)

C.execute("CREATE TABLE IF NOT EXISTS p(id INTEGER PRIMARY KEY,name TEXT,unit TEXT,qty INTEGER)")
C.execute("CREATE TABLE IF NOT EXISTS o(id INTEGER PRIMARY KEY,tm TEXT,branch TEXT,items TEXT,status TEXT)")
C.commit()

if C.execute("SELECT COUNT(*) FROM p").fetchone()[0] == 0:
    C.executemany("INSERT INTO p(name,unit,qty) VALUES(?,?,?)",[
        ("貝貝南瓜","公斤",30),
        ("北海道洋蔥","包",20),
        ("玉里大西瓜","顆",10)
    ])
    C.commit()

st.title("🛒 揪好覓｜分店叫貨系統")

mode = st.sidebar.radio("模式",["🏪 分店叫貨","👑 總部管理"])

if mode == "🏪 分店叫貨":

    branch = st.selectbox("選擇分店",B)
    rows = C.execute("SELECT * FROM p WHERE qty>0").fetchall()

    cart = []

    for r in rows:
        q = st.number_input(
            f"{r[1]}｜{r[2]}｜可叫 {r[3]}",
            0,r[3],0,key=f"p{r[0]}"
        )
        if q:
            cart.append({
                "商品":r[1],
                "單位":r[2],
                "數量":q
            })

    st.subheader("🧾 叫貨內容")

    if cart:
        for x in cart:
            st.write(f"• {x['商品']} × {x['數量']} {x['單位']}")

        if st.button("✅ 送出叫貨單",type="primary"):
            C.execute(
                "INSERT INTO o VALUES(NULL,?,?,?,?)",
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    branch,
                    json.dumps(cart,ensure_ascii=False),
                    "待配貨"
                )
            )
            C.commit()
            st.success("叫貨單已送出！")
            st.rerun()
    else:
        st.info("請選擇商品數量")

else:

    st.header("👑 總部管理")

    st.subheader("📦 商品數量")

    rows = C.execute("SELECT * FROM p").fetchall()

    for r in rows:
        col1,col2 = st.columns([3,1])
        col1.write(f"{r[1]}｜{r[2]}")
        q = col2.number_input(
            "可叫數量",
            0,999,r[3],
            key=f"stock{r[0]}"
        )

        if q != r[3]:
            C.execute("UPDATE p SET qty=? WHERE id=?", (q,r[0]))
            C.commit()

    st.divider()
    st.subheader("📋 分店叫貨單")

    orders = C.execute(
        "SELECT * FROM o ORDER BY id DESC"
    ).fetchall()

    if not orders:
        st.info("目前沒有叫貨單")
    else:
        for r in orders:
            st.write(
                f"**{r[2]}店**｜{r[1]}｜{r[4]}"
            )

            items = json.loads(r[3])

            for x in items:
                st.write(
                    f"　{x['商品']} × {x['數量']} {x['單位']}"
                )

            if r[4] != "已配貨":
                if st.button(
                    "✅ 已配貨",
                    key=f"ok{r[0]}"
                ):
                    C.execute(
                        "UPDATE o SET status='已配貨' WHERE id=?",
                        (r[0],)
                    )
                    C.commit()
                    st.rerun()

st.sidebar.caption("揪好覓｜五間分店")
