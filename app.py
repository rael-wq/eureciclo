import streamlit as st
import pandas as pd
import plotly.express as px

# ==========================================
# CONFIGURAÇÃO GERAL
# ==========================================
st.set_page_config(page_title="Visão Gerencial - Demanda", layout="wide")

def check_login():
    return True # Temporariamente liberado para garantir o funcionamento visual

if not check_login():
    st.error("🔒 Acesso restrito. Faça login usando sua conta corporativa @nhecotech.com.")
    st.stop()

# Lista de colunas numéricas transformada em variável global 
# para facilitar o reuso tanto no tratamento quanto na formatação visual
COLUNAS_NUMERICAS = ['Compensada', 'Em Aberto', 'Total Contratada', 'Projetada', 'Em aberto + Projetada', 'DEMANDA TOTAL']

# ==========================================
# CARREGAMENTO E TRATAMENTO DOS DADOS
# ==========================================
@st.cache_data(ttl=60)
def carregar_dados_finais():
    arquivo = 'OPS_Cobertura_de_Estoque_análi_Demanda_Visão_Gerencial.csv'
    
    # 1. Pula o cabeçalho sujo do CSV
    df_raw = pd.read_csv(arquivo, sep=',', skiprows=4)
    
    # 2. Isola a tabela detalhada (Começa a partir da coluna SKU)
    idx_sku = df_raw.columns.get_loc('SKU')
    df = df_raw.iloc[:, idx_sku:].copy()
    
    # 3. Limpa os nomes das colunas (tira '.1' gerado por colunas duplicadas)
    df.columns = [col.replace('.1', '').strip() for col in df.columns]
    
    # 4. Remove linhas vazias no final
    df = df.dropna(subset=['SKU'])
    
    # 5. Converte os números (Tira pontos de milhar para o Python conseguir somar nos bastidores)
    for col in COLUNAS_NUMERICAS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace('.', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# Executa a função
df = carregar_dados_finais()

# ==========================================
# INTERFACE E DASHBOARD
# ==========================================
st.title("📊 Visão Gerencial - Demanda de Estoque")
st.markdown("Visão executiva detalhada por SKU com filtros dinâmicos.")

# --- FILTROS LATERAIS ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg", width=50)
st.sidebar.header("Filtros de Análise")

ano_selecionado = st.sidebar.multiselect("Ano Base", sorted(df['Ano Base'].dropna().astype(str).unique()))
uf_selecionada = st.sidebar.multiselect("Estado (UF)", sorted(df['UF'].dropna().unique()))
material_selecionado = st.sidebar.multiselect("Material", sorted(df['material'].dropna().unique()))

# Aplica os filtros na base de dados
df_filtrado = df.copy()
if ano_selecionado:
    df_filtrado = df_filtrado[df_filtrado['Ano Base'].astype(str).isin(ano_selecionado)]
if uf_selecionada:
    df_filtrado = df_filtrado[df_filtrado['UF'].isin(uf_selecionada)]
if material_selecionado:
    df_filtrado = df_filtrado[df_filtrado['material'].isin(material_selecionado)]

# --- SEÇÃO DE KPIs ---
st.subheader("Indicadores Chave (KPIs)")
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

total_demanda = df_filtrado['DEMANDA TOTAL'].sum()
total_contratada = df_filtrado['Total Contratada'].sum()
total_projetada = df_filtrado['Projetada'].sum()
total_em_aberto = df_filtrado['Em Aberto'].sum()

# Mostra os KPIs formatados com separador de milhar
kpi1.metric("Demanda Total", f"{total_demanda:,.0f}".replace(",", "."))
kpi2.metric("Total Contratada", f"{total_contratada:,.0f}".replace(",", "."))
kpi3.metric("Demanda Projetada", f"{total_projetada:,.0f}".replace(",", "."))
kpi4.metric("Em Aberto", f"{total_em_aberto:,.0f}".replace(",", "."))

st.divider()

# --- SEÇÃO DE GRÁFICOS ---
st.subheader("Análise Visual")
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    df_uf = df_filtrado.groupby('UF', as_index=False)['DEMANDA TOTAL'].sum().sort_values('DEMANDA TOTAL', ascending=False)
    fig_uf = px.bar(df_uf, x='UF', y='DEMANDA TOTAL', 
                    title="Demanda Total por UF", 
                    color='DEMANDA TOTAL', color_continuous_scale="Blues")
    # Força a exibição de milhares com ponto no gráfico de barras
    fig_uf.update_traces(texttemplate='%{y:,.0f}', textposition='outside')
    fig_uf.update_layout(separators=".,", yaxis_tickformat=",.0f")
    st.plotly_chart(fig_uf, use_container_width=True)

with col_graf2:
    df_mat = df_filtrado.groupby('material', as_index=False)['DEMANDA TOTAL'].sum()
    fig_mat = px.pie(df_mat, values='DEMANDA TOTAL', names='material', 
                     title="Distribuição da Demanda por Material", hole=0.4)
    # Ajusta os rótulos que aparecem ao passar o mouse (hover)
    fig_mat.update_traces(textposition='inside', textinfo='percent+label', hovertemplate="%{label}: %{value:,.0f}<extra></extra>")
    fig_mat.update_layout(separators=".,")
    st.plotly_chart(fig_mat, use_container_width=True)

st.markdown("#### Composição do Estoque por UF")
df_composicao = df_filtrado.groupby('UF', as_index=False)[['Compensada', 'Em Aberto', 'Projetada']].sum()
fig_comp = px.bar(df_composicao, x='UF', y=['Compensada', 'Em Aberto', 'Projetada'],
                  title="Composição da Demanda: Compensada vs Em Aberto vs Projetada",
                  barmode='stack', color_discrete_sequence=['#2ecc71', '#e74c3c', '#3498db'])

# Ajusta formatação e tooltip no gráfico empilhado
fig_comp.update_traces(hovertemplate="%{data.name}: %{y:,.0f}<extra></extra>")
fig_comp.update_layout(separators=".,", yaxis_tickformat=",.0f")
st.plotly_chart(fig_comp, use_container_width=True)

# --- TABELA DE DADOS ---
with st.expander("Ver Dados Detalhados"):
    # Cria uma cópia puramente visual para não estragar a matemática dos filtros
    df_exibicao = df_filtrado.copy()
    
    # Aplica o formato de "1.000.000" para cada coluna da lista que contém números
    for col in COLUNAS_NUMERICAS:
        if col in df_exibicao.columns:
            df_exibicao[col] = df_exibicao[col].apply(lambda x: f"{x:,.0f}".replace(",", "."))
            
    st.dataframe(df_exibicao, use_container_width=True)
