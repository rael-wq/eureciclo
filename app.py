import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from streamlit_oauth import OAuth2Component
from streamlit_gsheets import GSheetsConnection

# ==========================================
# CONFIGURAÇÃO GERAL
# ==========================================
st.set_page_config(page_title="Visão Gerencial - Demanda", layout="wide")

# Lista de colunas numéricas
COLUNAS_NUMERICAS = ['Compensada', 'Em Aberto', 'Total Contratada', 'Projetada', 'Em aberto + Projetada', 'DEMANDA TOTAL']

# ==========================================
# LOGIN E AUTENTICAÇÃO COM GOOGLE
# ==========================================
try:
    CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    REDIRECT_URI = st.secrets["REDIRECT_URI"]
except KeyError:
    st.error("⚠️ Credenciais de login não configuradas no Streamlit Secrets.")
    st.stop()

oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, 
                         "https://accounts.google.com/o/oauth2/v2/auth", 
                         "https://oauth2.googleapis.com/token", 
                         "https://oauth2.googleapis.com/token", 
                         "https://oauth2.googleapis.com/revoke")

def check_login():
    if "user_email" in st.session_state:
        if st.session_state["user_email"].endswith("@nhecotech.com"):
            return True
        else:
            st.error(f"❌ Acesso negado: {st.session_state['user_email']} não autorizado.")
            return False

    st.markdown("### 🔒 Acesso Restrito")
    st.markdown("Faça login com sua conta corporativa `@nhecotech.com` para visualizar o dashboard.")
    
    result = oauth2.authorize_button(
        name="Continuar com o Google",
        icon="https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg",
        redirect_uri=REDIRECT_URI,
        scope="openid email profile",
        key="google_login",
        use_container_width=True
    )

    if result:
        token = result.get("token")
        user_req = requests.get("https://www.googleapis.com/oauth2/v1/userinfo", 
                                headers={"Authorization": f"Bearer {token['access_token']}"})
        email = user_req.json().get("email", "")

        if email.endswith("@nhecotech.com"):
            st.session_state["user_email"] = email
            st.rerun()
        else:
            st.error(f"❌ O e-mail {email} não pertence à nhecotech.com.")
            return False
            
    return False

if not check_login():
    st.stop()

# ==========================================
# CARREGAMENTO DOS DADOS DIRETAMENTE DO SHEETS
# ==========================================
st.sidebar.success(f"Logado como: {st.session_state['user_email']}")
if st.sidebar.button("Sair (Logout)"):
    del st.session_state["user_email"]
    st.rerun()

# O ttl agora é 600 segundos (10 minutos) para evitar bloqueio da API do Google
@st.cache_data(ttl=600)
def carregar_dados_finais():
    # Cria a conexão com o Google Sheets usando as credenciais do Secrets
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Lê a aba "Demanda", pulando as 4 primeiras linhas como fazíamos no CSV
    df_raw = conn.read(worksheet="Demanda", skiprows=4)
    
    # 2. Isola a tabela detalhada (Começa a partir da coluna SKU)
    if 'SKU' in df_raw.columns:
        idx_sku = df_raw.columns.get_loc('SKU')
        df = df_raw.iloc[:, idx_sku:].copy()
    else:
        # Fallback caso a estrutura mude
        df = df_raw.copy()
    
    # 3. Limpa os nomes das colunas (tira '.1' gerado por colunas duplicadas)
    df.columns = [str(col).replace('.1', '').strip() for col in df.columns]
    
    # 4. Remove linhas vazias no final
    df = df.dropna(subset=['SKU'])
    
    # 5. Tratamento de dados numéricos vindos do Sheets
    for col in COLUNAS_NUMERICAS:
        if col in df.columns:
            # O GSheets pode entregar números já formatados como int/float ou como texto
            df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# Tratamento de erro na conexão visual
try:
    df = carregar_dados_finais()
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    st.stop()

# ==========================================
# INTERFACE E DASHBOARD
# ==========================================
st.title("📊 Visão Gerencial - Demanda de Estoque")
st.markdown("Visão executiva detalhada por SKU com filtros dinâmicos.")

