import streamlit as st
import requests
from datetime import datetime, timezone

st.set_page_config(page_title="Painel ML", page_icon="🛒", layout="wide")

st.markdown("""
<style>
/* ── Fundo geral escuro ── */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #0d0d0d !important;
}
.block-container {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    max-width: 100% !important;
    background-color: #0d0d0d !important;
}
header[data-testid="stHeader"] { display: none; }
section[data-testid="stSidebar"] { display: none; }

/* ── Textos nativos ── */
.stApp p, .stApp label, .stApp span, .stApp div { color: #e0e0e0; }

/* ── Selectbox e inputs ── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextInput"] > div > div > input {
    background-color: #1e1e1e !important;
    border: 1px solid #333 !important;
    color: #f0f0f0 !important;
    border-radius: 8px !important;
}
[data-testid="stSelectbox"] > div > div > div { color: #f0f0f0 !important; }
[data-testid="stSelectbox"] svg { fill: #FFE600 !important; }
/* Dropdown popover e lista de itens */
div[data-baseweb="popover"],
div[data-baseweb="menu"] {
    background-color: #1e1e1e !important;
    border: 1px solid #333 !important;
}
div[data-baseweb="popover"] ul,
div[data-baseweb="menu"] ul { background-color: #1e1e1e !important; }
div[data-baseweb="popover"] li,
div[data-baseweb="menu"] li { background-color: #1e1e1e !important; color: #f0f0f0 !important; }
div[data-baseweb="popover"] li:hover,
div[data-baseweb="menu"] li:hover { background-color: #2a2a2a !important; }
div[data-baseweb="popover"] li *,
div[data-baseweb="menu"] li * { color: #f0f0f0 !important; }
ul[data-testid="stSelectboxVirtualDropdown"] {
    background-color: #1e1e1e !important;
    border: 1px solid #333 !important;
}
ul[data-testid="stSelectboxVirtualDropdown"] li { background-color: #1e1e1e !important; }
ul[data-testid="stSelectboxVirtualDropdown"] li:hover { background-color: #2a2a2a !important; }
ul[data-testid="stSelectboxVirtualDropdown"] li span,
ul[data-testid="stSelectboxVirtualDropdown"] li div,
ul[data-testid="stSelectboxVirtualDropdown"] li p { color: #f0f0f0 !important; }

/* ── Botão Sair ── */
[data-testid="stButton"] > button {
    background-color: #1e1e1e !important;
    color: #FFE600 !important;
    border: 1px solid #FFE600 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
[data-testid="stButton"] > button:hover {
    background-color: #FFE600 !important;
    color: #0d0d0d !important;
}

/* ── Mensagens ── */
.stSuccess { background-color: #0f2a0f !important; color: #4caf50 !important; border: 1px solid #2e7d32 !important; }

/* ── Tabela ── */
.ml-table {
    width: 100%; border-collapse: collapse; font-size: 13px;
    background: #1a1a1a; border-radius: 12px; overflow: hidden; border: 1px solid #2e2e2e;
}
.ml-table th {
    padding: 11px 14px; text-align: left; font-weight: 600;
    font-size: 12px; color: #888; background: #111; border-bottom: 1px solid #2e2e2e;
}
.ml-table td {
    padding: 11px 14px; border-bottom: 1px solid #222;
    vertical-align: middle; color: #e0e0e0;
}
.ml-table tr:last-child td { border-bottom: none; }
.ml-table tr:hover td { background: #222; }
.tc { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }

/* ── Badges ── */
.badge { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; }
.b-active  { background: #0f2a0f; color: #66bb6a; }
.b-paused  { background: #2a1f00; color: #ffa726; }
.b-closed  { background: #2a0a0a; color: #ef5350; }
.b-nosales { background: #2a0a0a; color: #ef5350; }
.b-sales   { background: #0f2a0f; color: #66bb6a; }
.b-old     { background: #2a1f00; color: #ffa726; }
a.ver { color: #FFE600; text-decoration: none; font-size: 12px; }
a.ver:hover { color: #fff; }

/* ── Login ── */
.login-box {
    max-width: 420px; margin: 6rem auto; background: #1a1a1a;
    border-radius: 16px; border: 1px solid #2e2e2e; padding: 2.5rem; text-align: center;
}
.login-box h2 { font-size: 20px; font-weight: 700; margin-bottom: 8px; color: #f0f0f0; }
.login-box p  { font-size: 13px; color: #888; margin-bottom: 2rem; }
.btn-login {
    display: inline-block; background: #FFE600; color: #0d0d0d;
    font-weight: 700; font-size: 15px; padding: 12px 32px;
    border-radius: 8px; text-decoration: none; border: none; cursor: pointer;
}
.btn-login:hover { background: #e6cf00; }

/* ── Título da seção ── */
.section-title {
    font-size: 17px; font-weight: 700; color: #f0f0f0;
    padding: 1rem 0 0.5rem;
    border-bottom: 2px solid #FFE600;
    margin-bottom: 1rem;
    display: inline-block;
}
</style>
""", unsafe_allow_html=True)

