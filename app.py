import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from streamlit_oauth import OAuth2Component
from streamlit_gsheets import GSheetsConnection

# ==========================================
# CONFIGURAÇÃO GERAL E TEMA INSTITUCIONAL EURECICLO
# ==========================================
st.set_page_config(
    page_title="Dashboard Executivo - eureciclo -", 
    layout="wide", 
    page_icon="♻️",
    initial_sidebar_state="expanded"
)

# Estilização CSS inspirada no portal principal da eureciclo (eureciclo.com.br)
# Inclui regras para ESCONDER o menu de três pontos do canto superior direito
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

    /* Ocultar o menu de três pontos (MainMenu) e o cabeçalho superior */
    #MainMenu {visibility: hidden !important;}
    [data-testid="stHeader"] {visibility: hidden !important;}
    footer {visibility: hidden !important;}

    /* Forçar Tema Light Institucional */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #FAFAFA !important;
        color: #2D3748 !important;
        font-family: 'Inter', sans-serif !important;
        color-scheme: light !important;
    }
    
    /* Fontes e Títulos do Portal eureciclo */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Montserrat', sans-serif !important;
        color: #0B3C5D !important;
        font-weight: 700 !important;
        letter-spacing: -0.3px;
    }

    h1 {
        font-size: 1.8rem !important;
        margin-bottom: 0.5rem !important;
    }

    h2, h3 {
        font-size: 1.3rem !important;
        margin-top: 1rem !important;
    }

    h5 {
        font-size: 0.9rem !important;
        margin-bottom: 0.3rem !important;
        font-weight: 600 !important;
    }

    /* Barra Lateral Ajustada */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E2E8F0 !important;
    }

    /* Cards de Métricas (KPIs) */
    [data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        padding: 12px 16px !important;
        border-radius: 12px !important;
        border: 1px solid #E2E8F0 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03) !important;
    }

    [data-testid="stMetricLabel"] {
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 600 !important;
        color: #4A5568 !important;
        font-size: 0.85rem !important;
    }

    [data-testid="stMetricValue"] {
        color: #00A859 !important;
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.6rem !important;
    }

    /* Botões Institucionais */
    .stButton>button {
        background-color: #00A859 !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        border: none !important;
        font-family: 'Montserrat', sans-serif !important;
        font-weight: 600 !important;
        padding: 8px 16px !important;
        transition: all 0.2s ease-in-out;
    }

    .stButton>button:hover {
        background-color: #007A40 !important;
        box-shadow: 0 4px 12px rgba(0, 168, 89, 0.3) !important;
    }

    /* Ajuste de Tamanho de Fonte das Tabelas Nativas */
    [data-testid="stDataFrame"] {
        font-size: 0.72rem !important;
    }

    /* Dividers */
    hr {
        border-top: 1px solid #E2E8F0 !important;
    }
    </style>
