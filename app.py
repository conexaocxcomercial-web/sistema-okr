import streamlit as st
import sqlite3
import pandas as pd
import time

# --- 1. CONFIGURAÇÃO E LOGIN ---
st.set_page_config(page_title="Sistema OKR", layout="wide")

# Inicializa sessão de login se não existir
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

# Tela de Login
if not st.session_state['logado']:
    st.title("🔒 Login")
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        if usuario == "admin" and senha == "1234":
            st.session_state['logado'] = True
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos")
    st.stop() # Para a execução do código aqui se não estiver logado

# Botão de Sair na Sidebar
if st.sidebar.button("Sair"):
    st.session_state['logado'] = False
    st.rerun()

# --- 2. BANCO DE DADOS (Criação limpa) ---
conn = sqlite3.connect('okrs.db')
c = conn.cursor()

# Cria tabelas APENAS se não existirem (sem inserir dados automáticos)
c.execute('''CREATE TABLE IF NOT EXISTS departamentos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS objetivos (id INTEGER PRIMARY KEY AUTOINCREMENT, departamento_id INTEGER, descricao TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS krs (id INTEGER PRIMARY KEY AUTOINCREMENT, objetivo_id INTEGER, descricao TEXT, meta REAL, atual REAL)''')
conn.commit()

st.title("Sistema de OKRs")

# --- 3. CADASTROS (Linear) ---

st.subheader("1. Cadastrar Departamento")
novo_dep = st.text_input("Nome do Departamento")
if st.button("Salvar Departamento"):
    if novo_dep:
        c.execute("INSERT INTO departamentos (nome) VALUES (?)", (novo_dep,))
        conn.commit()
        st.success(f"Departamento '{novo_dep}' salvo!")
        time.sleep(0.5)
        st.rerun() # CORREÇÃO: Atualiza a página imediatamente
    else:
        st.warning("Digite um nome.")

st.divider()

# Carregar departamentos para o selectbox
df_deps = pd.read_sql("SELECT * FROM departamentos", conn)

if not df_deps.empty:
    st.subheader("2. Cadastrar Objetivo")
    dep_selecionado = st.selectbox("Selecione o Departamento", df_deps['nome'])
    id_dep = df_deps[df_deps['nome'] == dep_selecionado]['id'].values[0]
    
    novo_obj = st.text_input("Descrição do Objetivo")
    if st.button("Salvar Objetivo"):
        if novo_obj:
            c.execute("INSERT INTO objetivos (departamento_id, descricao) VALUES (?, ?)", (id_dep, novo_obj))
            conn.commit()
            st.success("Objetivo salvo!")
            time.sleep(0.5)
            st.rerun()

    st.divider()

    # Carregar objetivos do departamento selecionado (opcional, mas melhor carregar todos para simplificar o filtro)
    st.subheader("3. Cadastrar Key Result (KR)")
    
    # Filtra objetivos baseados no departamento selecionado acima para facilitar
    df_objs = pd.read_sql(f"SELECT * FROM objetivos WHERE departamento_id = {id_dep}", conn)
    
    if not df_objs.empty:
        obj_selecionado = st.selectbox("Vincular ao Objetivo", df_objs['descricao'])
        id_obj = df_objs[df_objs['descricao'] == obj_selecionado]['id'].values[0]
        
        c1, c2, c3 = st.columns(3)
        desc_kr = c1.text_input("Descrição do KR")
        meta_kr = c2.number_input("Meta", min_value=0.0)
        atual_kr = c3.number_input("Valor Atual", min_value=0.0)
        
        if st.button("Salvar KR"):
            c.execute("INSERT INTO krs (objetivo_id, descricao, meta, atual) VALUES (?, ?, ?, ?)", (id_obj, desc_kr, meta_kr, atual_kr))
            conn.commit()
            st.success("KR salvo!")
            time.sleep(0.5)
            st.rerun()
    else:
        st.info("Cadastre um objetivo para este departamento primeiro.")

else:
    st.info("Cadastre um departamento para começar.")

# --- 4. VISUALIZAÇÃO DOS DADOS ---
st.divider()
st.subheader("📊 Visão Geral")

query_full = '''
    SELECT 
        d.nome as Departamento,
        o.descricao as Objetivo,
        k.descricao as KR,
        k.meta as Meta,
        k.atual as Atual
    FROM krs k
    JOIN objetivos o ON k.objetivo_id = o.id
    JOIN departamentos d ON o.departamento_id = d.id
'''
df_full = pd.read_sql(query_full, conn)

if not df_full.empty:
    st.dataframe(df_full, use_container_width=True)
    
    # Exportação Simples
    csv = df_full.to_csv(index=False).encode('utf-8')
    st.download_button("Baixar Excel (CSV)", csv, "okrs.csv", "text/csv")
else:
    st.write("Nenhum KR cadastrado ainda.")

conn.close()
