import streamlit as st
import pandas as pd
import numpy as np
import os
import time
from io import BytesIO
from datetime import date
from sqlalchemy import create_engine, text
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gestão de OKR", layout="wide")

# --- DEFINIÇÃO DE CORES ---
CORES_STATUS = {
    "Concluído": "#bef533",
    "Em Andamento": "#7371ff",
    "Pausado": "#ffd166",
    "Não Iniciado": "#ff5a34"
}

CORES_PRAZO = {
    "Atrasado": "#ff5a34",
    "Urgente (7 dias)": "#ff9f1c",
    "Atenção (30 dias)": "#ffd166",
    "No Prazo": "#7371ff",
    "Concluído": "#e0e0e0",
    "Sem Prazo": "#f0f2f6"
}

# --- 2. CONEXÃO COM BANCO ---
@st.cache_resource
def get_engine():
    """Cache da conexão do banco"""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url), db_url
    else:
        conn = st.connection("postgresql", type="sql")
        return conn.engine, None

engine, db_url = get_engine()

# --- 3. FUNÇÕES DE BANCO DE DADOS ---
def run_query(query, params=None):
    """Executa query no banco"""
    with engine.connect() as connection:
        return pd.read_sql(query, connection, params=params)

def criar_usuario(usuario, senha, nome, cliente):
    """Cria novo usuário"""
    query_check = text("SELECT * FROM users WHERE username = :usr")
    df_check = run_query(query_check, params={'usr': usuario})
    if not df_check.empty:
        return False, "Usuário já existe."
    
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (username, password, name, cliente) VALUES (:usr, :pwd, :name, :cli)"),
            {"usr": usuario, "pwd": senha, "name": nome, "cli": cliente}
        )
    return True, "Usuário criado com sucesso!"

def carregar_dados_cliente(cliente_nome):
    """Carrega dados do cliente do banco"""
    try:
        query = text("SELECT * FROM okrs WHERE cliente = :cli ORDER BY id ASC")
        df = run_query(query, params={'cli': cliente_nome})
        
        colunas_padrao = [
            'id', 'departamento', 'objetivo', 'kr', 'tarefa', 'status',
            'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct', 'cliente'
        ]
        
        if df.empty:
            return pd.DataFrame(columns=colunas_padrao)
        
        if 'prazo' in df.columns:
            df['prazo'] = pd.to_datetime(df['prazo'], errors='coerce')
        
        cols_num = ['avanco', 'alvo', 'progresso_pct']
        for c in cols_num:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        
        if 'created_at' in df.columns:
            del df['created_at']
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def salvar_dados_no_banco(df, cliente_nome):
    """Salva DataFrame no banco (operação batch)"""
    try:
        df_save = df.copy()
        
        cols_remove = ['created_at', 'classificacao_prazo', 'mes_ano']
        for c in cols_remove:
            if c in df_save.columns:
                del df_save[c]
        
        df_save['cliente'] = cliente_nome
        
        if 'id' in df_save.columns:
            del df_save['id']
        
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM okrs WHERE cliente = :cli"),
                {"cli": cliente_nome}
            )
            df_save.to_sql('okrs', connection, if_exists='append', index=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

@st.cache_data(ttl=3600)
def gerenciar_departamentos(cliente_nome):
    """Cache de departamentos por 1 hora"""
    try:
        query = text("SELECT nome FROM departamentos WHERE cliente = :cli ORDER BY nome")
        df_dept = run_query(query, params={'cli': cliente_nome})
        return df_dept['nome'].tolist()
    except:
        return []

def adicionar_departamento(novo, cli):
    """Adiciona novo departamento"""
    if novo:
        with engine.begin() as c:
            c.execute(
                text("INSERT INTO departamentos (nome, cliente) VALUES (:n, :c)"),
                {"n": novo, "c": cli}
            )
        gerenciar_departamentos.clear()

def remover_departamento(nome, cli):
    """Remove departamento"""
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM departamentos WHERE nome = :n AND cliente = :c"),
            {"n": nome, "c": cli}
        )
    gerenciar_departamentos.clear()

# --- 4. FUNÇÕES OTIMIZADAS (VETORIZADAS) ---
def calcular_progresso_vetorizado(df):
    with np.errstate(divide='ignore', invalid='ignore'):
        alvo_safe = df['alvo'].replace(0, 1)
        progresso = df['avanco'] / alvo_safe
        progresso = np.clip(progresso, 0, 1)
    return progresso

def classificar_prazo_vetorizado(df):
    hoje = pd.to_datetime(date.today())
    classificacao = pd.Series("Sem Prazo", index=df.index)
    
    mask_concluido = df['status'] == 'Concluído'
    classificacao[mask_concluido] = "Concluído"
    
    mask_prazo = df['prazo'].notna() & ~mask_concluido
    if mask_prazo.any():
        delta = (df.loc[mask_prazo, 'prazo'] - hoje).dt.days
        classificacao.loc[mask_prazo & (delta < 0)] = "Atrasado"
        classificacao.loc[mask_prazo & (delta <= 7)] = "Urgente (7 dias)"
        classificacao.loc[mask_prazo & (delta <= 30) & (delta > 7)] = "Atenção (30 dias)"
        classificacao.loc[mask_prazo & (delta > 30)] = "No Prazo"
    
    return classificacao