""", unsafe_allow_html=True)

COLUNAS_NUMERICAS_DEMANDA = ['Compensada', 'Em Aberto', 'Total Contratada', 'Projetada', 'Em aberto + Projetada', 'DEMANDA TOTAL']

COLUNAS_EXIBICAO_COBERTURA = [
    'UF', 'material', 'SKU', 'Ano Base',
    'Demanda Atual', 'Demanda Projetada', 'Demanda TOTAL', 
    'Quebra Atual', 'Quebra Projetada', 'Quebra Projetada c/ pipe Ops',
    'Quebra Atual (report)', 'Quebra Projetada (report)', 'Quebra Projetada c/ pipe Ops (report)'
]

COLUNAS_NUMERICAS_COBERTURA = [
    'Demanda Atual', 'Demanda Projetada', 'Demanda TOTAL', 
    'Quebra Atual', 'Quebra Projetada', 'Quebra Projetada c/ pipe Ops',
    'Quebra Atual (report)', 'Quebra Projetada (report)', 'Quebra Projetada c/ pipe Ops (report)'
]

COLUNAS_QUEBRAS_TODAS = [
    'Quebra Atual', 'Quebra Projetada', 'Quebra Projetada c/ pipe Ops',
    'Quebra Atual (report)', 'Quebra Projetada (report)', 'Quebra Projetada c/ pipe Ops (report)'
]

PALETA_EURECICLO = {
    'Compensada': '#00A859',                    # Verde eureciclo
    'Em Aberto': '#FF5A5F',                     # Coral
    'Projetada': '#0284C7',                     # Azul Oceano
    'Quebra Atual': '#E53E3E',                  # Vermelho Alerta
    'Quebra Projetada': '#DD6B20',              # Laranja Institucional
    'Quebra Projetada c/ pipe Ops': '#D69E2E',  # Âmbar
    'Quebra Atual (report)': '#9B2C2C',         # Vermelho Escuro
    'Quebra Projetada (report)': '#C05621',      # Laranja Escuro
    'Quebra Projetada c/ pipe Ops (report)': '#B7791F', # Âmbar Escuro
    'Verde_Escala': ['#E6F4EA', '#A3E0BF', '#42C785', '#00A859', '#007A40']
}

# Padrão Nacional de Cores da Reciclagem (CONAMA Resolução 275/2001)
CORES_MATERIAIS_CONAMA = {
    'PAPEL': '#2563EB',         # Azul (Papel / Papelão)
    'PLÁSTICO': '#DC2626',      # Vermelho (Plástico)
    'VIDRO': '#16A34A',         # Verde (Vidro)
    'METAL': '#EAB308',         # Amarelo (Metal)
    'PLÁSTICO PP': '#F87171',   # Tom Avermelhado Suave (Derivado de Plástico)
    'CARTONADO': '#1D4ED8',    # Tom Azul Escuro (Derivado de Papel)
    'CDRU': '#64748B'           # Cinza (Resíduo Geral / Não Reciclável)
}

LOGO_EURECICLO_URL = "https://pages.greatpages.com.br/lp.bowe.com.br-lp-eu-logistica/1782305795/imagens/desktop/3604298_1_17823057706a3bd3ea90543409291793.svg"

# ==========================================
# FUNÇÕES AUXILIARES DE TRATAMENTO E ESTILO
# ==========================================
def converter_valor_num(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s.lower() == 'nan':
        return 0.0
    try:
        return float(s)
    except ValueError:
        pass
    try:
        s_clean = s.replace('.', '').replace(',', '.')
        return float(s_clean)
    except ValueError:
        return 0.0

def colorir_celula_quebra(val):
    if not isinstance(val, (int, float)) or pd.isna(val):
        return ''
    if val < 0:
        alpha = min(abs(val) / 30000, 1.0) * 0.45 + 0.1
        return f'background-color: rgba(229, 62, 62, {alpha:.2f}); color: #1E293B;'
    elif val > 0:
        alpha = min(val / 30000, 1.0) * 0.45 + 0.1
        return f'background-color: rgba(2, 132, 199, {alpha:.2f}); color: #1E293B;'
    else:
        return 'background-color: #FFFFFF; color: #A0AEC0;'

# ==========================================
# CARREGAMENTO DA DATA DE ATUALIZAÇÃO (B1 DA ABA >>>>BASES>>>)
# ==========================================
@st.cache_data(ttl=600)
def carregar_data_atualizacao():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_bases = conn.read(worksheet=">>>>BASES>>>", nrows=1, header=None)
        if not df_bases.empty and len(df_bases.columns) > 1:
            val_b1 = str(df_bases.iloc[0, 1]).strip()
            if val_b1 and val_b1.lower() != 'nan':
                return val_b1
    except Exception:
        pass
    return "Não informada"

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

    st.image(LOGO_EURECICLO_URL, width=220)
    st.markdown("### 🔒 Acesso Restrito - Portal eureciclo")
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
# LOGO, LOGIN, BOTÃO DE LOGOUT E CARD DE DATA
# ==========================================
st.sidebar.image(LOGO_EURECICLO_URL, width=170)
st.sidebar.markdown("### Gestão de Operações")
st.sidebar.success(f"Logado como:\n{st.session_state['user_email']}")

if st.sidebar.button("Sair (Logout)"):
    del st.session_state["user_email"]
    st.rerun()

# CARD DA DATA DE ATUALIZAÇÃO DOS DADOS (ABA >>>>BASES>>> B1)
data_atualizacao_val = carregar_data_atualizacao()
st.sidebar.markdown(f"""
    <div style="
        background-color: #F1F5F9;
        border: 1px solid #CBD5E1;
        border-radius: 8px;
        padding: 10px 12px;
        margin-top: 10px;
        margin-bottom: 12px;
    ">
        <div style="font-weight: 600; font-size: 0.78rem; color: #475569; display: flex; align-items: center; gap: 6px;">
            📅 Data de Atualização
        </div>
        <div style="font-weight: 700; font-size: 0.88rem; color: #0B3C5D; margin-top: 4px;">
            {data_atualizacao_val}
        </div>
    </div>
