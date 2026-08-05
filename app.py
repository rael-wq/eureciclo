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
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

@st.cache_data(ttl=600)
def carregar_dados_cobertura():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Lê a aba "Cobertura / SKU (total)" pulando 17 linhas (início na linha 18 / célula B18)
    df_raw = conn.read(worksheet="Cobertura / SKU (total)", skiprows=17)
    
    # Isola a partir da coluna B (se houver SKU ou coluna similar)
    if 'SKU' in df_raw.columns:
        idx_sku = df_raw.columns.get_loc('SKU')
        df = df_raw.iloc[:, idx_sku:].copy()
    else:
        df = df_raw.iloc[:, 1:].copy() if df_raw.shape[1] > 1 else df_raw.copy()
        
    df.columns = [str(col).replace('.1', '').strip() for col in df.columns]
    
    # Limpeza de linhas vazias
    col_referencia = 'SKU' if 'SKU' in df.columns else df.columns[0]
    df = df.dropna(subset=[col_referencia])
    
    # Conversão de colunas numéricas
    for col in df.columns:
        if col not in ['SKU', 'UF', 'material', 'Ano Base', 'Categoria', 'Status']:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
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
        
        # 1. UF: MANTIDO NA POSIÇÃO ANTERIOR (COLUNAS VERTICAIS EMPILHADAS)
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
        st.error(f"Erro ao carregar dados de Cobertura: {e}")
        return

    st.title("🛡️ Visão Gerencial - Cobertura de Estoque")
    st.markdown("Análise estratégica da relação entre Estoque Disponível e Demanda por SKU.")

    st.sidebar.header("Filtros de Cobertura")
    
    # Mapeamento dinâmico de colunas
    col_ano = 'Ano Base' if 'Ano Base' in df.columns else None
    col_uf = 'UF' if 'UF' in df.columns else None
    col_mat = 'material' if 'material' in df.columns else ('Material' if 'Material' in df.columns else None)
    col_sku = 'SKU' if 'SKU' in df.columns else df.columns[0]

    ano_selecionado = st.sidebar.multiselect("Ano Base", sorted(df[col_ano].dropna().astype(str).unique()), key="cob_ano") if col_ano else []
    uf_selecionada = st.sidebar.multiselect("Estado (UF)", sorted(df[col_uf].dropna().unique()), key="cob_uf") if col_uf else []
    material_selecionado = st.sidebar.multiselect("Material", sorted(df[col_mat].dropna().unique()), key="cob_mat") if col_mat else []

    df_filtrado = df.copy()
    if ano_selecionado and col_ano:
        df_filtrado = df_filtrado[df_filtrado[col_ano].astype(str).isin(ano_selecionado)]
    if uf_selecionada and col_uf:
        df_filtrado = df_filtrado[df_filtrado[col_uf].isin(uf_selecionada)]
    if material_selecionado and col_mat:
        df_filtrado = df_filtrado[df_filtrado[col_mat].isin(material_selecionado)]

    st.sidebar.divider()
    if st.sidebar.button("🔄 Atualizar Dados", key="cob_reload"):
        st.cache_data.clear()
        st.rerun()

    # Identificação flexível de colunas de métrica na aba Cobertura
    col_estoque = next((c for c in df.columns if 'estoque' in c.lower() or 'saldo' in c.lower()), None)
    col_demanda = next((c for c in df.columns if 'demanda' in c.lower() or 'projetada' in c.lower()), None)
    col_cobertura = next((c for c in df.columns if 'cobertura' in c.lower() or '%' in c.lower()), None)

    total_estoque = df_filtrado[col_estoque].sum() if col_estoque else 0
    total_demanda = df_filtrado[col_demanda].sum() if col_demanda else 0
    
    if col_cobertura:
        cobertura_media = df_filtrado[col_cobertura].mean()
    else:
        cobertura_media = (total_estoque / total_demanda * 100) if total_demanda > 0 else 0

    saldo_sobra = total_estoque - total_demanda

    st.subheader("Indicadores Chave de Cobertura (KPIs)")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Estoque Total", f"{total_estoque:,.0f}".replace(",", "."))
    kpi2.metric("Demanda Projetada", f"{total_demanda:,.0f}".replace(",", "."))
    kpi3.metric("Cobertura Geral", f"{cobertura_media:.1f}%".replace(".", ","))
    kpi4.metric("Saldo / Sobra", f"{saldo_sobra:,.0f}".replace(",", "."), delta="Sobra" if saldo_sobra >= 0 else "Déficit")

    st.divider()

    st.subheader("Análise Visual de Cobertura")
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        if col_uf and col_estoque:
            df_uf_cob = df_filtrado.groupby(col_uf, as_index=False)[col_estoque].sum().sort_values(col_estoque, ascending=False)
            fig_uf_cob = px.bar(df_uf_cob, x=col_uf, y=col_estoque, title="Estoque Disponível por UF", color=col_estoque, color_continuous_scale="Greens")
            fig_uf_cob.update_traces(texttemplate='%{y:,.0f}', textposition='outside')
            fig_uf_cob.update_layout(separators=".,", yaxis_tickformat=",.0f")
            st.plotly_chart(fig_uf_cob, use_container_width=True)

    with col_g2:
        if col_mat and col_cobertura:
            df_mat_cob = df_filtrado.groupby(col_mat, as_index=False)[col_cobertura].mean()
            fig_mat_cob = px.pie(df_mat_cob, values=col_cobertura, names=col_mat, title="Cobertura Média (%) por Material", hole=0.4)
            fig_mat_cob.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_mat_cob, use_container_width=True)

    st.markdown("#### Balanço de Cobertura por SKU (Top 20 + Demais SKUs)")
    
    if col_sku and col_estoque and col_demanda:
        df_sku_cob = df_filtrado.groupby(col_sku, as_index=False)[[col_estoque, col_demanda]].sum()
        df_sku_cob['Total_Volume'] = df_sku_cob[col_estoque] + df_sku_cob[col_demanda]
        df_sku_cob = df_sku_cob.sort_values(by='Total_Volume', ascending=False)

        if len(df_sku_cob) > 20:
            df_top20 = df_sku_cob.iloc[:20].copy()
            df_demais = df_sku_cob.iloc[20:].copy()
            dict_demais = {
                col_sku: 'Demais SKUs',
                col_estoque: df_demais[col_estoque].sum(),
                col_demanda: df_demais[col_demanda].sum(),
                'Total_Volume': df_demais['Total_Volume'].sum()
            }
            df_final_sku_cob = pd.concat([df_top20, pd.DataFrame([dict_demais])], ignore_index=True)
        else:
            df_final_sku_cob = df_sku_cob.copy()

        df_final_sku_cob[col_sku] = df_final_sku_cob[col_sku].astype(str)
        ordem_y_cob = df_final_sku_cob[col_sku].tolist()[::-1]

        df_sku_melted_cob = df_final_sku_cob.melt(
            id_vars=[col_sku], 
            value_vars=[col_estoque, col_demanda], 
            var_name='Métrica', value_name='Valor'
        )

        fig_comp_sku_cob = px.bar(
            df_sku_melted_cob, x='Valor', y=col_sku, color='Métrica', orientation='h',
            title="Comparativo Estoque vs Demanda por SKU",
            color_discrete_map={col_estoque: '#2ecc71', col_demanda: '#e74c3c'},
            barmode='group'
        )
        fig_comp_sku_cob.update_traces(hovertemplate="%{data.name}: %{x:,.0f}<extra></extra>")
        fig_comp_sku_cob.update_layout(
            separators=".,", xaxis_tickformat=",.0f",
            yaxis={'type': 'category', 'categoryorder': 'array', 'categoryarray': ordem_y_cob}, height=600
        )
        st.plotly_chart(fig_comp_sku_cob, use_container_width=True)

    with st.expander("Ver Dados Detalhados de Cobertura"):
        def formatar_num(v):
            try: return f"{v:,.0f}".replace(",", ".")
            except: return v
        
        cols_num = df_filtrado.select_dtypes(include=['float64', 'int64']).columns
        dict_fmt = {c: formatar_num for c in cols_num}
        st.dataframe(df_filtrado.style.format(dict_fmt), use_container_width=True)

# ==========================================
# ROTAEAMENTO DE PÁGINAS
# ==========================================
if pagina_selecionada == "📊 Visão de Demanda":
    renderizar_visao_demanda()
elif pagina_selecionada == "🛡️ Visão de Cobertura":
    renderizar_visao_cobertura()
