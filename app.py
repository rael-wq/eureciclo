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
# Carrega as credenciais do painel de Secrets
CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI = st.secrets.get("REDIRECT_URI", "https://seu-app.streamlit.app/")
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Inicializa o componente de autenticação
oauth2 = OAuth2Component(
    CLIENT_ID, 
    CLIENT_SECRET, 
    AUTHORIZE_URL, 
    TOKEN_URL, 
    TOKEN_URL, 
    TOKEN_URL
)

# Verifica se o usuário já está logado na sessão
if "user_token" not in st.session_state:
    st.title("🔒 Acesso Restrito")
    st.write("Por favor, faça login com sua conta corporativa para acessar o dashboard.")
    
    # Cria o botão de login do Google
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
    st.stop() # Interrompe a execução se não estiver logado

# Validação do domínio corporativo
token_info = st.session_state["user_token"]
id_token = token_info.get("id_token")

import jwt # Requer a biblioteca PyJWT no requirements.txt (ou decodificação manual base64)
# Como alternativa sem biblioteca extra, assumimos a validação do email via token decodificado
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
# Cache ajustado para 5 minutos (300 segundos) para otimizar velocidade
@st.cache_data(ttl=300)
def carregar_dados():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
    
    # Lista das colunas numéricas de demanda
    colunas_demanda = ["Compensada", "Em Aberto", "Projetada"]
    
    # Limpeza de dados: garante que as colunas sejam tratadas como números (float)
    # Remove pontos de milhares e converte vírgula decimal se vier formatado do Sheets
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
st.sidebar.image("https://via.placeholder.com/150", caption="Nhecotech") # Substitua pelo logo da empresa
st.sidebar.write(f"Bem-vindo, **{user_info.get('name', 'Usuário')}**")

if st.sidebar.button("🚪 Sair"):
    del st.session_state["user_token"]
    st.rerun()

st.sidebar.divider()

# Botão de Atualização Manual de Dados (Limpa o Cache)
if st.sidebar.button("🔄 Atualizar Dados da Planilha"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.subheader("Filtros de Visão")

# Filtro de colunas de demanda
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

# Somando o total global de cada coluna
vol_compensada = df['Compensada'].sum() if 'Compensada' in df.columns else 0
vol_em_aberto = df['Em Aberto'].sum() if 'Em Aberto' in df.columns else 0
vol_projetada = df['Projetada'].sum() if 'Projetada' in df.columns else 0

demanda_total = vol_compensada + vol_em_aberto + vol_projetada

# Calculando as porcentagens globais
perc_em_aberto = (vol_em_aberto / demanda_total) if demanda_total > 0 else 0
perc_projetada = (vol_projetada / demanda_total) if demanda_total > 0 else 0

# Exibição dos KPIs
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

# Calculando a representatividade de cada linha (%) sobre a Demanda Total Global
if 'Em Aberto' in df.columns:
    df['% do Total (Em Aberto)'] = df['Em Aberto'] / demanda_total if demanda_total > 0 else 0
if 'Projetada' in df.columns:
    df['% do Total (Projetada)'] = df['Projetada'] / demanda_total if demanda_total > 0 else 0

# Separando as colunas descritivas (ex: Cliente, Produto, Mês, etc) das colunas de cálculo
colunas_identificacao = [
    col for col in df.columns 
    if col not in colunas_demanda and col not in ['% do Total (Em Aberto)', '% do Total (Projetada)']
]

# Montando a lista final de colunas a serem exibidas na tabela
colunas_para_exibir = colunas_identificacao + demandas_selecionadas

# Adiciona as colunas de percentual apenas se a respectiva demanda também foi selecionada no filtro
if 'Em Aberto' in demandas_selecionadas:
    colunas_para_exibir.append('% do Total (Em Aberto)')
if 'Projetada' in demandas_selecionadas:
    colunas_para_exibir.append('% do Total (Projetada)')

# Filtra o DataFrame final
df_exibicao = df[colunas_para_exibir]

# Renderizando a Tabela com formatações
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
