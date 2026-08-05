import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from streamlit_oauth import OAuth2Component
from streamlit_gsheets import GSheetsConnection

# ==========================================
# CONFIGURAÇÃO GERAL
# ==========================================
st.set_page_config(page_title="Dashboard Executivo - Operações", layout="wide")

COLUNAS_NUMERICAS_DEMANDA = ['Compensada', 'Em Aberto', 'Total Contratada', 'Projetada', 'Em aberto + Projetada', 'DEMANDA TOTAL']

COLUNAS_NUMERICAS_COBERTURA = [
    'Demanda Atual', 'Demanda Projetada', 'Demanda TOTAL', 
    'Oferta Atual', 'Oferta Projetada (ativos)', 'Oferta Projetada (expansão)', 
    'Oferta Total', 'Quebra Atual', 'Quebra Projetada', 'Quebra Projetada c/ pipe Ops'
]

# ==========================================
# FUNÇÃO AUXILIAR DE TRATAMENTO NUMÉRICO
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

# ==========================================
# NAVEGAÇÃO ENTRE PÁGINAS NO MENU LATERAL
# ==========================================
st.sidebar.title("📌 Navegação")
pagina_selecionada = st.sidebar.radio(
    "Selecione a Visão:",
    ["📊 Visão de Demanda", "🛡️ Visão de Cobertura"]
)
st.sidebar.divider()

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

st.sidebar.success(f"Logado como: {st.session_state['user_email']}")
if st.sidebar.button("Sair (Logout)"):
    del st.session_state["user_email"]
    st.rerun()

