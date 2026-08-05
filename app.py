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

@st.cache_data(ttl=600)
def carregar_dados_finais():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_raw = conn.read(worksheet="[Demanda] Visão Gerencial", skiprows=4)
    
    if 'SKU' in df_raw.columns:
        idx_sku = df_raw.columns.get_loc('SKU')
        df = df_raw.iloc[:, idx_sku:].copy()
    else:
        df = df_raw.copy()
    
    df.columns = [str(col).replace('.1', '').strip() for col in df.columns]
    df = df.dropna(subset=['SKU'])
    
    for col in COLUNAS_NUMERICAS:
        if col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

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
# CÁLCULOS GLOBAIS E KPIs
# ==========================================
st.subheader("Indicadores Chave (KPIs)")

total_demanda = df_filtrado['DEMANDA TOTAL'].sum()
total_compensada = df_filtrado['Compensada'].sum() if 'Compensada' in df_filtrado.columns else 0
total_em_aberto = df_filtrado['Em Aberto'].sum() if 'Em Aberto' in df_filtrado.columns else 0
total_projetada = df_filtrado['Projetada'].sum() if 'Projetada' in df_filtrado.columns else 0

soma_demanda_calc = total_compensada + total_em_aberto + total_projetada
perc_compensada = (total_compensada / soma_demanda_calc * 100) if soma_demanda_calc > 0 else 0
perc_em_aberto = (total_em_aberto / soma_demanda_calc * 100) if soma_demanda_calc > 0 else 0
perc_projetada = (total_projetada / soma_demanda_calc * 100) if soma_demanda_calc > 0 else 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Demanda Total (Calculada)", f"{soma_demanda_calc:,.0f}".replace(",", "."))
kpi2.metric("Compensada", f"{total_compensada:,.0f}".replace(",", "."), f"{perc_compensada:.1f}%", delta_color="off")
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

st.markdown("#### Composição do Estoque (Visão por UF e SKU)")

opcoes_demanda = ['Compensada', 'Em Aberto', 'Projetada']
demandas_grafico = st.multiselect(
    "Selecione as Demandas para visualizar nos gráficos abaixo:", 
    options=opcoes_demanda, 
    default=opcoes_demanda
)

if demandas_grafico:
    mapa_cores = {'Compensada': '#2ecc71', 'Em Aberto': '#e74c3c', 'Projetada': '#3498db'}
    
    # --- GRÁFICO 1: COMPOSIÇÃO POR UF ---
    df_composicao_uf = df_filtrado.groupby('UF', as_index=False)[opcoes_demanda].sum()
    df_composicao_uf['UF'] = df_composicao_uf['UF'].astype(str)
    
    # MELT: Transforma colunas em linhas para o Plotly empilhar de forma nativa
    df_uf_melted = df_composicao_uf.melt(id_vars=['UF'], value_vars=demandas_grafico, var_name='Tipo de Demanda', value_name='Valor')
    
    fig_comp_uf = px.bar(
        df_uf_melted, 
        x='UF', 
        y='Valor', 
        color='Tipo de Demanda', # Define a quebra vertical
        title="Composição da Demanda por UF", 
        color_discrete_map=mapa_cores,
        barmode='stack' # Comando direto no construtor
    )
    fig_comp_uf.update_traces(hovertemplate="%{data.name}: %{y:,.0f}<extra></extra>")
    fig_comp_uf.update_layout(
        separators=".,", 
        yaxis_tickformat=",.0f", 
        xaxis={'type': 'category', 'categoryorder': 'total descending'}
    )
    # ATENÇÃO AQUI: theme=None bloqueia o Streamlit de alterar o empilhamento
    st.plotly_chart(fig_comp_uf, use_container_width=True, theme=None) 

    # --- GRÁFICO 2: COMPOSIÇÃO POR SKU ---
    df_composicao_sku = df_filtrado.groupby('SKU', as_index=False)[opcoes_demanda].sum()
    df_composicao_sku['Total_Selecionado'] = df_composicao_sku[demandas_grafico].sum(axis=1)
    df_composicao_sku = df_composicao_sku.sort_values(by='Total_Selecionado', ascending=False)
    
    if len(df_composicao_sku) > 20:
        df_top20 = df_composicao_sku.iloc[:20].copy()
        df_demais = df_composicao_sku.iloc[20:].copy()
        
        dict_demais = {'SKU': 'Demais SKUs', 'Total_Selecionado': df_demais['Total_Selecionado'].sum()}
        for demanda in opcoes_demanda:
            dict_demais[demanda] = df_demais[demanda].sum()
            
        df_demais_row = pd.DataFrame([dict_demais])
        df_final_sku = pd.concat([df_top20, df_demais_row], ignore_index=True)
    else:
        df_final_sku = df_composicao_sku.copy()

    df_final_sku['SKU'] = df_final_sku['SKU'].astype(str)

    # MELT: Preparação perfeita para empilhamento vertical
    df_sku_melted = df_final_sku.melt(id_vars=['SKU'], value_vars=demandas_grafico, var_name='Tipo de Demanda', value_name='Valor')

    fig_comp_sku = px.bar(
        df_sku_melted, 
        x='SKU', 
        y='Valor', 
        color='Tipo de Demanda', 
        title="Composição da Demanda por SKU (Top 20 + Demais SKUs)", 
        color_discrete_map=mapa_cores,
        barmode='stack' # Comando direto no construtor
    )
    fig_comp_sku.update_traces(hovertemplate="%{data.name}: %{y:,.0f}<extra></extra>")
    fig_comp_sku.update_layout(
        separators=".,", 
        yaxis_tickformat=",.0f", 
        xaxis={'type': 'category', 'categoryorder': 'array', 'categoryarray': df_final_sku['SKU'].tolist()}
    )
    # ATENÇÃO AQUI: theme=None bloqueia o Streamlit de alterar o empilhamento
    st.plotly_chart(fig_comp_sku, use_container_width=True, theme=None)

else:
    st.info("Selecione pelo menos um tipo de demanda para exibir os gráficos.")

# ==========================================
# TABELA DETALHADA COM %
# ==========================================
with st.expander("Ver Dados Detalhados"):
    df_tabela = df_filtrado.copy()
    
    soma_linha = df_tabela['Compensada'] + df_tabela['Em Aberto'] + df_tabela['Projetada']
    df_tabela['% Compensada'] = (df_tabela['Compensada'] / soma_linha).fillna(0)
    df_tabela['% Em Aberto'] = (df_tabela['Em Aberto'] / soma_linha).fillna(0)
    df_tabela['% Projetada'] = (df_tabela['Projetada'] / soma_linha).fillna(0)
    
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

    colunas_presentes = [col for col in COLUNAS_NUMERICAS if col in df_tabela.columns]
    formato_dict = {col: formatar_numero_br for col in colunas_presentes}
    formato_dict['% Compensada'] = formatar_percentual
    formato_dict['% Em Aberto'] = formatar_percentual
    formato_dict['% Projetada'] = formatar_percentual
    
    colunas_exibicao = [c for c in df_tabela.columns if not c.startswith('%')] + ['% Compensada', '% Em Aberto', '% Projetada']
    df_tabela = df_tabela[colunas_exibicao]
    
    st.dataframe(df_tabela.style.format(formato_dict), use_container_width=True)
