import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from streamlit_oauth import OAuth2Component
from streamlit_gsheets import GSheetsConnection

# ==========================================
# CONFIGURAÇÃO GERAL E TEMA INSTITUCIONAL EURECICLO
# ==========================================
st.set_page_config(
    page_title="Dashboard Executivo - eureciclo", 
    layout="wide", 
    page_icon="♻️",
    initial_sidebar_state="expanded"
)

# Estilização CSS inspirada no portal principal da eureciclo (eureciclo.com.br)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

    /* Forçar Tema Light Institucional */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
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

    /* Dividers */
    hr {
        border-top: 1px solid #E2E8F0 !important;
    }
    </style>
""", unsafe_allow_html=True)

COLUNAS_NUMERICAS_DEMANDA = ['Compensada', 'Em Aberto', 'Total Contratada', 'Projetada', 'Em aberto + Projetada', 'DEMANDA TOTAL']

# Colunas numéricas da aba Cobertura (sem colunas de Oferta para exibição limpa)
COLUNAS_EXIBICAO_COBERTURA = [
    'UF', 'material', 'SKU', 'Ano Base',
    'Demanda Atual', 'Demanda Projetada', 'Demanda TOTAL', 
    'Quebra Atual', 'Quebra Projetada', 'Quebra Projetada c/ pipe Ops'
]

COLUNAS_NUMERICAS_COBERTURA = [
    'Demanda Atual', 'Demanda Projetada', 'Demanda TOTAL', 
    'Quebra Atual', 'Quebra Projetada', 'Quebra Projetada c/ pipe Ops'
]

# Paleta de Cores do Portal eureciclo
PALETA_EURECICLO = {
    'Compensada': '#00A859',        # Verde eureciclo
    'Em Aberto': '#FF5A5F',         # Coral
    'Projetada': '#0284C7',         # Azul Oceano
    'Quebra Atual': '#E53E3E',      # Vermelho Alerta
    'Quebra Projetada': '#DD6B20',  # Laranja Institucional
    'Quebra Projetada c/ pipe Ops': '#D69E2E', # Âmbar
    'Verde_Escala': ['#E6F4EA', '#A3E0BF', '#42C785', '#00A859', '#007A40']
}

# Logo Oficial eureciclo
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

# Função de Mapa de Calor customizada (Sem dependência de matplotlib)
def colorir_celula_quebra(val):
    if not isinstance(val, (int, float)) or pd.isna(val):
        return ''
    if val < 0:
        # Intensidade do vermelho baseada na escala do valor negativo
        alpha = min(abs(val) / 30000, 1.0) * 0.45 + 0.1
        return f'background-color: rgba(229, 62, 62, {alpha:.2f}); color: #1E293B;'
    elif val > 0:
        # Intensidade do azul para valores positivos
        alpha = min(val / 30000, 1.0) * 0.45 + 0.1
        return f'background-color: rgba(2, 132, 199, {alpha:.2f}); color: #1E293B;'
    else:
        return 'background-color: #FFFFFF; color: #A0AEC0;'

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

    # Exibição do logo no topo antes da área de login
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
# LOGO E NAVEGAÇÃO NO MENU LATERAL (ESQUERDA)
# ==========================================
st.sidebar.image(LOGO_EURECICLO_URL, width=170)
st.sidebar.markdown("### Gestão de Operações")
st.sidebar.success(f"Logado como:\n{st.session_state['user_email']}")

if st.sidebar.button("Sair (Logout)"):
    del st.session_state["user_email"]
    st.rerun()
st.sidebar.divider()

pagina_selecionada = st.sidebar.radio(
    "Navegação do Dashboard:",
    ["📊 Visão de Demanda", "🛡️ Visão de Cobertura"]
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
            title="Distribuição da Demanda por Material", hole=0.4,
            color_discrete_sequence=['#00A859', '#0284C7', '#FF5A5F', '#DD6B20']
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

    df_filtrado = df.copy()
    if ano_selecionado:
        df_filtrado = df_filtrado[df_filtrado['Ano Base'].astype(str).isin(ano_selecionado)]
    if uf_selecionada:
        df_filtrado = df_filtrado[df_filtrado['UF'].isin(uf_selecionada)]
    if material_selecionado:
        df_filtrado = df_filtrado[df_filtrado['material'].isin(material_selecionado)]

    st.sidebar.divider()
    if st.sidebar.button("🔄 Atualizar Dados", key="cob_reload"):
        st.cache_data.clear()
        st.rerun()

    # CÁLCULOS DOS KPIs E % DE QUEBRAS EM RELAÇÃO À DEMANDA TOTAL
    total_demanda_cob = df_filtrado['Demanda TOTAL'].sum()
    total_quebra_atual = df_filtrado['Quebra Atual'].sum()
    total_quebra_proj = df_filtrado['Quebra Projetada'].sum()
    total_quebra_pipe = df_filtrado['Quebra Projetada c/ pipe Ops'].sum()

    pct_quebra_atual = (total_quebra_atual / total_demanda_cob * 100) if total_demanda_cob > 0 else 0
    pct_quebra_proj = (total_quebra_proj / total_demanda_cob * 100) if total_demanda_cob > 0 else 0
    pct_quebra_pipe = (total_quebra_pipe / total_demanda_cob * 100) if total_demanda_cob > 0 else 0

    st.subheader("Indicadores Chave de Quebra (KPIs)")
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

    st.divider()

    # TABELAS PIVOTEADAS DAS 3 QUEBRAS (UF x MATERIAL) COM MAPA DE CALOR CUSTOMIZADO
    st.subheader("Análise Detalhada das Quebras por UF e Material")

    def formatar_numero_br(v):
        try: return f"{v:,.0f}".replace(",", ".")
        except: return v

    def criar_tabela_pivot_quebra(coluna_metrica, titulo):
        st.markdown(f"##### {titulo}")
        if coluna_metrica in df_filtrado.columns and 'UF' in df_filtrado.columns and 'material' in df_filtrado.columns:
            pivot_df = df_filtrado.pivot_table(
                index='UF', 
                columns='material', 
                values=coluna_metrica, 
                aggfunc='sum', 
                fill_value=0
            )
            # Adiciona coluna de Total
            pivot_df['Total'] = pivot_df.sum(axis=1)
            
            # Formatação numérica BR
            fmt_dict = {c: formatar_numero_br for c in pivot_df.columns}
            
            # Aplica estilização de mapa de calor nativa sem dependência do matplotlib
            styler = pivot_df.style.format(fmt_dict).applymap(colorir_celula_quebra)
            
            st.dataframe(styler, use_container_width=True)
        else:
            st.warning(f"Não foi possível gerar a tabela de {titulo}.")

    # Exibição das 3 tabelas de quebra com gradiente CSS
    criar_tabela_pivot_quebra('Quebra Atual', '1. Quebra Atual por UF x Material')
    criar_tabela_pivot_quebra('Quebra Projetada', '2. Quebra Projetada por UF x Material')
    criar_tabela_pivot_quebra('Quebra Projetada c/ pipe Ops', '3. Quebra Projetada c/ Pipe Ops por UF x Material')

    st.divider()

    st.markdown("#### Composição das Quebras por UF e SKU")
    opcoes_quebra = ['Quebra Atual', 'Quebra Projetada', 'Quebra Projetada c/ pipe Ops']
    quebras_grafico = st.multiselect("Selecione os Tipos de Quebra para visualizar nos gráficos:", options=opcoes_quebra, default=opcoes_quebra, key="cob_multi")

    if quebras_grafico:
        mapa_cores_quebra = {
            'Quebra Atual': PALETA_EURECICLO['Quebra Atual'], 
            'Quebra Projetada': PALETA_EURECICLO['Quebra Projetada'], 
            'Quebra Projetada c/ pipe Ops': PALETA_EURECICLO['Quebra Projetada c/ pipe Ops']
        }

        # 1. COMPOSIÇÃO DE QUEBRA POR UF (COLUNAS VERTICAIS EMPILHADAS)
        df_composicao_uf_quebra = df_filtrado.groupby('UF', as_index=False)[quebras_grafico].sum()
        df_composicao_uf_quebra['UF'] = df_composicao_uf_quebra['UF'].astype(str)
        df_uf_melted_quebra = df_composicao_uf_quebra.melt(id_vars=['UF'], value_vars=quebras_grafico, var_name='Tipo de Quebra', value_name='Valor')

        fig_comp_uf_quebra = px.bar(
            df_uf_melted_quebra, x='UF', y='Valor', color='Tipo de Quebra',
            title="Composição da Quebra por UF", color_discrete_map=mapa_cores_quebra, barmode='stack'
        )
        fig_comp_uf_quebra.update_traces(hovertemplate="%{data.name}: %{y:,.0f}<extra></extra>")
        fig_comp_uf_quebra.update_layout(
            separators=".,", yaxis_tickformat=",.0f", 
            xaxis={'type': 'category', 'categoryorder': 'total ascending'},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif")
        )
        st.plotly_chart(fig_comp_uf_quebra, use_container_width=True)

        # 2. COMPOSIÇÃO DE QUEBRA POR SKU (BARRAS HORIZONTAIS EMPILHADAS TOP 20 + DEMAIS SKUS)
        df_composicao_sku_quebra = df_filtrado.groupby('SKU', as_index=False)[quebras_grafico].sum()
        df_composicao_sku_quebra['Total_Quebra'] = df_composicao_sku_quebra[quebras_grafico].sum(axis=1)
        df_composicao_sku_quebra = df_composicao_sku_quebra.sort_values(by='Total_Quebra', ascending=True)

        if len(df_composicao_sku_quebra) > 20:
            df_top20_quebra = df_composicao_sku_quebra.iloc[:20].copy()
            df_demais_quebra = df_composicao_sku_quebra.iloc[20:].copy()
            dict_demais_quebra = {'SKU': 'Demais SKUs', 'Total_Quebra': df_demais_quebra['Total_Quebra'].sum()}
            for q_col in quebras_grafico:
                dict_demais_quebra[q_col] = df_demais_quebra[q_col].sum()
            df_final_sku_quebra = pd.concat([df_top20_quebra, pd.DataFrame([dict_demais_quebra])], ignore_index=True)
        else:
            df_final_sku_quebra = df_composicao_sku_quebra.copy()

        df_final_sku_quebra['SKU'] = df_final_sku_quebra['SKU'].astype(str)
        ordem_y_quebra = df_final_sku_quebra['SKU'].tolist()[::-1]
        df_sku_melted_quebra = df_final_sku_quebra.melt(id_vars=['SKU'], value_vars=quebras_grafico, var_name='Tipo de Quebra', value_name='Valor')

        fig_comp_sku_quebra = px.bar(
            df_sku_melted_quebra, x='Valor', y='SKU', color='Tipo de Quebra', orientation='h',
            title="Composição da Quebra por SKU (Top 20 + Demais SKUs)", color_discrete_map=mapa_cores_quebra, barmode='stack'
        )
        fig_comp_sku_quebra.update_traces(hovertemplate="%{data.name}: %{x:,.0f}<extra></extra>")
        fig_comp_sku_quebra.update_layout(
            separators=".,", xaxis_tickformat=",.0f",
            yaxis={'type': 'category', 'categoryorder': 'array', 'categoryarray': ordem_y_quebra}, height=600,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif")
        )
        st.plotly_chart(fig_comp_sku_quebra, use_container_width=True)

    # TABELA DETALHADA COBERTURA / QUEBRAS (SEM COLUNAS DE OFERTA)
    with st.expander("Ver Dados Detalhados de Quebras"):
        cols_presentes = [c for c in COLUNAS_EXIBICAO_COBERTURA if c in df_filtrado.columns]
        df_tabela_cob = df_filtrado[cols_presentes].copy()

        formato_dict_cob = {col: formatar_numero_br for col in COLUNAS_NUMERICAS_COBERTURA if col in df_tabela_cob.columns}
        st.dataframe(df_tabela_cob.style.format(formato_dict_cob), use_container_width=True)

# ==========================================
# ROTEAMENTO DE PÁGINAS
# ==========================================
if pagina_selecionada == "📊 Visão de Demanda":
    renderizar_visao_demanda()
elif pagina_selecionada == "🛡️ Visão de Cobertura":
    renderizar_visao_cobertura()