# ==========================================
# CARREGAMENTO DOS DADOS (CACHE DE 10 MIN)
# ==========================================
@st.cache_data(ttl=600)
def carregar_dados_demanda():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_raw = conn.read(worksheet="[Demanda] Visão Gerencial", skiprows=4)
    
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
    # Lê a aba "Cobertura / SKU (total)" a partir do cabeçalho na célula B18 (linha 18 da planilha)
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
    st.markdown("Visão executiva detalhada por SKU com filtros dinâmicos.")

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
    demandas_grafico = st.multiselect("Selecione as Demandas:", options=opcoes_demanda, default=opcoes_demanda, key="dem_multi")

    if demandas_grafico:
        mapa_cores = {'Compensada': '#2ecc71', 'Em Aberto': '#e74c3c', 'Projetada': '#3498db'}
        
        # 1. UF: COLUNAS VERTICAIS EMPILHADAS
        df_composicao_uf = df_filtrado.groupby('UF', as_index=False)[opcoes_demanda].sum()
        df_composicao_uf['UF'] = df_composicao_uf['UF'].astype(str)
        df_uf_melted = df_composicao_uf.melt(id_vars=['UF'], value_vars=demandas_grafico, var_name='Tipo de Demanda', value_name='Valor')
        
        fig_comp_uf = px.bar(
            df_uf_melted, x='UF', y='Valor', color='Tipo de Demanda',
            title="Composição da Demanda por UF", color_discrete_map=mapa_cores, barmode='stack'
        )
        fig_comp_uf.update_traces(hovertemplate="%{data.name}: %{y:,.0f}<extra></extra>")
        fig_comp_uf.update_layout(separators=".,", yaxis_tickformat=",.0f", xaxis={'type': 'category', 'categoryorder': 'total descending'})
        st.plotly_chart(fig_comp_uf, use_container_width=True)

        # 2. SKU: BARRAS HORIZONTAIS EMPILHADAS (UM EMBAIXO DO OUTRO)
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
            yaxis={'type': 'category', 'categoryorder': 'array', 'categoryarray': ordem_y}, height=600
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
# FUNÇÃO PARA VISÃO DE COBERTURA
# ==========================================
def renderizar_visao_cobertura():
    try:
        df = carregar_dados_cobertura()
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba Cobertura / SKU (total): {e}")
        return

    st.title("🛡️ Visão Gerencial - Cobertura de Estoque")
    st.markdown("Análise detalhada de Oferta vs Demanda e Quebras por SKU (Aba B18:O450).")

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

    # CÁLCULOS DOS KPIs DE COBERTURA
    total_demanda_cob = df_filtrado['Demanda TOTAL'].sum()
    total_oferta_cob = df_filtrado['Oferta Total'].sum()
    perc_cobertura_global = (total_oferta_cob / total_demanda_cob * 100) if total_demanda_cob > 0 else 0
    total_quebra_proj = df_filtrado['Quebra Projetada'].sum()

    st.subheader("Indicadores Chave de Cobertura (KPIs)")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Demanda TOTAL", f"{total_demanda_cob:,.0f}".replace(",", "."))
    kpi2.metric("Oferta Total", f"{total_oferta_cob:,.0f}".replace(",", "."))
    kpi3.metric("Cobertura Geral", f"{perc_cobertura_global:.1f}%".replace(".", ","))
    kpi4.metric("Quebra Projetada", f"{total_quebra_proj:,.0f}".replace(",", "."), delta="Quebra" if total_quebra_proj < 0 else "OK")

    st.divider()

    # GRÁFICOS VISÃO COBERTURA
    st.subheader("Análise Visual de Oferta e Cobertura")
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        df_uf_oferta = df_filtrado.groupby('UF', as_index=False)['Oferta Total'].sum().sort_values('Oferta Total', ascending=False)
        fig_uf_oferta = px.bar(df_uf_oferta, x='UF', y='Oferta Total', title="Oferta Total por UF", color='Oferta Total', color_continuous_scale="Greens")
        fig_uf_oferta.update_traces(texttemplate='%{y:,.0f}', textposition='outside')
        fig_uf_oferta.update_layout(separators=".,", yaxis_tickformat=",.0f")
        st.plotly_chart(fig_uf_oferta, use_container_width=True)

    with col_g2:
        df_mat_oferta = df_filtrado.groupby('material', as_index=False)['Oferta Total'].sum()
        fig_mat_oferta = px.pie(df_mat_oferta, values='Oferta Total', names='material', title="Distribuição da Oferta por Material", hole=0.4)
        fig_mat_oferta.update_traces(textposition='inside', textinfo='percent+label', hovertemplate="%{label}: %{value:,.0f}<extra></extra>")
        fig_mat_oferta.update_layout(separators=".,")
        st.plotly_chart(fig_mat_oferta, use_container_width=True)

    st.markdown("#### Composição da Oferta por UF e SKU")
    opcoes_oferta = ['Oferta Atual', 'Oferta Projetada (ativos)', 'Oferta Projetada (expansão)']
    ofertas_grafico = st.multiselect("Selecione os Tipos de Oferta para visualizar nos gráficos:", options=opcoes_oferta, default=opcoes_oferta, key="cob_multi")

    if ofertas_grafico:
        mapa_cores_cobertura = {'Oferta Atual': '#2ecc71', 'Oferta Projetada (ativos)': '#3498db', 'Oferta Projetada (expansão)': '#9b59b6'}

        # 1. COMPOSIÇÃO DE OFERTA POR UF (COLUNAS VERTICAIS EMPILHADAS)
        df_composicao_uf_cob = df_filtrado.groupby('UF', as_index=False)[ofertas_grafico].sum()
        df_composicao_uf_cob['UF'] = df_composicao_uf_cob['UF'].astype(str)
        df_uf_melted_cob = df_composicao_uf_cob.melt(id_vars=['UF'], value_vars=ofertas_grafico, var_name='Tipo de Oferta', value_name='Valor')

        fig_comp_uf_cob = px.bar(
            df_uf_melted_cob, x='UF', y='Valor', color='Tipo de Oferta',
            title="Composição da Oferta por UF", color_discrete_map=mapa_cores_cobertura, barmode='stack'
        )
        fig_comp_uf_cob.update_traces(hovertemplate="%{data.name}: %{y:,.0f}<extra></extra>")
        fig_comp_uf_cob.update_layout(separators=".,", yaxis_tickformat=",.0f", xaxis={'type': 'category', 'categoryorder': 'total descending'})
        st.plotly_chart(fig_comp_uf_cob, use_container_width=True)

        # 2. COMPOSIÇÃO DE OFERTA POR SKU (BARRAS HORIZONTAIS EMPILHADAS TOP 20 + DEMAIS SKUS)
        df_composicao_sku_cob = df_filtrado.groupby('SKU', as_index=False)[ofertas_grafico + ['Oferta Total']].sum()
        df_composicao_sku_cob = df_composicao_sku_cob.sort_values(by='Oferta Total', ascending=False)

        if len(df_composicao_sku_cob) > 20:
            df_top20_cob = df_composicao_sku_cob.iloc[:20].copy()
            df_demais_cob = df_composicao_sku_cob.iloc[20:].copy()
            dict_demais_cob = {'SKU': 'Demais SKUs', 'Oferta Total': df_demais_cob['Oferta Total'].sum()}
            for o_col in ofertas_grafico:
                dict_demais_cob[o_col] = df_demais_cob[o_col].sum()
            df_final_sku_cob = pd.concat([df_top20_cob, pd.DataFrame([dict_demais_cob])], ignore_index=True)
        else:
            df_final_sku_cob = df_composicao_sku_cob.copy()

        df_final_sku_cob['SKU'] = df_final_sku_cob['SKU'].astype(str)
        ordem_y_cob = df_final_sku_cob['SKU'].tolist()[::-1]
        df_sku_melted_cob = df_final_sku_cob.melt(id_vars=['SKU'], value_vars=ofertas_grafico, var_name='Tipo de Oferta', value_name='Valor')

        fig_comp_sku_cob = px.bar(
            df_sku_melted_cob, x='Valor', y='SKU', color='Tipo de Oferta', orientation='h',
            title="Composição da Oferta por SKU (Top 20 + Demais SKUs)", color_discrete_map=mapa_cores_cobertura, barmode='stack'
        )
        fig_comp_sku_cob.update_traces(hovertemplate="%{data.name}: %{x:,.0f}<extra></extra>")
        fig_comp_sku_cob.update_layout(
            separators=".,", xaxis_tickformat=",.0f",
            yaxis={'type': 'category', 'categoryorder': 'array', 'categoryarray': ordem_y_cob}, height=600
        )
        st.plotly_chart(fig_comp_sku_cob, use_container_width=True)

    # TABELA DETALHADA COBERTURA
    with st.expander("Ver Dados Detalhados de Cobertura"):
        df_tabela_cob = df_filtrado.copy()
        
        # Cálculo de colunas percentuais de cobertura e quebra
        df_tabela_cob['% Cobertura'] = (df_tabela_cob['Oferta Total'] / df_tabela_cob['Demanda TOTAL']).fillna(0)
        df_tabela_cob['% Quebra Projetada'] = (df_tabela_cob['Quebra Projetada'] / df_tabela_cob['Demanda TOTAL']).fillna(0)

        def formatar_numero_br(v):
            try: return f"{v:,.0f}".replace(",", ".")
            except: return v

        def formatar_percentual(v):
            try: return f"{v * 100:.1f}%".replace(".", ",")
            except: return v

        formato_dict_cob = {col: formatar_numero_br for col in COLUNAS_NUMERICAS_COBERTURA if col in df_tabela_cob.columns}
        formato_dict_cob['% Cobertura'] = formatar_percentual
        formato_dict_cob['% Quebra Projetada'] = formatar_percentual

        st.dataframe(df_tabela_cob.style.format(formato_dict_cob), use_container_width=True)

# ==========================================
# ROTEAMENTO DE PÁGINAS
# ==========================================
if pagina_selecionada == "📊 Visão de Demanda":
    renderizar_visao_demanda()
elif pagina_selecionada == "🛡️ Visão de Cobertura":
    renderizar_visao_cobertura()