st.sidebar.header("Filtros de Análise")
ano_selecionado = st.sidebar.multiselect("Ano Base", sorted(df['Ano Base'].dropna().astype(str).unique()))
uf_selecionada = st.sidebar.multiselect("Estado (UF)", sorted(df['UF'].dropna().unique()))
material_selecionado = st.sidebar.multiselect("Material", sorted(df['material'].dropna().unique()))

df_filtrado = df.copy()
if ano_selecionado:
    df_filtrado = df_filtrado[df_filtrado['Ano Base'].astype(str).isin(ano_selecionado)]
if uf_selecionada:
    df_filtrado = df_filtrado[df_filtrado['UF'].isin(uf_selecionada)]
if material_selecionado:
    df_filtrado = df_filtrado[df_filtrado['material'].isin(material_selecionado)]

st.subheader("Indicadores Chave (KPIs)")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
total_demanda = df_filtrado['DEMANDA TOTAL'].sum()
total_contratada = df_filtrado['Total Contratada'].sum()
total_projetada = df_filtrado['Projetada'].sum()
total_em_aberto = df_filtrado['Em Aberto'].sum()

kpi1.metric("Demanda Total", f"{total_demanda:,.0f}".replace(",", "."))
kpi2.metric("Total Contratada", f"{total_contratada:,.0f}".replace(",", "."))
kpi3.metric("Demanda Projetada", f"{total_projetada:,.0f}".replace(",", "."))
kpi4.metric("Em Aberto", f"{total_em_aberto:,.0f}".replace(",", "."))
st.divider()

st.subheader("Análise Visual")
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    df_uf = df_filtrado.groupby('UF', as_index=False)['DEMANDA TOTAL'].sum().sort_values('DEMANDA TOTAL', ascending=False)
    fig_uf = px.bar(df_uf, x='UF', y='DEMANDA TOTAL', title="Demanda Total por UF", color='DEMANDA TOTAL', color_continuous_scale="Blues")
    fig_uf.update_traces(texttemplate='%{y:,.0f}', textposition='outside')
    fig_uf.update_layout(separators=".,", yaxis_tickformat=",.0f")
    st.plotly_chart(fig_uf, use_container_width=True)

with col_graf2:
    df_mat = df_filtrado.groupby('material', as_index=False)['DEMANDA TOTAL'].sum()
    fig_mat = px.pie(df_mat, values='DEMANDA TOTAL', names='material', title="Distribuição da Demanda por Material", hole=0.4)
    fig_mat.update_traces(textposition='inside', textinfo='percent+label', hovertemplate="%{label}: %{value:,.0f}<extra></extra>")
    fig_mat.update_layout(separators=".,")
    st.plotly_chart(fig_mat, use_container_width=True)

st.markdown("#### Composição do Estoque por UF")
df_composicao = df_filtrado.groupby('UF', as_index=False)[['Compensada', 'Em Aberto', 'Projetada']].sum()
fig_comp = px.bar(df_composicao, x='UF', y=['Compensada', 'Em Aberto', 'Projetada'], title="Composição da Demanda: Compensada vs Em Aberto vs Projetada", barmode='stack', color_discrete_sequence=['#2ecc71', '#e74c3c', '#3498db'])
fig_comp.update_traces(hovertemplate="%{data.name}: %{y:,.0f}<extra></extra>")
fig_comp.update_layout(separators=".,", yaxis_tickformat=",.0f")
st.plotly_chart(fig_comp, use_container_width=True)

with st.expander("Ver Dados Detalhados"):
    def formatar_numero_br(valor):
        try:
            return f"{valor:,.0f}".replace(",", ".")
        except:
            return valor
    colunas_presentes = [col for col in COLUNAS_NUMERICAS if col in df_filtrado.columns]
    formato_dict = {col: formatar_numero_br for col in colunas_presentes}
    st.dataframe(df_filtrado.style.format(formato_dict), use_container_width=True)
