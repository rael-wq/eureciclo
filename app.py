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
    
    # FATIAMENTO CIRÚRGICO DA PLANILHA (Mantido para não dar erro)
    df = conn.read(
        worksheet="NOME_DA_SUA_ABA", 
        skiprows=4, 
        usecols=list(range(11, 21))
    )
    
    df.columns = df.columns.str.strip()
    
    if 'SKU' in df.columns:
        df = df.dropna(subset=['SKU'])
    else:
        st.error("Erro Crítico: A coluna 'SKU' não foi encontrada. Verifique o número de linhas vazias no topo da planilha.")
        st.stop()
    
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
# 4. BARRA LATERAL (CONTROLES)
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

# ==========================================
# 5. TABELA DE DETALHAMENTO
# ==========================================
st.title("📊 Dashboard de Demanda de Estoque")
st.divider()
st.subheader("Detalhamento por Item")

# Exibe o DataFrame limpo diretamente, sem filtros ou colunas percentuais
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)
