import streamlit as st
import requests
import os
import math
import json
from collections import defaultdict
from datetime import datetime, date, timezone, timedelta
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

# ─────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────
ML_APP_ID     = os.getenv("ML_APP_ID", "")
ML_SECRET     = os.getenv("ML_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("ML_REDIRECT_URI", "")
ML_AUTH_URL   = "https://auth.mercadolivre.com.br/authorization"
ML_TOKEN_URL  = "https://api.mercadolibre.com/oauth/token"
ML_API_BASE   = "https://api.mercadolibre.com"
BOXES_FILE    = "boxes_config.json"
BR_OFFSET     = timedelta(hours=-3)   # UTC-3 (Brasília)

st.set_page_config(page_title="ML Compras Dashboard", page_icon="🛒", layout="wide")

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #FFE600, #FFC107);
        padding: 18px 24px; border-radius: 12px; margin-bottom: 24px;
    }
    .main-header h1 { margin: 0; font-size: 28px; color: #333; }
    .main-header p  { margin: 0; color: #666; font-size: 13px; }
    .badge-hoje      { background:#ff4b4b; color:#fff; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:700; }
    .badge-proximos  { background:#1f77b4; color:#fff; border-radius:6px; padding:2px 8px; font-size:12px; font-weight:700; }
    div[data-testid="stButton"] > button {
        background: #FFE600; color: #333; font-weight: 700;
        border: 2px solid #e6cf00; border-radius: 8px;
        padding: 8px 20px; font-size: 14px;
    }
    div[data-testid="stButton"] > button:hover { background: #f0d800; }
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


def get_brazil_today():
    """Retorna a data de hoje no fuso de Brasília (UTC-3)."""
    return (datetime.now(timezone.utc) + BR_OFFSET).date()


def classify_order(order):
    """
    Classifica um pedido como 'hoje' ou 'proximos'.
    - 'hoje'    → date_closed ANTES de hoje (precisava ter saído ontem ou antes)
    - 'proximos' → date_closed HOJE (entrou hoje, ainda está dentro do prazo)
    """
    today = get_brazil_today()
    date_str = order.get("date_closed") or order.get("date_created", "")
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            order_date = (dt + BR_OFFSET).date()
            if order_date < today:
                return "hoje"
        except Exception:
            pass
    return "proximos"


def fetch_orders(seller_id):
    """
    Busca pedidos pagos dos últimos 60 dias e filtra apenas os
    que ainda não foram enviados (shipping.status pendente/ready).
    """
    all_orders   = []
    debug_info   = {}

    # Últimos 60 dias (cobre todos os pedidos pendentes de envio)
    date_from = (datetime.now(timezone.utc) - timedelta(days=60)).strftime(
        "%Y-%m-%dT00:00:00.000-00:00"
    )

    offset, limit = 0, 50
    fetched_raw   = 0

    while True:
        resp = ml_get("/orders/search", {
            "seller":                  seller_id,
            "order.status":            "paid",
            "order.date_created.from": date_from,
            "limit":                   limit,
            "offset":                  offset,
            "sort":                    "date_desc",
        })

        if not resp.ok:
            debug_info["error"] = {"status_code": resp.status_code, "body": resp.json()}
            break

        data    = resp.json()
        results = data.get("results", [])
        total   = data.get("paging", {}).get("total", 0)

        if offset == 0:
            debug_info["total_paid_60d"] = total

        fetched_raw += len(results)

        # Mantém apenas pedidos cujo envio ainda está pendente
        PENDING_SHIPPING = {"pending", "ready_to_ship", "handling", "to_be_agreed", None, ""}
        for order in results:
            ship_status = (order.get("shipping") or {}).get("status", "")
            if ship_status in PENDING_SHIPPING:
                all_orders.append(order)

        offset += limit
        if offset >= total or not results:
            break

    debug_info["fetched_raw"]    = fetched_raw
    debug_info["pending_orders"] = len(all_orders)
    st.session_state["_debug"]   = debug_info
    return all_orders


def aggregate(orders):
    """Agrupa por SKU/variação e separa em hoje vs próximos dias."""
    agg = defaultdict(lambda: {
        "Produto": "", "Variação": "", "SKU": "",
        "item_id": "", "variation_id": None,
        "hoje_un": 0,    "hoje_ped": 0,
        "proximos_un": 0, "proximos_ped": 0,
    })

    for order in orders:
        period = classify_order(order)
        for item in order.get("order_items", []):
            d   = item.get("item", {})
            vid = d.get("variation_id")
            key = (d.get("id", ""), vid or "sem")
            attrs = d.get("variation_attributes", [])
            var   = ", ".join(
                f"{a['name']}: {a['value_name']}"
                for a in attrs if a.get("value_name")
            ) or "Padrão"

            agg[key].update({
                "Produto":      d.get("title", ""),
                "Variação":     var,
                "SKU":          d.get("seller_sku") or "",
                "item_id":      d.get("id", ""),
                "variation_id": vid,
            })

            qty = item.get("quantity", 0)
            if period == "hoje":
                agg[key]["hoje_un"]  += qty
                agg[key]["hoje_ped"] += 1
            else:
                agg[key]["proximos_un"]  += qty
                agg[key]["proximos_ped"] += 1

    result = []
    for v in agg.values():
        v["total_un"]  = v["hoje_un"]  + v["proximos_un"]
        v["total_ped"] = v["hoje_ped"] + v["proximos_ped"]
        result.append(v)

    # Ordena: hoje primeiro, depois por total de unidades
    return sorted(result, key=lambda x: (-(x["hoje_un"]), -(x["total_un"])))


# ─────────────────────────────────────────────
# Caixas — persistência em arquivo JSON
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
# OAuth: captura code na URL
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
  <h1>🛒 ML Compras</h1>
  <p>Dashboard de reposição de estoque — Mercado Livre</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────

if "access_token" not in st.session_state:
    st.markdown("### 🔐 Conecte sua conta")
    st.markdown("Clique no botão abaixo para autorizar o acesso aos seus pedidos.")
    auth_url = (
        f"{ML_AUTH_URL}?response_type=code"
        f"&client_id={ML_APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    st.link_button("🛒  Entrar com Mercado Livre", auth_url)
    st.stop()

# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

col_title, col_btn = st.columns([6, 1])
with col_btn:
    if st.button("↻ Atualizar"):
        st.cache_data.clear()
    if st.button("Sair", type="secondary"):
        del st.session_state["access_token"]
        st.rerun()

with st.spinner("Carregando pedidos..."):
    seller_id = get_seller_id()
    if not seller_id:
        st.error("Não foi possível conectar. Token inválido — faça login novamente.")
        if st.button("Fazer login novamente"):
            del st.session_state["access_token"]
            st.rerun()
        st.stop()

    orders = fetch_orders(seller_id)
    items  = aggregate(orders)

# ─── Totais para os cards ─────────────────────
hoje_ped     = sum(i["hoje_ped"]     for i in items)
hoje_un      = sum(i["hoje_un"]      for i in items)
proximos_ped = sum(i["proximos_ped"] for i in items)
proximos_un  = sum(i["proximos_un"]  for i in items)
total_ped    = hoje_ped + proximos_ped
total_un     = hoje_un  + proximos_un

# ─── Cards de resumo ──────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("🔴 Envios de hoje",    f"{hoje_ped} pedidos",    f"{hoje_un} un.")
c2.metric("🔵 Próximos dias",     f"{proximos_ped} pedidos", f"{proximos_un} un.")
c3.metric("🏷️ SKUs distintos",   len(items))
c4.metric("📦 Total de pedidos",  total_ped, f"{total_un} un. no total")

# ─── Debug sempre visível para diagnóstico ────
if "_debug" in st.session_state:
    with st.expander("🔍 Diagnóstico da API (remover depois)", expanded=(total_ped == 0)):
        st.json(st.session_state["_debug"])

if not items:
    st.success("✅ Nenhum pedido pendente para enviar no momento.")
    st.stop()

st.divider()

# ─────────────────────────────────────────────
# TABELA POR SKU
# ─────────────────────────────────────────────

st.subheader("📦 Produtos a enviar por SKU")
st.caption("🔴 **Hoje** = pedidos antigos que precisam sair agora  |  🔵 **Próximos dias** = pedidos recentes ainda no prazo  |  Preencha **Un./Caixa** para calcular compras.")

boxes_cfg = load_boxes()

rows = []
for item in items:
    key      = f"{item['item_id']}_{item['variation_id'] or 'sem'}"
    un_caixa = int(boxes_cfg.get(key, 0))
    rows.append({
        "Produto":        item["Produto"],
        "Variacao":       item["Variação"],
        "SKU":            item["SKU"],
        "Hoje":           item["hoje_un"],
        "Proximos dias":  item["proximos_un"],
        "Total":          item["total_un"],
        "Un./Caixa":      un_caixa,
        "_key":           key,
    })

df = pd.DataFrame(rows) if rows else pd.DataFrame(
    columns=["Produto", "Variacao", "SKU", "Hoje", "Proximos dias", "Total", "Un./Caixa", "_key"]
)

edited = st.data_editor(
    df[["Produto", "Variacao", "SKU", "Hoje", "Proximos dias", "Total", "Un./Caixa"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Produto":       st.column_config.TextColumn("Produto", width="large", disabled=True),
        "Variacao":      st.column_config.TextColumn("Variação", disabled=True),
        "SKU":           st.column_config.TextColumn("SKU", disabled=True),
        "Hoje":          st.column_config.NumberColumn("🔴 Hoje (un.)", disabled=True, width="small"),
        "Proximos dias": st.column_config.NumberColumn("🔵 Próx. dias (un.)", disabled=True, width="small"),
        "Total":         st.column_config.NumberColumn("Total (un.)", disabled=True, width="small"),
        "Un./Caixa":     st.column_config.NumberColumn("Un./Caixa", min_value=0, step=1,
                                                        help="Quantas unidades vêm por caixa?"),
    },
    num_rows="fixed",
    key="tabela_produtos",
)

# Salva Un./Caixa
new_boxes = {}
for i, row in edited.iterrows():
    key = df.at[i, "_key"]
    val = int(row["Un./Caixa"] or 0)
    if val > 0:
        new_boxes[key] = val
if new_boxes:
    save_boxes(new_boxes)

# ─────────────────────────────────────────────
# RESUMO DE COMPRAS
# ─────────────────────────────────────────────

st.divider()
st.subheader("🛒 Resumo de compras")

resultado = []
for i, row in edited.iterrows():
    un_caixa = int(row["Un./Caixa"] or 0)
    total    = int(row["Total"])
    if un_caixa > 0:
        caixas   = math.ceil(total / un_caixa)
        inteiras = total // un_caixa
        resto    = total % un_caixa
        detalhe  = f"{inteiras} cx completa(s)" + (f" + {resto} avulsas" if resto else " ✓ exato")
        resultado.append({
            "Produto":          row["Produto"],
            "Variação":         row["Variacao"],
            "SKU":              row["SKU"],
            "🔴 Hoje":          int(row["Hoje"]),
            "🔵 Próx. dias":    int(row["Proximos dias"]),
            "Total un.":        total,
            "Un./Caixa":        un_caixa,
            "Caixas a comprar": caixas,
            "Detalhe":          detalhe,
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