CLIENT_ID     = st.secrets["ML_CLIENT_ID"]
CLIENT_SECRET = st.secrets["ML_CLIENT_SECRET"]
REDIRECT_URI  = st.secrets["ML_REDIRECT_URI"]

# ── Helpers ────────────────────────────────────────────────
def age_days(date_str):
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except:
        return 0

def fmt_age(days):
    if days < 30:  return f"{days} dias"
    if days < 365: return f"{days // 30} meses"
    return f"{days / 365:.1f} anos"

def fmt_price(p):
    return f"R$ {p:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def status_label(s):
    return {"active": "ativo", "paused": "pausado", "closed": "fechado"}.get(s, s)

def status_badge(s):
    cls = {"active": "b-active", "paused": "b-paused", "closed": "b-closed"}.get(s, "b-paused")
    return f'<span class="badge {cls}">{status_label(s)}</span>'

def sales_badge(n):
    return f'<span class="badge {"b-nosales" if n == 0 else "b-sales"}">{n}</span>'

def age_badge(days):
    if days > 365:
        return f'<span class="badge b-old">{fmt_age(days)}</span>'
    return fmt_age(days)

SORT_OPTIONS = ["Mais vendidos", "Mais recentes", "Mais antigos", "Maior preço", "Menor preço"]

def sort_data(data, criterion):
    if criterion == "Mais vendidos":
        return sorted(data, key=lambda l: l.get("sold_quantity") or 0, reverse=True)
    elif criterion == "Mais recentes":
        return sorted(data, key=lambda l: l.get("date_created", ""), reverse=True)
    elif criterion == "Mais antigos":
        return sorted(data, key=lambda l: l.get("date_created", ""))
    elif criterion == "Maior preço":
        return sorted(data, key=lambda l: l.get("price") or 0, reverse=True)
    elif criterion == "Menor preço":
        return sorted(data, key=lambda l: l.get("price") or 0)
    return data

def exchange_code(code):
    r = requests.post("https://api.mercadolibre.com/oauth/token", data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    }, timeout=15)
    r.raise_for_status()
    return r.json()

def refresh_token_fn(refresh_token):
    r = requests.post("https://api.mercadolibre.com/oauth/token", data={
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token
    }, timeout=15)
    r.raise_for_status()
    return r.json()

@st.cache_data(show_spinner=False)
def load_listings(token):
    headers = {"Authorization": f"Bearer {token}"}
    me = requests.get("https://api.mercadolibre.com/users/me", headers=headers, timeout=15)
    me.raise_for_status()
    user_id = me.json()["id"]
    nickname = me.json().get("nickname", str(user_id))
    all_ids = []
    offset = 0
    while True:
        r = requests.get(
            f"https://api.mercadolibre.com/users/{user_id}/items/search?limit=50&offset={offset}",
            headers=headers, timeout=15
        )
        ids = r.json().get("results", [])
        all_ids.extend(ids)
        if len(ids) < 50: break
        offset += 50
    listings = []
    for i in range(0, len(all_ids), 20):
        chunk = all_ids[i:i+20]
        r = requests.get(
            f"https://api.mercadolibre.com/items?ids={','.join(chunk)}"
            f"&attributes=id,title,status,price,sold_quantity,date_created,permalink",
            headers=headers, timeout=15
        )
        for item in r.json():
            if item.get("code") == 200 and item.get("body"):
                listings.append(item["body"])
    return nickname, listings

