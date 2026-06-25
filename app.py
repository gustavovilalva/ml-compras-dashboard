import streamlit as st
import requests
import os
import math
import json
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────
ML_APP_ID      = os.getenv("ML_APP_ID", "")
ML_SECRET      = os.getenv("ML_CLIENT_SECRET", "")
REDIRECT_URI   = os.getenv("ML_REDIRECT_URI", "")
ML_AUTH_URL    = "https://auth.mercadolivre.com.br/authorization"
ML_TOKEN_URL   = "https://api.mercadolibre.com/oauth/token"
ML_API_BASE    = "https://api.mercadolibre.com"
BOXES_FILE     = "boxes_config.json"

st.set_page_config(
    page_title="ML Compras Dashboard",
    page_icon="🛒",
    layout="wide",
)

# ─────────────────────────────────────────────
# CSS customizado
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #FFE600, #FFC107);
        padding: 18px 24px;
        border-radius: 12px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .main-header h1 { margin: 0; font-size: 28px; color: #333; }
    .main-header p  { margin: 0; color: #666; font-size: 13px; }
    .metric-card {
        background: #fff;
        border-radius: 10px;
        padding: 16px;
        border-left: 4px solid;
        box-shadow: 0 1px 4px rgba(0,0,0,.08);
    }
    .stDataFrame { border-radius: 10px; overflow: hidden; }
    div[data-testid="stButton"] > button {
        background: #FFE600;
        color: #333;
        font-weight: 700;
        border: 2px solid #e6cf00;
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 15px;
    }
    div[data-testid="stButton"] > button:hover {
        background: #f0d800;
        border-color: #c8b400;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Helpers: token e API
# ─────────────────────────────────────────────

def exchange_code_for_token(code: str):
    resp = requests.post(
        ML_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": ML_APP_ID,
            "client_secret": ML_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp.json() if resp.ok else None


def refresh_token():
    rt = st.session_state.get("refresh_token")
    if not rt:
        return False
    resp = requests.post(
        ML_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": ML_APP_ID,
            "client_secret": ML_SECRET,
            "refresh_token": rt,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.ok:
        data = resp.json()
        st.session_state["access_token"]  = data.get("access_token")
        st.session_state["refresh_token"] = data.get("refresh_token")
        return True
    return False


def ml_get(path, params=None):
    token = st.session_state.get("access_token", "")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{ML_API_BASE}{path}", headers=headers, params=params or {})
    if resp.status_code == 401:
        if refresh_token():
            headers["Authorization"] = f"Bearer {st.session_state['access_token']}"
            resp = requests.get(f"{ML_API_BASE}{path}", headers=headers, params=params or {})
    return resp


def get_seller_id():
    resp = ml_get("/users/me")
    return resp.json().get("id") if resp.ok else None


def fetch_orders(seller_id):
    all_orders = []
    debug_info = {}
    for status in ["ready_to_ship", "payment_done", "paid", "handling"]:
        offset, limit = 0, 50
        resp = ml_get("/orders/search", {
            "seller": seller_id,
            "order.status": status,
            "limit": limit,
            "offset": offset,
            "sort": "date_desc",
        })
        debug_info[status] = {"status_code": resp.status_code, "body": resp.json()}
        if not resp.ok:
            continue
        data    = resp.json()
        results = data.get("results", [])
        all_orders.extend(results)
        total  = data.get("paging", {}).get("total", 0)
        offset += limit
        while offset < total and results:
            resp = ml_get("/orders/search", {
                "seller": seller_id,
                "order.status": status,
                "limit": limit,
                "offset": offset,
            })
            if not resp.ok:
                break
            data    = resp.json()
            results = data.get("results", [])
            all_orders.extend(results)
            total  = data.get("paging", {}).get("total", 0)
            offset += limit
    # Guarda debug na sessão
    st.session_state["_debug"] = debug_info
    return all_orders


def aggregate(orders):
    agg = defaultdict(lambda: {
        "Produto": "", "Variação": "", "SKU": "",
        "item_id": "", "variation_id": None,
        "Pedidos": 0, "Unidades": 0,
    })
    for order in orders:
        for item in order.get("order_items", []):
            d  = item.get("item", {})
            vid = d.get("variation_id")
            key = (d.get("id", ""), vid or "sem")
            attrs = d.get("variation_attributes", [])
            var   = ", ".join(
                f"{a['name']}: {a['value_name']}"
                for a in attrs if a.get("value_name")
            ) or "Padrão"

            agg[key]["Produto"]      = d.get("title", "")
            agg[key]["Variação"]     = var
            agg[key]["SKU"]          = d.get("seller_sku") or ""
            agg[key]["item_id"]      = d.get("id", "")
            agg[key]["variation_id"] = vid
            agg[key]["Pedidos"]     += 1
            agg[key]["Unidades"]    += item.get("quantity", 0)

    return sorted(agg.values(), key=lambda x: x["Unidades"], reverse=True)


# ─────────────────────────────────────────────
# Configuração de caixas (persistência em arquivo)
# ─────────────────────────────────────────────

def load_boxes():
    if os.path.exists(BOXES_FILE):
        with open(BOXES_FILE) as f:
            return json.load(f)
    return {}


def save_boxes(config: dict):
    existing = load_boxes()
    existing.update(config)
    with open(BOXES_FILE, "w") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# OAuth: captura o code na URL
# ─────────────────────────────────────────────

params = st.query_params
if "code" in params and "access_token" not in st.session_state:
    with st.spinner("Conectando ao Mercado Livre..."):
        data = exchange_code_for_token(params["code"])
    if data and data.get("access_token"):
        st.session_state["access_token"]  = data["access_token"]
        st.session_state["refresh_token"] = data.get("refresh_token", "")
        st.query_params.clear()
        st.rerun()
    else:
        st.error(f"Erro ao obter token: {data}")
        st.stop()

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────

st.markdown("""
<div class="main-header">
  <div>
    <h1>🛒 ML Compras</h1>
    <p>Dashboard de reposição de estoque — Mercado Livre</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# TELA DE LOGIN
# ─────────────────────────────────────────────

if "access_token" not in st.session_state:
    st.markdown("### 🔐 Conecte sua conta")
    st.markdown("Clique no botão abaixo para autorizar o acesso aos seus pedidos.")

    auth_url = (
        f"{ML_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={ML_APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    st.link_button("🛒  Entrar com Mercado Livre", auth_url, use_container_width=False)
    st.stop()

# ─────────────────────────────────────────────
# DASHBOARD PRINCIPAL
# ─────────────────────────────────────────────

col_title, col_btn = st.columns([6, 1])
with col_btn:
    if st.button("↻ Atualizar"):
        st.cache_data.clear()
    if st.button("Sair", type="secondary"):
        del st.session_state["access_token"]
        st.rerun()

def get_data():
    sid = get_seller_id()
    if not sid:
        return None, [], {}
    orders = fetch_orders(sid)
    items  = aggregate(orders)
    return len(orders), items, st.session_state.get("_debug", {})

total_orders, items, debug = get_data()

if total_orders is None:
    st.error("Não foi possível conectar. Token inválido — faça login novamente.")
    if st.button("Fazer login novamente"):
        del st.session_state["access_token"]
        st.rerun()
    st.stop()

# Cards de resumo
total_units = sum(i["Unidades"] for i in items)
c1, c2, c3 = st.columns(3)
c1.metric("📦 Pedidos a enviar",   total_orders)
c2.metric("🏷️ Produtos distintos", len(items))
c3.metric("📊 Total de unidades",  total_units)

# Debug temporário — mostra resposta da API
if total_orders == 0 and debug:
    with st.expander("🔍 Diagnóstico da API (remover depois)"):
        for status, info in debug.items():
            st.write(f"**{status}** → HTTP {info['status_code']}")
            st.json(info["body"])

st.divider()

# ─────────────────────────────────────────────
# TABELA EDITÁVEL
# ─────────────────────────────────────────────

st.subheader("Produtos a repor")
st.caption("Preencha a coluna **Un./Caixa** com quantas unidades vêm em cada caixa. O cálculo é automático.")

boxes_cfg = load_boxes()

# Monta lista de linhas
rows = []
for item in items:
    key = f"{item['item_id']}_{item['variation_id'] or 'sem'}"
    un_caixa = int(boxes_cfg.get(key, 0)) or None
    rows.append({
        "Produto":    item["Produto"],
        "Variação":   item["Variação"],
        "SKU":        item["SKU"],
        "Pedidos":    item["Pedidos"],
        "Unidades":   item["Unidades"],
        "Un./Caixa":  un_caixa or 0,
        "_key":       key,
    })

import pandas as pd

COLS = ["Produto", "Variacao", "SKU", "Pedidos", "Unidades", "Un./Caixa"]

# Renomeia chave com acento para evitar KeyError em algumas versões do pandas
for r in rows:
    r["Variacao"] = r.pop("Variação")

df = pd.DataFrame(rows, columns=["Produto", "Variacao", "SKU", "Pedidos", "Unidades", "Un./Caixa", "_key"]) \
    if rows else pd.DataFrame(columns=["Produto", "Variacao", "SKU", "Pedidos", "Unidades", "Un./Caixa", "_key"])

if df.empty:
    st.info("✅ Nenhum pedido pendente para enviar no momento.")
    st.stop()

edited = st.data_editor(
    df[["Produto", "Variacao", "SKU", "Pedidos", "Unidades", "Un./Caixa"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Produto":   st.column_config.TextColumn("Produto", width="large", disabled=True),
        "Variacao":  st.column_config.TextColumn("Variação", disabled=True),
        "SKU":       st.column_config.TextColumn("SKU", disabled=True),
        "Pedidos":   st.column_config.NumberColumn("Pedidos", disabled=True),
        "Unidades":  st.column_config.NumberColumn("Unidades", disabled=True),
        "Un./Caixa": st.column_config.NumberColumn("Un./Caixa", min_value=0, step=1,
                                                    help="Quantas unidades vêm por caixa?"),
    },
    num_rows="fixed",
    key="tabela_produtos",
)

# Salva alterações nas caixas
new_boxes = {}
for i, row in edited.iterrows():
    key = df.at[i, "_key"]
    val = int(row["Un./Caixa"] or 0)
    if val > 0:
        new_boxes[key] = val
if new_boxes:
    save_boxes(new_boxes)

# ─────────────────────────────────────────────
# TABELA DE RESULTADO (cálculo de caixas)
# ─────────────────────────────────────────────

st.divider()
st.subheader("📋 Resumo de compras")

resultado = []
for i, row in edited.iterrows():
    un_caixa = int(row["Un./Caixa"] or 0)
    unidades = int(row["Unidades"])
    if un_caixa > 0:
        caixas   = math.ceil(unidades / un_caixa)
        inteiras = unidades // un_caixa
        resto    = unidades % un_caixa
        detalhe  = f"{inteiras} cx completa(s)" + (f" + {resto} avulsas" if resto else " ✓ exato")
        resultado.append({
            "Produto":        row["Produto"],
            "Variação":       row["Variação"],
            "Unidades":       unidades,
            "Un./Caixa":      un_caixa,
            "Caixas a comprar": caixas,
            "Detalhe":        detalhe,
        })

if resultado:
    df_res = pd.DataFrame(resultado)
    st.dataframe(
        df_res,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Produto":          st.column_config.TextColumn(width="large"),
            "Caixas a comprar": st.column_config.NumberColumn(width="small"),
        }
    )
else:
    st.info("Preencha a coluna **Un./Caixa** na tabela acima para ver o resumo de compras.")
