import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Visão Gerencial - Demanda", layout="wide")

def check_login():
    return True # Temporariamente liberado para focarmos em arrumar os dados

if not check_login():
    st.error("🔒 Acesso restrito.")
    st.stop()

# Nome da função alterado novamente para forçar a quebra do cache
@st.cache_data(ttl=60)
def carregar_dados_seguro():
    arquivo = 'OPS_Cobertura_de_Estoque_análi_Demanda_Visão_Gerencial.csv'
    
    # 1. Pula as 4 primeiras linhas (skiprows=4) que estão sujas/vazias no CSV
    df = pd.read_csv(arquivo, sep=',', skiprows=4)
    
    # 2. Localiza a coluna 'SKU' e corta a tabela para pegar apenas os dados da direita
    if 'SKU' in df.columns:
        idx_sku = df.columns.get_loc('SKU')
        df = df.iloc[:, idx_sku:].copy()
        
        # O Pandas coloca um ".1" em nomes de colunas repetidas. Vamos limpar isso:
        df.columns = [col.replace('.1', '').strip() for col in df.columns]
    
    # 3. Remove as linhas completamente vazias que ficam no final do arquivo
    df = df.dropna(subset=['SKU'])
    
    # 4. Tratamento matemático (Remove os pontos de milhar para o Python somar corretamente)
    colunas_numericas = ['Compensada', 'Em Aberto', 'Total Contratada', 'Projetada', 'Em aberto + Projetada', 'DEMANDA TOTAL']
    
    for col in colunas_numericas:
        if col in df.columns:
            # Remove o ponto e converte o texto para número
            df[col] = df[col].astype(str).str.replace('.', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# 1. Carrega os dados
df = carregar_dados_seguro()

st.title("📊 Visão Gerencial - Demanda de Estoque")

# 2. MODO DIAGNÓSTICO: Mostra as colunas na tela para descobrirmos o problema
st.warning("⚠️ MODO DIAGNÓSTICO ATIVADO: Veja abaixo as colunas que o Streamlit encontrou no seu arquivo.")
st.write("Lista exata de colunas encontradas:", df.columns.tolist())
st.write("Total de colunas:", len(df.columns))

# 3. FILTROS (Com trava de segurança para não dar erro na tela)
st.sidebar.header("Filtros de Análise")

# Só cria o filtro se a coluna existir, senão avisa o erro
if 'Ano Base' in df.columns:
    ano_selecionado = st.sidebar.multiselect("Ano Base", sorted(df['Ano Base'].dropna().astype(str).unique()))
else:
    st.sidebar.error("❌ Coluna 'Ano Base' não encontrada!")
    ano_selecionado = []

if 'UF' in df.columns:
    uf_selecionada = st.sidebar.multiselect("Estado (UF)", sorted(df['UF'].dropna().unique()))
else:
    st.sidebar.error("❌ Coluna 'UF' não encontrada!")
    uf_selecionada = []

if 'material' in df.columns:
    material_selecionado = st.sidebar.multiselect("Material", sorted(df['material'].dropna().unique()))
else:
    material_selecionado = []

# Mostra a tabela crua para conferência
st.markdown("### Dados Carregados")
st.dataframe(df.head())
