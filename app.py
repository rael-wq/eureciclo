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
    
    # Lê a aba "Demanda", pulando as 4 primeiras linhas
    df_raw = conn.read(worksheet="[Demanda] Visão Gerencial", skiprows=4)
    
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
            # Verifica se o Google Sheets já enviou a coluna formatada como número
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(0)
            else:
                # Se for texto, aplica a regra de conversão de moeda brasileira
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

st.sidebar.divider() 
if st.sidebar.button("🔄 Atualizar Dados"):
    st.cache_data.clear() 
    st.rerun()            

# ==========================================
# CÁLCULOS GLOBAIS E KPIs COM %
# ==========================================
st.subheader("Indicadores Chave (KPIs)")

total_demanda = df_filtrado['DEMANDA TOTAL'].sum()
total_compensada = df_filtrado['Compensada'].sum() if 'Compensada' in df_filtrado.columns else 0
total_em_aberto = df_filtrado['Em Aberto'].sum() if 'Em Aberto' in df_filtrado.columns else 0
total_projetada = df_filtrado['Projetada'].sum() if 'Projetada' in df_filtrado.columns else 0

# Base de cálculo para os percentuais globais (Compensada + Em Aberto + Projetada)
soma_demanda_calc = total_compensada + total_em_aberto + total_projetada

perc_em_aberto = (total_em_aberto / soma_demanda_calc * 100) if soma_demanda_calc > 0 else 0
perc_projetada = (total_projetada / soma_demanda_calc * 100) if soma_demanda_calc > 0 else 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric("Demanda Total (Calculada)", f"{soma_demanda_calc:,.0f}".replace(",", "."))
kpi2.metric("Compensada", f"{total_compensada:,.0f}".replace(",", "."))
kpi3.metric("Em Aberto", f"{total_em_aberto:,.0f}".replace(",", "."), f"{perc_em_aberto:.1f}%", delta_color="off")
kpi4.metric("Projetada", f"{total_projetada:,.0f}".replace(",", "."), f"{perc_projetada:.1f}%", delta_color="off")

st.divider()

# ==========================================
# GRÁFICOS
# ==========================================
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

# Filtro específico para o gráfico de Composição
opcoes_demanda = ['Compensada', 'Em Aberto', 'Projetada']
demandas_grafico = st.multiselect(
    "Selecione as Demandas para visualizar no gráfico:", 
    options=opcoes_demanda, 
    default=opcoes_demanda
)

if demandas_grafico:
    df_composicao = df_filtrado.groupby('UF', as_index=False)[opcoes_demanda].sum()
    
    # Mapa de cores fixo para garantir que as cores não mudem ao desmarcar uma opção
    mapa_cores = {
        'Compensada': '#2ecc71', 
        'Em Aberto': '#e74c3c', 
        'Projetada': '#3498db'
    }
    
    fig_comp = px.bar(
        df_composicao, 
        x='UF', 
        y=demandas_grafico, 
        title="Composição da Demanda", 
        barmode='stack', 
        color_discrete_map=mapa_cores
    )
    fig_comp.update_traces(hovertemplate="%{data.name}: %{y:,.0f}<extra></extra>")
    fig_comp.update_layout(separators=".,", yaxis_tickformat=",.0f", legend_title_text="Tipo de Demanda")
    st.plotly_chart(fig_comp, use_container_width=True)
else:
    st.info("Selecione pelo menos um tipo de demanda para exibir o gráfico.")

# ==========================================
# TABELA DETALHADA COM %
# ==========================================
with st.expander("Ver Dados Detalhados"):
    df_tabela = df_filtrado.copy()
    
    # Calcula os indicadores percentuais linha a linha
    soma_linha = df_tabela['Compensada'] + df_tabela['Em Aberto'] + df_tabela['Projetada']
    df_tabela['% Em Aberto'] = (df_tabela['Em Aberto'] / soma_linha).fillna(0)
    df_tabela['% Projetada'] = (df_tabela['Projetada'] / soma_linha).fillna(0)
    
    # Funções de formatação do Pandas Styler
    def formatar_numero_br(valor):
        try:
            return f"{valor:,.0f}".replace(",", ".")
        except:
            return valor
            
    def formatar_percentual(valor):
        try:
            return f"{valor * 100:.1f}%".replace(".", ",")
        except:
            return valor

    # Aplica a formatação
    colunas_presentes = [col for col in COLUNAS_NUMERICAS if col in df_tabela.columns]
    formato_dict = {col: formatar_numero_br for col in colunas_presentes}
    formato_dict['% Em Aberto'] = formatar_percentual
    formato_dict['% Projetada'] = formatar_percentual
    
    st.dataframe(df_tabela.style.format(formato_dict), use_container_width=True)