def render_table(data):
    if not data:
        st.success("Nenhum anúncio nesta categoria!")
        return
    rows_html = ""
    for l in data:
        age = age_days(l.get("date_created", ""))
        title = l.get("title", "").replace('"', '&quot;').replace('<', '&lt;')
        rows_html += f"""<tr>
          <td><span class="tc" title="{title}">{title}</span></td>
          <td>{status_badge(l.get('status', ''))}</td>
          <td>{sales_badge(l.get('sold_quantity') or 0)}</td>
          <td>{fmt_price(l.get('price') or 0)}</td>
          <td>{age_badge(age)}</td>
          <td><a class="ver" href="{l.get('permalink', '#')}" target="_blank">ver ↗</a></td>
        </tr>"""
    st.markdown(f"""
    <table class="ml-table">
      <thead><tr><th>Título</th><th>Status</th><th>Vendas</th><th>Preço</th><th>Idade</th><th>Link</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table><br>
    """, unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────
st.markdown("""
<div style='background:#FFE600;padding:0.85rem 1.5rem;display:flex;align-items:center;gap:12px'>
  <div style='background:#0d0d0d;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center'>
    <span style='color:#FFE600;font-size:16px'>✔</span>
  </div>
  <span style='font-size:19px;font-weight:700;color:#0d0d0d'>Painel de Anúncios</span>
  <span style='font-size:13px;color:#555'>Mercado Livre Analytics</span>
</div>
""", unsafe_allow_html=True)

# ── OAuth flow ─────────────────────────────────────────────
params = st.query_params

if "code" in params and "access_token" not in st.session_state:
    with st.spinner("Autenticando..."):
        try:
            token_data = exchange_code(params["code"])
            st.session_state["access_token"]  = token_data["access_token"]
            st.session_state["refresh_token"] = token_data.get("refresh_token", "")
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Erro na autenticação: {e}")
            st.stop()

if "access_token" not in st.session_state:
    auth_url = (
        f"https://auth.mercadolivre.com.br/authorization"
        f"?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    )
    st.markdown(f"""
    <div class="login-box">
      <div style='font-size:48px;margin-bottom:1rem'>🛒</div>
      <h2>Painel de Anúncios</h2>
      <p>Faça login com sua conta do Mercado Livre<br>para visualizar e analisar seus anúncios.</p>
      <a href="{auth_url}" class="btn-login" target="_self">🔑 Entrar com Mercado Livre</a>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Renovar token se necessário
access_token = st.session_state["access_token"]
test = requests.get(
    "https://api.mercadolibre.com/users/me",
    headers={"Authorization": f"Bearer {access_token}"}, timeout=10
)
if test.status_code == 401 and st.session_state.get("refresh_token"):
    try:
        new_tokens = refresh_token_fn(st.session_state["refresh_token"])
        st.session_state["access_token"]  = new_tokens["access_token"]
        st.session_state["refresh_token"] = new_tokens.get("refresh_token", st.session_state["refresh_token"])
        access_token = st.session_state["access_token"]
        st.cache_data.clear()
    except:
        del st.session_state["access_token"]
        st.rerun()

# ── Carregar dados ─────────────────────────────────────────
with st.spinner("Carregando seus anúncios..."):
    try:
        nickname, listings = load_listings(access_token)
    except Exception as e:
        st.error(f"Erro: {e}")
        st.stop()

total    = len(listings)
no_sales = [l for l in listings if (l.get("sold_quantity") or 0) == 0]
w_sales  = [l for l in listings if (l.get("sold_quantity") or 0) > 0]
active   = [l for l in listings if l.get("status") == "active"]
paused   = [l for l in listings if l.get("status") == "paused"]
closed   = [l for l in listings if l.get("status") == "closed"]
now_str  = datetime.now().strftime("%d/%m/%Y %H:%M")

# View selecionada via query param (definida pelos cards clicáveis)
current_view = st.query_params.get("view", "todos")

# Barra de usuário + botão sair
col_a, col_b = st.columns([6, 1])
with col_a:
    st.markdown(
        f"<div style='font-size:13px;color:#aaa;padding:0.4rem 0;background:#111;"
        f"border-bottom:1px solid #2e2e2e;padding-left:1rem'>"
        f"Conectado como <strong style='color:#FFE600'>{nickname}</strong> · {now_str}</div>",
        unsafe_allow_html=True
    )
with col_b:
    if st.button("🚪 Sair"):
        for k in ["access_token", "refresh_token"]:
            st.session_state.pop(k, None)
        st.cache_data.clear()
        st.query_params.clear()
        st.rerun()

# ── Cards clicáveis de métricas ────────────────────────────
def card_style(view_key):
    if current_view == view_key:
        return "background:#1e1c00;border:2px solid #FFE600;border-radius:12px;padding:1.1rem 1rem;cursor:pointer;transition:all 0.15s;user-select:none;"
    return "background:#1a1a1a;border:1px solid #2e2e2e;border-radius:12px;padding:1.1rem 1rem;cursor:pointer;transition:all 0.15s;user-select:none;"

st.components.v1.html(f"""
<style>
  body {{ margin:0; padding:0; background:#0d0d0d; }}
  .mgrid {{ display:grid; grid-template-columns:repeat(6,1fr); gap:12px; padding:12px 0 4px 0; }}
  .mcard {{ border-radius:12px; padding:1.1rem 1rem; cursor:pointer; transition:all 0.15s; user-select:none; }}
  .mcard:hover {{ filter:brightness(1.15); }}
  .mlabel {{ font-size:12px; color:#ccc; margin-bottom:6px; font-family:sans-serif; }}
  .mvalue {{ font-size:30px; font-weight:700; font-family:sans-serif; }}
  .c-yellow {{ color:#FFE600; }}
  .c-red    {{ color:#ef5350; }}
  .c-green  {{ color:#66bb6a; }}
  .c-orange {{ color:#ffa726; }}
  .inactive {{ background:#1a1a1a; border:1px solid #2e2e2e; }}
  .active   {{ background:#1e1c00; border:2px solid #FFE600; }}
</style>
<div class="mgrid">
  <div class="mcard {'active' if current_view == 'todos' else 'inactive'}" onclick="setView('todos')">
    <div class="mlabel">Total de anúncios</div>
    <div class="mvalue c-yellow">{total}</div>
  </div>
  <div class="mcard {'active' if current_view == 'sem_venda' else 'inactive'}" onclick="setView('sem_venda')">
    <div class="mlabel">Sem nenhuma venda</div>
    <div class="mvalue c-red">{len(no_sales)}</div>
  </div>
  <div class="mcard {'active' if current_view == 'com_venda' else 'inactive'}" onclick="setView('com_venda')">
    <div class="mlabel">Com vendas</div>
    <div class="mvalue c-green">{len(w_sales)}</div>
  </div>
  <div class="mcard {'active' if current_view == 'ativos' else 'inactive'}" onclick="setView('ativos')">
    <div class="mlabel">Ativos</div>
    <div class="mvalue c-green">{len(active)}</div>
  </div>
  <div class="mcard {'active' if current_view == 'pausados' else 'inactive'}" onclick="setView('pausados')">
    <div class="mlabel">Pausados</div>
    <div class="mvalue c-orange">{len(paused)}</div>
  </div>
  <div class="mcard {'active' if current_view == 'fechados' else 'inactive'}" onclick="setView('fechados')">
    <div class="mlabel">Fechados</div>
    <div class="mvalue c-red">{len(closed)}</div>
  </div>
</div>
<script>
function setView(v) {{
  try {{
    var url = new URL(window.top.location.href);
    url.searchParams.set('view', v);
    window.top.location.href = url.toString();
  }} catch(e) {{
    try {{
      var a = document.createElement('a');
      a.href = window.top.location.pathname + '?view=' + v;
      a.target = '_top';
      document.body.appendChild(a);
      a.click();
    }} catch(e2) {{
      window.location.href = '?view=' + v;
    }}
  }}
}}
</script>
""", height=130)

# ── Gráficos ───────────────────────────────────────────────
age_bins = [0, 0, 0, 0]
for l in listings:
    d = age_days(l.get("date_created", ""))
    if d < 30:    age_bins[0] += 1
    elif d < 180: age_bins[1] += 1
    elif d < 365: age_bins[2] += 1
    else:         age_bins[3] += 1

st.components.v1.html(f"""
<div style="background:#0d0d0d;padding:4px 0 8px 0">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
  <div style="background:#1a1a1a;border-radius:12px;border:1px solid #2e2e2e;padding:1.25rem">
    <div style="font-size:13px;color:#888;font-weight:600;margin-bottom:1rem">Status dos anúncios</div>
    <canvas id="cStatus" style="max-height:190px"></canvas>
  </div>
  <div style="background:#1a1a1a;border-radius:12px;border:1px solid #2e2e2e;padding:1.25rem">
    <div style="font-size:13px;color:#888;font-weight:600;margin-bottom:1rem">Anúncios por idade</div>
    <canvas id="cAge" style="max-height:190px"></canvas>
  </div>
</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
Chart.defaults.color = '#888';
new Chart(document.getElementById('cStatus'), {{
  type: 'doughnut',
  data: {{ labels: ['Ativos','Pausados','Fechados'],
    datasets: [{{ data: [{len(active)},{len(paused)},{len(closed)}],
      backgroundColor: ['#66bb6a','#ffa726','#ef5350'], borderWidth: 0 }}] }},
  options: {{ responsive: true, maintainAspectRatio: true,
    plugins: {{ legend: {{ position: 'right', labels: {{ color:'#bbb', font:{{size:12}}, boxWidth:12 }} }} }} }}
}});
new Chart(document.getElementById('cAge'), {{
  type: 'bar',
  data: {{ labels: ['< 1 mês','1-6 meses','6-12 meses','> 1 ano'],
    datasets: [{{ data: {age_bins},
      backgroundColor: ['#FFE600','#c9b800','#9e8f00','#6e6300'], borderRadius: 6 }}] }},
  options: {{ responsive: true, maintainAspectRatio: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ beginAtZero:true, ticks:{{stepSize:1,font:{{size:11}},color:'#888'}}, grid:{{color:'#222'}} }},
      x: {{ ticks:{{font:{{size:11}},color:'#888'}}, grid:{{color:'#222'}} }}
    }}
  }}
}});
</script>
""", height=275)

# ── Tabela da view selecionada ─────────────────────────────
view_config = {
    "todos":     ("📋 Todos os anúncios",       listings,  0),
    "sem_venda": ("🔴 Sem nenhuma venda",        no_sales,  2),
    "com_venda": ("🟢 Com vendas",               w_sales,   0),
    "ativos":    ("✅ Ativos",                   active,    0),
    "pausados":  ("⏸️ Pausados",                paused,    0),
    "fechados":  ("🚫 Fechados",                 closed,    1),
}

title, dados_view, default_sort = view_config.get(current_view, view_config["todos"])

st.markdown(f"<div class='section-title'>{title} &nbsp;({len(dados_view)})</div>", unsafe_allow_html=True)

# Controles: busca + ordenação (+ filtros extras por view)
if current_view == "todos":
    c1, c2, c3 = st.columns([2, 3, 2])
    with c1:
        filtro = st.selectbox("Status", ["Todos", "Ativos", "Pausados", "Fechados"],
                              label_visibility="collapsed", key="filtro_status")
        if filtro == "Ativos":     dados_view = active
        elif filtro == "Pausados": dados_view = paused
        elif filtro == "Fechados": dados_view = closed
    with c2:
        busca = st.text_input("Buscar", placeholder="🔍  Buscar por título...",
                              label_visibility="collapsed", key="busca_todos")
        if busca:
            dados_view = [l for l in dados_view if busca.lower() in l.get("title","").lower()]
    with c3:
        ordem = st.selectbox("Ordenar", SORT_OPTIONS, index=default_sort,
                             label_visibility="collapsed", key="ord_todos")

elif current_view == "sem_venda":
    # Filtro de período exclusivo para anúncios sem venda
    PERIODO_OPTS = {
        "⏱️ Todos os períodos": 0,
        "📅 Mais de 15 dias":   15,
        "📅 Mais de 30 dias":   30,
        "📅 Mais de 60 dias":   60,
        "📅 Mais de 90 dias":   90,
    }
    c1, c2, c3 = st.columns([2, 3, 2])
    with c1:
        periodo_label = st.selectbox(
            "Período sem venda", list(PERIODO_OPTS.keys()),
            label_visibility="collapsed", key="filtro_periodo"
        )
        min_dias = PERIODO_OPTS[periodo_label]
        if min_dias > 0:
            dados_view = [l for l in dados_view if age_days(l.get("date_created","")) >= min_dias]
    with c2:
        busca = st.text_input("Buscar", placeholder="🔍  Buscar por título...",
                              label_visibility="collapsed", key="busca_view")
        if busca:
            dados_view = [l for l in dados_view if busca.lower() in l.get("title","").lower()]
    with c3:
        ordem = st.selectbox("Ordenar", SORT_OPTIONS, index=default_sort,
                             label_visibility="collapsed", key="ord_view")

    # Resumo do filtro aplicado
    if min_dias > 0:
        st.markdown(
            f"<div style='font-size:12px;color:#ffa726;padding:4px 0 8px'>"
            f"🔎 Mostrando {len(dados_view)} anúncio(s) com mais de {min_dias} dias sem nenhuma venda.</div>",
            unsafe_allow_html=True
        )

else:
    c1, c2 = st.columns([4, 1])
    with c1:
        busca = st.text_input("Buscar", placeholder="🔍  Buscar por título...",
                              label_visibility="collapsed", key="busca_view")
        if busca:
            dados_view = [l for l in dados_view if busca.lower() in l.get("title","").lower()]
    with c2:
        ordem = st.selectbox("Ordenar", SORT_OPTIONS, index=default_sort,
                             label_visibility="collapsed", key="ord_view")

render_table(sort_data(dados_view, ordem))

st.markdown(
    f"<div style='text-align:center;font-size:12px;color:#444;padding:1.5rem'>Painel ML · {now_str}</div>",
    unsafe_allow_html=True
)
