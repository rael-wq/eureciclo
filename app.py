import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da Página
st.set_page_config(page_title="Visão Gerencial - Demanda", layout="wide")

# ==========================================
# 1. AUTENTICAÇÃO GOOGLE (@nhecotech.com)
# ==========================================
# Nota: Em produção, utilize pacotes como 'streamlit-google-auth' para gerar o botão de login real via OAuth2.
def check_login():
    """ 
    Simulação da lógica de verificação de login.
    O sistema checaria o domínio do e-mail autenticado pelo Google.
    """
    user_email = "usuario@nhecotech.com" # Exemplo do retorno do Google Auth
    if user_email.endswith("@nhecotech.com"):
        return True
    return False

if not check_login():
    st.error("🔒 Acesso restrito. Faça login usando sua conta Google corporativa @nhecotech.com.")
    st.stop() # Interrompe a renderização do resto da página


# ==========================================
# 2. CARREGAMENTO DOS DADOS (Tempo Real)
# ==========================================
# O "ttl=60" faz com que o cache expire em 1 minuto, recarregando os dados novos da planilha.
@st.cache_data(ttl=60)
def load_data():
    # Para leitura em tempo real da planilha, insira o link de exportação CSV do Google Sheets
    # ou conecte a API. Aqui leremos o arquivo CSV atual para montar a estrutura.
    df = pd.read_csv('OPS_Cobertura_de_Estoque_análi_Demanda_Visão_Gerencial.csv')
    
    # Tratamento de dados numéricos (remove vírgulas indevidas e força conversão)
    colunas_numericas = ['Compensada', 'Em Aberto', 'Total Contratada', 'Projetada', 'Em aberto + Projetada', 'DEMANDA TOTAL']
    for col in colunas_numericas:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
    
    return df

df = load_data()


# ==========================================
# 3. INTERFACE E DASHBOARD
# ==========================================
st.title("📊 Visão Gerencial - Demanda de Estoque")
st.markdown("Visão executiva da aba *[Demanda] Visão Gerencial*. Atualização sincronizada com a planilha.")

# Filtros Laterais
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg", width=50)
st.sidebar.header("Filtros de Análise")
ano_selecionado = st.sidebar.multiselect("Ano Base", sorted(df['Ano Base'].dropna().astype(str).unique()))
uf_selecionada = st.sidebar.multiselect("Estado (UF)", sorted(df['UF'].dropna().unique()))
material_selecionado = st.sidebar.multiselect("Material", sorted(df['material'].dropna().unique()))

# Aplicação dos Filtros
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

kpi1.metric("Demanda Total", f"{total_demanda:,.0f}")
kpi2.metric("Total Contratada", f"{total_contratada:,.0f}")
kpi3.metric("Demanda Projetada", f"{total_projetada:,.0f}")
kpi4.metric("Em Aberto", f"{total_em_aberto:,.0f}")

st.divider()

# --- SEÇÃO DE GRÁFICOS ---
st.subheader("Análise Visual")
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    # 1. Gráfico de Demanda por UF
    df_uf = df_filtrado.groupby('UF', as_index=False)['DEMANDA TOTAL'].sum().sort_values('DEMANDA TOTAL', ascending=False)
    fig_uf = px.bar(df_uf, x='UF', y='DEMANDA TOTAL', 
                    title="Demanda Total por UF", 
                    text_auto='.2s', color='DEMANDA TOTAL', color_continuous_scale="Blues")
    st.plotly_chart(fig_uf, use_container_width=True)

with col_graf2:
    # 2. Gráfico de Distribuição por Material
    df_mat = df_filtrado.groupby('material', as_index=False)['DEMANDA TOTAL'].sum()
    fig_mat = px.pie(df_mat, values='DEMANDA TOTAL', names='material', 
                     title="Distribuição da Demanda por Material", hole=0.4)
    fig_mat.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_mat, use_container_width=True)

# 3. Composição da Demanda (Contratada vs Projetada)
st.markdown("#### Composição do Estoque por UF")
df_composicao = df_filtrado.groupby('UF', as_index=False)[['Compensada', 'Em Aberto', 'Projetada']].sum()
fig_comp = px.bar(df_composicao, x='UF', y=['Compensada', 'Em Aberto', 'Projetada'],
                  title="Composição da Demanda: Compensada vs Em Aberto vs Projetada",
                  barmode='stack', color_discrete_sequence=['#2ecc71', '#e74c3c', '#3498db'])
st.plotly_chart(fig_comp, use_container_width=True)

# --- TABELA DE DADOS ---
with st.expander("Ver Dados Detalhados"):
    st.dataframe(df_filtrado, use_container_width=True)