""", unsafe_allow_html=True)

st.sidebar.divider()

pagina_selecionada = st.sidebar.radio(
    "Navegação do Dashboard:",
    ["📊 Visão de Demanda", "🛡️ Visão de Cobertura", "📅 Cronograma 2S26"]
)
st.sidebar.divider()

# ==========================================
# CARREGAMENTO DOS DADOS (CACHE DE 10 MIN)
# ==========================================
@st.cache_data(ttl=600)
def carregar_dados_demanda():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_raw = conn.read(worksheet="[DASH] Demanda", skiprows=4)
    
    if 'SKU' in df_raw.columns:
        idx_sku = df_raw.columns.get_loc('SKU')
        df = df_raw.iloc[:, idx_sku:].copy()
    else:
        df = df_raw.copy()
    
    df.columns = [str(col).replace('.1', '').strip() for col in df.columns]
    df = df.dropna(subset=['SKU'])
    
    for col in COLUNAS_NUMERICAS_DEMANDA:
        if col in df.columns:
            df[col] = df[col].apply(converter_valor_num)
            
    return df

@st.cache_data(ttl=600)
def carregar_dados_cobertura():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_raw = conn.read(worksheet="Cobertura / SKU (total)", skiprows=17)
    
    df = df_raw.copy()
    df.columns = [str(col).replace('.1', '').strip() for col in df.columns]
    
    if 'SKU' in df.columns:
        df = df.dropna(subset=['SKU'])
    
    for col in COLUNAS_NUMERICAS_COBERTURA:
        if col in df.columns:
            df[col] = df[col].apply(converter_valor_num)
            
    return df

@st.cache_data(ttl=600)
def carregar_dados_cronograma():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_raw = conn.read(worksheet="[DASH] Cronograma")
    except Exception:
        df_raw = conn.read(worksheet="[DASH] Cronograma", skiprows=4)
    
    df = df_raw.copy()
    cols_clean = [str(col).replace('.1', '').strip() for col in df.columns]
    df.columns = cols_clean

    col_uf = [c for c in df.columns if c.upper() == 'UF']
    col_mes = [c for c in df.columns if 'mês' in c.lower() or 'mes' in c.lower()]
    col_massa = [c for c in df.columns if 'massa' in c.lower()]
    col_ops = [c for c in df.columns if 'operador' in c.lower()]

    if col_uf and col_mes and col_massa and col_ops:
        df = df[[col_uf[0], col_mes[0], col_massa[0], col_ops[0]]].copy()
        df.columns = ['UF', 'Mês', 'Massa (t)', 'Operadores (#)']
    else:
        df = df.iloc[:, :4].copy()
        df.columns = ['UF', 'Mês', 'Massa (t)', 'Operadores (#)']

    df = df.dropna(subset=['UF', 'Mês']).copy()
    df = df[df['UF'].astype(str).str.upper() != 'UF'].copy()
    
    df['Massa (t)'] = df['Massa (t)'].apply(converter_valor_num)
    df['Operadores (#)'] = df['Operadores (#)'].apply(converter_valor_num)
    
    df['Mês_dt'] = pd.to_datetime(df['Mês'], errors='coerce')
    df = df.dropna(subset=['Mês_dt']).sort_values('Mês_dt').reset_index(drop=True)
    
    df['Mês_Label'] = df['Mês_dt'].dt.strftime('%m/%y')
    
    return df

# ==========================================
# FUNÇÃO PARA VISÃO DE DEMANDA
# ==========================================
def renderizar_visao_demanda():
    try:
        df = carregar_dados_demanda()
    except Exception as e:
        st.error(f"Erro ao carregar dados de Demanda: {e}")
        return

    st.title("📊 Visão Gerencial - Demanda de Estoque")
    st.markdown("Gestão executiva de demanda e saldo por SKU.")

    st.sidebar.header("Filtros de Demanda")
    ano_selecionado = st.sidebar.multiselect("Ano Base", sorted(df['Ano Base'].dropna().astype(str).unique()), key="dem_ano")
    uf_selecionada = st.sidebar.multiselect("Estado (UF)", sorted(df['UF'].dropna().unique()), key="dem_uf")
    material_selecionado = st.sidebar.multiselect("Material", sorted(df['material'].dropna().unique()), key="dem_mat")

    df_filtrado = df.copy()
    if ano_selecionado:
        df_filtrado = df_filtrado[df_filtrado['Ano Base'].astype(str).isin(ano_selecionado)]
    if uf_selecionada:
        df_filtrado = df_filtrado[df_filtrado['UF'].isin(uf_selecionada)]
    if material_selecionado:
        df_filtrado = df_filtrado[df_filtrado['material'].isin(material_selecionado)]

    st.sidebar.divider() 
    if st.sidebar.button("🔄 Atualizar Dados", key="dem_reload"):
        st.cache_data.clear() 
        st.rerun()            

    # KPIs
    st.subheader("Indicadores Chave (KPIs)")
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

    # GRÁFICOS INICIAIS
    st.subheader("Análise Visual")
    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        df_uf = df_filtrado.groupby('UF', as_index=False)['DEMANDA TOTAL'].sum().sort_values('DEMANDA TOTAL', ascending=False)
        fig_uf = px.bar(
            df_uf, x='UF', y='DEMANDA TOTAL', 
            title="Demanda Total por UF", 
            color='DEMANDA TOTAL', 
            color_continuous_scale=PALETA_EURECICLO['Verde_Escala']
        )
        fig_uf.update_traces(texttemplate='%{y:,.0f}', textposition='outside')
        fig_uf.update_layout(separators=".,", yaxis_tickformat=",.0f", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif"))
        st.plotly_chart(fig_uf, use_container_width=True)

    with col_graf2:
        df_mat = df_filtrado.groupby('material', as_index=False)['DEMANDA TOTAL'].sum()
        
        fig_mat = px.pie(
            df_mat, values='DEMANDA TOTAL', names='material', 
            title="Distribuição da Demanda por Material (Padrão CONAMA)", hole=0.4,
            color='material',
            color_discrete_map=CORES_MATERIAIS_CONAMA
        )
        fig_mat.update_traces(textposition='inside', textinfo='percent+label', hovertemplate="%{label}: %{value:,.0f}<extra></extra>")
        fig_mat.update_layout(separators=".,", paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif"))
        st.plotly_chart(fig_mat, use_container_width=True)

    st.markdown("#### Composição do Estoque (Visão por UF e SKU)")
    opcoes_demanda = ['Compensada', 'Em Aberto', 'Projetada']
    demandas_grafico = st.multiselect("Selecione as Demandas:", options=opcoes_demanda, default=opcoes_demanda, key="dem_multi")

    if demandas_grafico:
        mapa_cores = {
            'Compensada': PALETA_EURECICLO['Compensada'], 
            'Em Aberto': PALETA_EURECICLO['Em Aberto'], 
            'Projetada': PALETA_EURECICLO['Projetada']
        }
        
        # 1. UF: COLUNAS VERTICAIS EMPILHADAS
        df_composicao_uf = df_filtrado.groupby('UF', as_index=False)[opcoes_demanda].sum()
        df_composicao_uf['UF'] = df_composicao_uf['UF'].astype(str)
        df_uf_melted = df_composicao_uf.melt(id_vars=['UF'], value_vars=demandas_grafico, var_name='Tipo de Demanda', value_name='Valor')
        
        fig_comp_uf = px.bar(
            df_uf_melted, x='UF', y='Valor', color='Tipo de Demanda',
            title="Composição da Demanda por UF", color_discrete_map=mapa_cores, barmode='stack'
        )
        fig_comp_uf.update_traces(hovertemplate="%{data.name}: %{y:,.0f}<extra></extra>")
        fig_comp_uf.update_layout(
            separators=".,", yaxis_tickformat=",.0f", 
            xaxis={'type': 'category', 'categoryorder': 'total descending'},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif")
        )
        st.plotly_chart(fig_comp_uf, use_container_width=True)

        # 2. SKU: BARRAS HORIZONTAIS EMPILHADAS
        df_composicao_sku = df_filtrado.groupby('SKU', as_index=False)[opcoes_demanda].sum()
        df_composicao_sku['Total_Selecionado'] = df_composicao_sku[demandas_grafico].sum(axis=1)
        df_composicao_sku = df_composicao_sku.sort_values(by='Total_Selecionado', ascending=False)
        
        if len(df_composicao_sku) > 20:
            df_top20 = df_composicao_sku.iloc[:20].copy()
            df_demais = df_composicao_sku.iloc[20:].copy()
            dict_demais = {'SKU': 'Demais SKUs', 'Total_Selecionado': df_demais['Total_Selecionado'].sum()}
            for demanda in opcoes_demanda:
                dict_demais[demanda] = df_demais[demanda].sum()
            df_final_sku = pd.concat([df_top20, pd.DataFrame([dict_demais])], ignore_index=True)
        else:
            df_final_sku = df_composicao_sku.copy()

        df_final_sku['SKU'] = df_final_sku['SKU'].astype(str)
        ordem_y = df_final_sku['SKU'].tolist()[::-1]
        df_sku_melted = df_final_sku.melt(id_vars=['SKU'], value_vars=demandas_grafico, var_name='Tipo de Demanda', value_name='Valor')

        fig_comp_sku = px.bar(
            df_sku_melted, x='Valor', y='SKU', color='Tipo de Demanda', orientation='h',
            title="Composição da Demanda por SKU (Top 20 + Demais SKUs)", color_discrete_map=mapa_cores, barmode='stack'
        )
        fig_comp_sku.update_traces(hovertemplate="%{data.name}: %{x:,.0f}<extra></extra>")
        fig_comp_sku.update_layout(
            separators=".,", xaxis_tickformat=",.0f",
            yaxis={'type': 'category', 'categoryorder': 'array', 'categoryarray': ordem_y}, height=600,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif")
        )
        st.plotly_chart(fig_comp_sku, use_container_width=True)

    # TABELA DETALHADA
    with st.expander("Ver Dados Detalhados"):
        df_tabela = df_filtrado.copy()
        soma_linha = df_tabela['Compensada'] + df_tabela['Em Aberto'] + df_tabela['Projetada']
        df_tabela['% Compensada'] = (df_tabela['Compensada'] / soma_linha).fillna(0)
        df_tabela['% Em Aberto'] = (df_tabela['Em Aberto'] / soma_linha).fillna(0)
        df_tabela['% Projetada'] = (df_tabela['Projetada'] / soma_linha).fillna(0)
        
        def formatar_numero_br(v):
            try: return f"{v:,.0f}".replace(",", ".")
            except: return v
        def formatar_percentual(v):
            try: return f"{v * 100:.1f}%".replace(".", ",")
            except: return v

        formato_dict = {col: formatar_numero_br for col in COLUNAS_NUMERICAS_DEMANDA if col in df_tabela.columns}
        formato_dict['% Compensada'] = formatar_percentual
        formato_dict['% Em Aberto'] = formatar_percentual
        formato_dict['% Projetada'] = formatar_percentual
        
        colunas_exibicao = [c for c in df_tabela.columns if not c.startswith('%')] + ['% Compensada', '% Em Aberto', '% Projetada']
        st.dataframe(df_tabela[colunas_exibicao].style.format(formato_dict), use_container_width=True)

# ==========================================
# FUNÇÃO PARA VISÃO DE COBERTURA (QUEBRAS)
# ==========================================
def renderizar_visao_cobertura():
    try:
        df = carregar_dados_cobertura()
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba Cobertura / SKU (total): {e}")
        return

    st.title("🛡️ Visão Gerencial - Cobertura e Quebras de Estoque")
    st.markdown("Análise detalhada de Quebras e Déficit por SKU.")

    st.sidebar.header("Filtros de Cobertura")
    ano_selecionado = st.sidebar.multiselect("Ano Base", sorted(df['Ano Base'].dropna().astype(str).unique()), key="cob_ano")
    uf_selecionada = st.sidebar.multiselect("Estado (UF)", sorted(df['UF'].dropna().unique()), key="cob_uf")
    material_selecionado = st.sidebar.multiselect("Material", sorted(df['material'].dropna().unique()), key="cob_mat")

    # 1. Aplicação de filtros no dataset base
    df_filtrado = df.copy()
    if ano_selecionado:
        df_filtrado = df_filtrado[df_filtrado['Ano Base'].astype(str).isin(ano_selecionado)]
    if uf_selecionada:
        df_filtrado = df_filtrado[df_filtrado['UF'].isin(uf_selecionada)]
    if material_selecionado:
        df_filtrado = df_filtrado[df_filtrado['material'].isin(material_selecionado)]

    for col in COLUNAS_NUMERICAS_COBERTURA:
        if col in df_filtrado.columns:
            df_filtrado[col] = df_filtrado[col].apply(converter_valor_num)

    st.sidebar.divider()
    if st.sidebar.button("🔄 Atualizar Dados", key="cob_reload"):
        st.cache_data.clear()
        st.rerun()

    # CÁLCULOS DOS KPIs COM INDEXAÇÃO BOOLEANA ESTRITA (< 0)
    total_demanda_cob = df_filtrado['Demanda TOTAL'].sum()
    
    total_quebra_atual = df_filtrado[df_filtrado['Quebra Atual'] < 0]['Quebra Atual'].sum()
    total_quebra_proj = df_filtrado[df_filtrado['Quebra Projetada'] < 0]['Quebra Projetada'].sum()
    total_quebra_pipe = df_filtrado[df_filtrado['Quebra Projetada c/ pipe Ops'] < 0]['Quebra Projetada c/ pipe Ops'].sum()

    total_quebra_atual_rep = df_filtrado[df_filtrado['Quebra Atual (report)'] < 0]['Quebra Atual (report)'].sum() if 'Quebra Atual (report)' in df_filtrado.columns else 0
    total_quebra_proj_rep = df_filtrado[df_filtrado['Quebra Projetada (report)'] < 0]['Quebra Projetada (report)'].sum() if 'Quebra Projetada (report)' in df_filtrado.columns else 0
    total_quebra_pipe_rep = df_filtrado[df_filtrado['Quebra Projetada c/ pipe Ops (report)'] < 0]['Quebra Projetada c/ pipe Ops (report)'].sum() if 'Quebra Projetada c/ pipe Ops (report)' in df_filtrado.columns else 0

    pct_quebra_atual = (total_quebra_atual / total_demanda_cob * 100) if total_demanda_cob > 0 else 0
    pct_quebra_proj = (total_quebra_proj / total_demanda_cob * 100) if total_demanda_cob > 0 else 0
    pct_quebra_pipe = (total_quebra_pipe / total_demanda_cob * 100) if total_demanda_cob > 0 else 0

    pct_quebra_atual_rep = (total_quebra_atual_rep / total_demanda_cob * 100) if total_demanda_cob > 0 else 0
    pct_quebra_proj_rep = (total_quebra_proj_rep / total_demanda_cob * 100) if total_demanda_cob > 0 else 0
    pct_quebra_pipe_rep = (total_quebra_pipe_rep / total_demanda_cob * 100) if total_demanda_cob > 0 else 0

    st.subheader("Indicadores Chave de Quebra (KPIs)")
    
    # Primeira linha: Demanda + 3 Quebras Padrão
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Demanda a Compensar", f"{total_demanda_cob:,.0f}".replace(",", "."))
    kpi2.metric(
        "Quebra Atual", 
        f"{total_quebra_atual:,.0f}".replace(",", "."), 
        f"{pct_quebra_atual:.1f}%".replace(".", ","), 
        delta_color="off"
    )
    kpi3.metric(
        "Quebra Projetada", 
        f"{total_quebra_proj:,.0f}".replace(",", "."), 
        f"{pct_quebra_proj:.1f}%".replace(".", ","), 
        delta_color="off"
    )
    kpi4.metric(
        "Quebra c/ Pipe Ops", 
        f"{total_quebra_pipe:,.0f}".replace(",", "."), 
        f"{pct_quebra_pipe:.1f}%".replace(".", ","), 
        delta_color="off"
    )

    st.markdown("##### Indicadores de Quebra (Report)")
    # Segunda linha: 3 Indicadores (Report)
    kpi_r1, kpi_r2, kpi_r3 = st.columns(3)
    kpi_r1.metric(
        "Quebra Atual (Report)", 
        f"{total_quebra_atual_rep:,.0f}".replace(",", "."), 
        f"{pct_quebra_atual_rep:.1f}%".replace(".", ","), 
        delta_color="off"
    )
    kpi_r2.metric(
        "Quebra Projetada (Report)", 
        f"{total_quebra_proj_rep:,.0f}".replace(",", "."), 
        f"{pct_quebra_proj_rep:.1f}%".replace(".", ","), 
        delta_color="off"
    )
    kpi_r3.metric(
        "Quebra c/ Pipe Ops (Report)", 
        f"{total_quebra_pipe_rep:,.0f}".replace(",", "."), 
        f"{pct_quebra_pipe_rep:.1f}%".replace(".", ","), 
        delta_color="off"
    )

    st.divider()

    # TABELAS PIVOTEADAS EM ABAS (TABS) - QUEBRA TOTAL SOMA EXCLUSIVAMENTE VALORES NEGATIVOS
    st.subheader("Análise Detalhada das Quebras por UF e Material")

    def formatar_numero_br(v):
        try: return f"{v:,.0f}".replace(",", ".")
        except: return v

    def gerar_styler_pivot(coluna_metrica):
        if coluna_metrica in df_filtrado.columns and 'UF' in df_filtrado.columns and 'material' in df_filtrado.columns:
            pivot_df = df_filtrado.pivot_table(
                index='UF', 
                columns='material', 
                values=coluna_metrica, 
                aggfunc='sum', 
                fill_value=0.0
            )
            
            # Coluna 'Quebra Total' somando ESTRITAMENTE apenas os valores negativos (< 0)
            pivot_df['Quebra Total'] = pivot_df.apply(lambda row: row[row < 0].sum(), axis=1)
            
            fmt_dict = {c: formatar_numero_br for c in pivot_df.columns}
            
            styler_obj = pivot_df.style.format(fmt_dict)
            if hasattr(styler_obj, "map"):
                styler = styler_obj.map(colorir_celula_quebra)
            else:
                styler = styler_obj.applymap(colorir_celula_quebra)
            
            return styler
        return None

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "1. Quebra Atual", 
        "2. Quebra Projetada", 
        "3. Quebra c/ Pipe Ops",
        "4. Quebra Atual (Report)",
        "5. Quebra Projetada (Report)",
        "6. Quebra c/ Pipe Ops (Report)"
    ])

    with tab1:
        styler1 = gerar_styler_pivot('Quebra Atual')
        if styler1: st.dataframe(styler1, use_container_width=True)
        else: st.warning("Dados indisponíveis.")

    with tab2:
        styler2 = gerar_styler_pivot('Quebra Projetada')
        if styler2: st.dataframe(styler2, use_container_width=True)
        else: st.warning("Dados indisponíveis.")

    with tab3:
        styler3 = gerar_styler_pivot('Quebra Projetada c/ pipe Ops')
        if styler3: st.dataframe(styler3, use_container_width=True)
        else: st.warning("Dados indisponíveis.")

    with tab4:
        styler4 = gerar_styler_pivot('Quebra Atual (report)')
        if styler4: st.dataframe(styler4, use_container_width=True)
        else: st.warning("Dados indisponíveis.")

    with tab5:
        styler5 = gerar_styler_pivot('Quebra Projetada (report)')
        if styler5: st.dataframe(styler5, use_container_width=True)
        else: st.warning("Dados indisponíveis.")

    with tab6:
        styler6 = gerar_styler_pivot('Quebra Projetada c/ pipe Ops (report)')
        if styler6: st.dataframe(styler6, use_container_width=True)
        else: st.warning("Dados indisponíveis.")

    st.divider()

    st.markdown("#### Composição das Quebras por UF e SKU")
    
    opcoes_quebra = [
        'Quebra Atual', 
        'Quebra Projetada', 
        'Quebra Projetada c/ pipe Ops',
        'Quebra Atual (report)', 
        'Quebra Projetada (report)', 
        'Quebra Projetada c/ pipe Ops (report)'
    ]
    
    quebras_grafico = st.multiselect(
        "Selecione os Tipos de Quebra para visualizar nos gráficos:", 
        options=opcoes_quebra, 
        default=opcoes_quebra, 
        key="cob_multi"
    )

    if quebras_grafico:
        mapa_cores_quebra = {
            'Quebra Atual': PALETA_EURECICLO['Quebra Atual'], 
            'Quebra Projetada': PALETA_EURECICLO['Quebra Projetada'], 
            'Quebra Projetada c/ pipe Ops': PALETA_EURECICLO['Quebra Projetada c/ pipe Ops'],
            'Quebra Atual (report)': PALETA_EURECICLO['Quebra Atual (report)'],
            'Quebra Projetada (report)': PALETA_EURECICLO['Quebra Projetada (report)'],
            'Quebra Projetada c/ pipe Ops (report)': PALETA_EURECICLO['Quebra Projetada c/ pipe Ops (report)']
        }

        # 1. GRÁFICO POR UF: FILTRA ESTRITAMENTE APENAS AS LINHAS COM QUEBRA < 0
        df_uf_quebra_negativas = df_filtrado.copy()
        for c in quebras_grafico:
            if c in df_uf_quebra_negativas.columns:
                df_uf_quebra_negativas[c] = df_uf_quebra_negativas[c].apply(lambda x: x if x < 0 else 0.0)

        df_composicao_uf_quebra = df_uf_quebra_negativas.groupby('UF', as_index=False)[quebras_grafico].sum()
        df_composicao_uf_quebra['UF'] = df_composicao_uf_quebra['UF'].astype(str)
        df_uf_melted_quebra = df_composicao_uf_quebra.melt(id_vars=['UF'], value_vars=quebras_grafico, var_name='Tipo de Quebra', value_name='Valor')

        fig_comp_uf_quebra = px.bar(
            df_uf_melted_quebra, x='UF', y='Valor', color='Tipo de Quebra',
            title="Composição da Quebra por UF (Somente Déficits Negativos)", color_discrete_map=mapa_cores_quebra, barmode='stack'
        )
        fig_comp_uf_quebra.update_traces(hovertemplate="%{data.name}: %{y:,.0f}<extra></extra>")
        fig_comp_uf_quebra.update_layout(
            separators=".,", yaxis_tickformat=",.0f", 
            xaxis={'type': 'category', 'categoryorder': 'total ascending'},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif")
        )
        st.plotly_chart(fig_comp_uf_quebra, use_container_width=True)

        # 2. GRÁFICO POR SKU: FILTRA ESTRITAMENTE APENAS AS LINHAS COM QUEBRA < 0
        df_sku_quebra_negativas = df_filtrado.copy()
        for c in quebras_grafico:
            if c in df_sku_quebra_negativas.columns:
                df_sku_quebra_negativas[c] = df_sku_quebra_negativas[c].apply(lambda x: x if x < 0 else 0.0)

        df_sku_base = df_sku_quebra_negativas.groupby('SKU', as_index=False)[quebras_grafico].sum()
        df_sku_base['Total_Quebra'] = df_sku_base[quebras_grafico].sum(axis=1)
        df_sku_base = df_sku_base.sort_values(by='Total_Quebra', ascending=True)

        if len(df_sku_base) > 20:
            df_top20_quebra = df_sku_base.iloc[:20].copy()
            df_demais_quebra = df_sku_base.iloc[20:].copy()
            dict_demais_quebra = {'SKU': 'Demais SKUs', 'Total_Quebra': df_demais_quebra['Total_Quebra'].sum()}
            for q_col in quebras_grafico:
                dict_demais_quebra[q_col] = df_demais_quebra[q_col].sum()
            df_final_sku_quebra = pd.concat([df_top20_quebra, pd.DataFrame([dict_demais_quebra])], ignore_index=True)
        else:
            df_final_sku_quebra = df_sku_base.copy()

        df_final_sku_quebra['SKU'] = df_final_sku_quebra['SKU'].astype(str)
        ordem_y_quebra = df_final_sku_quebra['SKU'].tolist()[::-1]
        df_sku_melted_quebra = df_final_sku_quebra.melt(id_vars=['SKU'], value_vars=quebras_grafico, var_name='Tipo de Quebra', value_name='Valor')

        fig_comp_sku_quebra = px.bar(
            df_sku_melted_quebra, x='Valor', y='SKU', color='Tipo de Quebra', orientation='h',
            title="Composição da Quebra por SKU (Top 20 + Demais SKUs - Somente Déficits Negativos)", color_discrete_map=mapa_cores_quebra, barmode='stack'
        )
        fig_comp_sku_quebra.update_traces(hovertemplate="%{data.name}: %{x:,.0f}<extra></extra>")
        fig_comp_sku_quebra.update_layout(
            separators=".,", xaxis_tickformat=",.0f",
            yaxis={'type': 'category', 'categoryorder': 'array', 'categoryarray': ordem_y_quebra}, height=600,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif")
        )
        st.plotly_chart(fig_comp_sku_quebra, use_container_width=True)

    # TABELA DETALHADA COBERTURA / QUEBRAS
    with st.expander("Ver Dados Detalhados de Quebras"):
        cols_presentes = [c for c in COLUNAS_EXIBICAO_COBERTURA if c in df_filtrado.columns]
        df_tabela_cob = df_filtrado[cols_presentes].copy()

        formato_dict_cob = {col: formatar_numero_br for col in COLUNAS_NUMERICAS_COBERTURA if col in df_tabela_cob.columns}
        st.dataframe(df_tabela_cob.style.format(formato_dict_cob), use_container_width=True)

# ==========================================
# FUNÇÃO PARA CRONOGRAMA 2S26
# ==========================================
def renderizar_cronograma_2s26():
    try:
        df = carregar_dados_cronograma()
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba [DASH] Cronograma: {e}")
        return

    if df.empty:
        st.warning("⚠️ Não foram encontrados dados na aba [DASH] Cronograma.")
        return

    st.title("📅 Cronograma de Entregas 2S26")
    st.markdown("Consulta e acompanhamento estratégico do cronograma de entregas e operadores por UF.")

    # Filtros laterais
    st.sidebar.header("Filtros do Cronograma")
    
    meses_unicos = df[['Mês_Label', 'Mês_dt']].drop_duplicates().sort_values('Mês_dt')
    meses_disponiveis = meses_unicos['Mês_Label'].tolist()
    
    mes_selecionado = st.sidebar.multiselect("Mês de Entrega (mm/yy)", meses_disponiveis, key="cron_mes")
    uf_selecionada = st.sidebar.multiselect("Estado (UF)", sorted(df['UF'].unique()), key="cron_uf")

    df_filtrado = df.copy()
    if mes_selecionado:
        df_filtrado = df_filtrado[df_filtrado['Mês_Label'].isin(mes_selecionado)]
    if uf_selecionada:
        df_filtrado = df_filtrado[df_filtrado['UF'].isin(uf_selecionada)]

    st.sidebar.divider()
    if st.sidebar.button("🔄 Atualizar Dados", key="cron_reload"):
        st.cache_data.clear()
        st.rerun()

    # 1. KPIs
    total_massa = df_filtrado['Massa (t)'].sum()
    total_operadores = df_filtrado['Operadores (#)'].sum()
    qtd_meses = df_filtrado['Mês_dt'].nunique()
    media_mensal = (total_massa / qtd_meses) if qtd_meses > 0 else 0
    produtividade = (total_massa / total_operadores) if total_operadores > 0 else 0

    st.subheader("Indicadores de Desempenho do Cronograma")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Massa Total Planejada", f"{total_massa:,.0f} t".replace(",", "."))
    kpi2.metric("Operadores Estimados", f"{total_operadores:,.1f} op".replace(".", ","))
    kpi3.metric("Média Mensal Planejada", f"{media_mensal:,.0f} t/mês".replace(",", "."))
    kpi4.metric("Produtividade Média", f"{produtividade:,.1f} t/op".replace(".", ","))

    st.divider()

    # 2. GRÁFICOS VISUAIS
    st.subheader("Análise Cronológica e Geográfica")
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        df_mensal = df_filtrado.groupby(['Mês_dt', 'Mês_Label'], as_index=False).agg({
            'Massa (t)': 'sum',
            'Operadores (#)': 'sum',
            'UF': lambda ufs: ", ".join(sorted(set(ufs)))
        }).sort_values('Mês_dt')
        
        # Rótulo do Eixo X com mm/yy e UFs na linha abaixo
        df_mensal['Eixo_X_Label'] = df_mensal.apply(lambda r: f"{r['Mês_Label']}<br>({r['UF']})", axis=1)

        fig_cron_mes = go.Figure()
        fig_cron_mes.add_trace(go.Bar(
            x=df_mensal['Eixo_X_Label'], y=df_mensal['Massa (t)'],
            name="Massa (t)", marker_color=PALETA_EURECICLO['Compensada'],
            hovertemplate="%{x}: %{y:,.0f} t<extra></extra>"
        ))
        fig_cron_mes.add_trace(go.Scatter(
            x=df_mensal['Eixo_X_Label'], y=df_mensal['Operadores (#)'],
            name="Operadores (#)", yaxis="y2", mode="lines+markers+text",
            text=[f"{v:,.1f}".replace(".", ",") for v in df_mensal['Operadores (#)']],
            textposition="top center", line=dict(color=PALETA_EURECICLO['Projetada'], width=3)
        ))
        fig_cron_mes.update_layout(
            title="Evolução Mensal de Massa (t) e Operadores (#)",
            separators=".,",
            xaxis=dict(tickangle=-90, type='category'),
            yaxis=dict(title="Massa (t)", tickformat=",.0f"),
            yaxis2=dict(title="Operadores (#)", overlaying="y", side="right", showgrid=False),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family="Inter, sans-serif")
        )
        st.plotly_chart(fig_cron_mes, use_container_width=True)

    with col_g2:
        df_uf = df_filtrado.groupby('UF', as_index=False)['Massa (t)'].sum().sort_values('Massa (t)', ascending=False)
        fig_cron_uf = px.bar(
            df_uf, x='UF', y='Massa (t)',
            title="Massa Planejada por Estado (UF)",
            color='Massa (t)',
            color_continuous_scale=PALETA_EURECICLO['Verde_Escala']
        )
        fig_cron_uf.update_traces(texttemplate='%{y:,.0f}', textposition='outside')
        fig_cron_uf.update_layout(
            separators=".,", yaxis_tickformat=",.0f", 
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif")
        )
        st.plotly_chart(fig_cron_uf, use_container_width=True)

    # 3. TABELA DETALHADA DE CONSULTA DO CRONOGRAMA
    def formatar_numero_br(v):
        try: return f"{v:,.0f}".replace(",", ".")
        except: return v

    with st.expander("Ver Tabela de Dados do Cronograma", expanded=True):
        st.dataframe(df_filtrado[['UF', 'Mês_Label', 'Massa (t)', 'Operadores (#)']].style.format({
            'Massa (t)': formatar_numero_br,
            'Operadores (#)': lambda v: f"{v:,.1f}".replace(".", ",")
        }), use_container_width=True)

# ==========================================
# ROTEAMENTO DE PÁGINAS
# ==========================================
if pagina_selecionada == "📊 Visão de Demanda":
    renderizar_visao_demanda()
elif pagina_selecionada == "🛡️ Visão de Cobertura":
    renderizar_visao_cobertura()
elif pagina_selecionada == "📅 Cronograma 2S26":
    renderizar_cronograma_2s26()
