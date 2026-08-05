import streamlit as st
import pandas as pd
from streamlit_oauth import OAuth2Component
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Dashboard de Demanda - Nhecotech",
    page_icon="📊",
    layout="wide"
)

# ==========================================
# 2. CONFIGURAÇÃO DO GOOGLE OAUTH
# ==========================================
CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI = st.secrets.get("REDIRECT_URI", "https://seu-app.streamlit.app/")
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

oauth2 = OAuth2Component(
    CLIENT_ID, 
    CLIENT_SECRET, 
    AUTHORIZE_URL, 
    TOKEN_URL, 
    TOKEN_URL, 
    TOKEN_URL
)

if "user_token" not in st.session_state:
    st.title("🔒 Acesso Restrito")
    st.write("Por favor, faça login com sua conta corporativa para acessar o dashboard.")
    
    result = oauth2.authorize_button(
        name="Continuar com Google",
        icon="https://www.google.com/favicon.ico",
        redirect_uri=REDIRECT_URI,
        scope="openid email profile",
        key="google_login",
        extras_params={"prompt": "consent", "access_type": "offline"}
    )
    
    if result:
        st.session_state["user_token"] = result["token"]
        st.rerun()
    st.stop()

token_info = st.session_state["user_token"]
id_token = token_info.get("id_token")

import jwt 
try:
    user_info = jwt.decode(id_token, options={"verify_signature": False})
    user_email = user_info.get("email", "")
    
    if not user_email.endswith("@nhecotech.com"):
        st.error(f"Acesso negado. O email {user_email} não pertence ao domínio @nhecotech.com.")
        if st.button("Sair"):
            del st.session_state["user_token"]
            st.rerun()
        st.stop()
except Exception as e:
    st.error("Erro ao validar credenciais. Faça login novamente.")
    st.stop()

# ==========================================
# 3. CONEXÃO E LEITURA DE DADOS (GOOGLE SHEETS)
# ==========================================
@st.cache_data(ttl=300)
def carregar_dados():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # FATIAMENTO CIRÚRGICO DA PLANILHA:
    # skiprows=3 -> Ignora as linhas 1, 2 e 3 (cabeçalho sujo)
    # usecols=list(range(11, 21)) -> Pega apenas da coluna 12 (SKU) até a 21 (DEMANDA TOTAL)
    df = conn.read(
        worksheet="[Demanda] Visão Gerencial", 
        skiprows=3, 
        usecols=list(range(11, 21))
    )
    
    # Remove linhas vazias no final da planilha (se a coluna SKU estiver nula, a linha não serve)
    df = df.dropna(subset=['SKU'])
    
    colunas_demanda = ["Compensada", "Em Aberto", "Projetada"]
    
    # Limpeza de dados numéricos
    for col in colunas_demanda:
        if col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    return df

df = carregar_dados()

# ==========================================
# 4. BARRA LATERAL (FILTROS E CONTROLES)
# ==========================================
st.sidebar.image("https://via.placeholder.com/150", caption="Nhecotech") 
st.sidebar.write(f"Bem-vindo, **{user_info.get('name', 'Usuário')}**")

if st.sidebar.button("🚪 Sair"):
    del st.session_state["user_token"]
    st.rerun()

st.sidebar.divider()

if st.sidebar.button("🔄 Atualizar Dados da Planilha"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Filtros de Visão")

colunas_demanda = ["Compensada", "Em Aberto", "Projetada"]
demandas_selecionadas = st.sidebar.multiselect(
    "Selecione as Demandas para exibir na tabela:",
    options=colunas_demanda,
    default=colunas_demanda
)

# ==========================================
# 5. CÁLCULO DE KPIS GLOBAIS E INDICADORES
# ==========================================
st.title("📊 Dashboard de Demanda de Estoque")

vol_compensada = df['Compensada'].sum() if 'Compensada' in df.columns else 0
vol_em_aberto = df['Em Aberto'].sum() if 'Em Aberto' in df.columns else 0
vol_projetada = df['Projetada'].sum() if 'Projetada' in df.columns else 0

demanda_total = vol_compensada + vol_em_aberto + vol_projetada

perc_em_aberto = (vol_em_aberto / demanda_total) if demanda_total > 0 else 0
perc_projetada = (vol_projetada / demanda_total) if demanda_total > 0 else 0

st.subheader("Resumo da Demanda Total")
col1, col2, col3 = st.columns(3)

col1.metric("Demanda Total", f"{demanda_total:,.0f}")
col2.metric("% Em Aberto", f"{perc_em_aberto * 100:.1f}%")
col3.metric("% Projetada", f"{perc_projetada * 100:.1f}%")

# ==========================================
# 6. TABELA DE DETALHAMENTO INTERATIVA
# ==========================================
st.divider()
st.subheader("Detalhamento por Item")

if 'Em Aberto' in df.columns:
    df['% do Total (Em Aberto)'] = df['Em Aberto'] / demanda_total if demanda_total > 0 else 0
if 'Projetada' in df.columns:
    df['% do Total (Projetada)'] = df['Projetada'] / demanda_total if demanda_total > 0 else 0

colunas_identificacao = [
    col for col in df.columns 
    if col not in colunas_demanda and col not in ['% do Total (Em Aberto)', '% do Total (Projetada)']
]

colunas_para_exibir = colunas_identificacao + demandas_selecionadas

if 'Em Aberto' in demandas_selecionadas and '% do Total (Em Aberto)' in df.columns:
    colunas_para_exibir.append('% do Total (Em Aberto)')
if 'Projetada' in demandas_selecionadas and '% do Total (Projetada)' in df.columns:
    colunas_para_exibir.append('% do Total (Projetada)')

colunas_reais_seguras = [col for col in colunas_para_exibir if col in df.columns]

df_exibicao = df[colunas_reais_seguras]

st.dataframe(
    df_exibicao,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Compensada": st.column_config.NumberColumn("Compensada", format="%.0f"),
        "Em Aberto": st.column_config.NumberColumn("Em Aberto", format="%.0f"),
        "Projetada": st.column_config.NumberColumn("Projetada", format="%.0f"),
        "% do Total (Em Aberto)": st.column_config.NumberColumn(
            "% do Total (Em Aberto)", 
            format="%.2f%%"
        ),
        "% do Total (Projetada)": st.column_config.NumberColumn(
            "% do Total (Projetada)", 
            format="%.2f%%"
        )
    }
)
