import streamlit as st
import pandas as pd
import os
import time
from io import BytesIO
from datetime import date
from sqlalchemy import create_engine, text

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gestão de OKR", layout="wide")

# --- 2. CONEXÃO HÍBRIDA ---
db_url = os.getenv("DATABASE_URL")

if db_url:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(db_url)
    conn = engine
else:
    conn = st.connection("postgresql", type="sql")
    engine = conn.engine

# --- 3. FUNÇÕES DE BANCO DE DADOS ---

def run_query(query, params=None):
    if db_url:
        with engine.connect() as connection:
            return pd.read_sql(query, connection, params=params)
    else:
        if hasattr(query, 'text'):
            sql_str = query.text
        else:
            sql_str = str(query)
        return conn.query(sql_str, params=params, ttl=0)

def criar_usuario(usuario, senha, nome, cliente):
    # 1. Verifica se usuário já existe
    query_check = text("SELECT * FROM users WHERE username = :usr")
    df_check = run_query(query_check, params={'usr': usuario})
    
    if not df_check.empty:
        return False, "Usuário já existe. Escolha outro."
    
    # 2. Cria o usuário
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (username, password, name, cliente) VALUES (:usr, :pwd, :name, :cli)"),
            {"usr": usuario, "pwd": senha, "name": nome, "cli": cliente}
        )
    return True, "Usuário criado com sucesso! Faça login."

def carregar_dados_cliente(cliente_nome):
    try:
        query = text("SELECT * FROM okrs WHERE cliente = :cli")
        df = run_query(query, params={'cli': cliente_nome})
        
        colunas_padrao = [
            'departamento', 'objetivo', 'kr', 'tarefa', 
            'status', 'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct', 'cliente'
        ]
        
        if df.empty:
            return pd.DataFrame(columns=colunas_padrao)
            
        if 'prazo' in df.columns:
            df['prazo'] = pd.to_datetime(df['prazo'], errors='coerce')
            
        cols_num = ['avanco', 'alvo', 'progresso_pct']
        for c in cols_num:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
            
        cols_txt = ['departamento', 'objetivo', 'kr', 'tarefa', 'status', 'responsavel']
        for c in cols_txt:
            if c in df.columns: df[c] = df[c].fillna('').astype(str)
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def salvar_dados_cliente(df, cliente_nome):
    df_save = df.copy()
    if 'id' in df_save.columns: del df_save['id']
    if 'created_at' in df_save.columns: del df_save['created_at']
    
    df_save['cliente'] = cliente_nome
    
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM okrs WHERE cliente = :cli"), {"cli": cliente_nome})
        df_save.to_sql('okrs', connection, if_exists='append', index=False)

def gerenciar_departamentos(cliente_nome):
    try:
        query = text("SELECT nome FROM departamentos WHERE cliente = :cli ORDER BY nome")
        df_dept = run_query(query, params={'cli': cliente_nome})
        return df_dept['nome'].tolist()
    except:
        return []

def adicionar_departamento(novo_nome, cliente_nome):
    if novo_nome:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO departamentos (nome, cliente) VALUES (:nome, :cli)"),
                {"nome": novo_nome, "cli": cliente_nome}
            )

def remover_departamento(nome_remover, cliente_nome):
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM departamentos WHERE nome = :nome AND cliente = :cli"),
            {"nome": nome_remover, "cli": cliente_nome}
        )

def calcular_progresso(row):
    try:
        av = float(row['avanco'])
        al = float(row['alvo'])
        if al > 0:
            return min(max(av / al, 0.0), 1.0)
        return 0.0
    except:
        return 0.0

def converter_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp = df.copy()
        if 'prazo' in df_exp.columns:
            df_exp['prazo'] = df_exp['prazo'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '')
        df_exp.to_excel(writer, index=False, sheet_name='OKRs')
    return output.getvalue()

# --- 4. CONTROLE DE SESSÃO ---
if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'df_master' not in st.session_state:
    st.session_state['df_master'] = pd.DataFrame()

# --- 5. TELA DE LOGIN / CADASTRO ---
def check_login():
    if st.session_state['user']: return True
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## Sistema OKR")
        
        # Abas para alternar entre Login e Cadastro
        tab_login, tab_cadastro = st.tabs(["Entrar", "Criar Conta"])
        
        with tab_login:
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            
            if st.button("Acessar", type="primary"):
                query = text("SELECT * FROM users WHERE username = :usr AND password = :pwd")
                try:
                    df_user = run_query(query, params={'usr': usuario, 'pwd': senha})
                    if not df_user.empty:
                        user_data = df_user.iloc[0].to_dict()
                        st.session_state['user'] = user_data
                        st.session_state['df_master'] = carregar_dados_cliente(user_data['cliente'])
                        st.rerun()
                    else:
                        st.error("Usuário ou senha inválidos.")
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")

        with tab_cadastro:
            st.info("Cadastre sua empresa para começar.")
            new_user = st.text_input("Novo Usuário (Login)")
            new_pass = st.text_input("Nova Senha", type="password")
            new_name = st.text_input("Seu Nome")
            new_cli = st.text_input("Nome da Empresa")
            
            if st.button("Cadastrar"):
                if new_user and new_pass and new_cli:
                    sucesso, msg = criar_usuario(new_user, new_pass, new_name, new_cli)
                    if sucesso:
                        st.success(msg)
                    else:
                        st.error(msg)
                else:
                    st.warning("Preencha todos os campos.")
                    
    return False

# --- 6. APLICAÇÃO ---
if check_login():
    user = st.session_state['user']
    cliente_atual = user['cliente']
    df = st.session_state['df_master']
    
    lista_deptos = gerenciar_departamentos(cliente_atual)

    # --- MENU LATERAL ---
    with st.sidebar:
        st.markdown(f"### {cliente_atual}")
        st.caption(f"Olá, {user['name']}")
        
        if st.button("Sair"):
            st.session_state['user'] = None
            st.session_state['df_master'] = pd.DataFrame()
            st.rerun()
            
        st.divider()
        st.markdown("### Configurações")
        
        with st.expander("Departamentos", expanded=True):
            with st.form("add_dept"):
                novo = st.text_input("Novo Departamento:")
                if st.form_submit_button("Adicionar"):
                    if novo:
                        if novo not in lista_deptos:
                            adicionar_departamento(novo, cliente_atual)
                            st.rerun()
                        else:
                            st.warning("Já existe.")
            
            if lista_deptos:
                st.write("---")
                rm_dept = st.selectbox("Remover:", lista_deptos)
                if st.button("Excluir Departamento"):
                    if rm_dept:
                        remover_departamento(rm_dept, cliente_atual)
                        st.rerun()
            else:
                st.info("Nenhum departamento cadastrado.")

        st.divider()
        st.markdown("### Novo Objetivo")
        
        if lista_deptos:
            with st.form("quick_add"):
                d = st.selectbox("Departamento", lista_deptos)
                o = st.text_input("Objetivo Macro")
                if st.form_submit_button("Criar"):
                    if o:
                        novo_okr = {
                            'departamento': d, 'objetivo': o, 'kr': '',
                            'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0,
                            'prazo': pd.to_datetime(date.today()), 'tarefa': '', 'responsavel': '',
                            'cliente': cliente_atual
                        }
                        df_novo = pd.concat([df, pd.DataFrame([novo_okr])], ignore_index=True)
                        st.session_state['df_master'] = df_novo
                        salvar_dados_cliente(df_novo, cliente_atual)
                        st.rerun()
                    else:
                        st.warning("Preencha o nome.")
        else:
            st.warning("Cadastre um departamento para começar.")

    # --- ÁREA PRINCIPAL ---
    st.title(f"Painel OKR")
    
    if not lista_deptos:
        st.info("Bem-vindo! Comece adicionando os departamentos da sua empresa no menu lateral.")
    elif df.empty:
        st.info(f"Nenhum objetivo cadastrado.")
    else:
        depts_usados = {x for x in set(df['departamento'].unique()) if x and x != 'nan'}
        todos_depts = sorted(list(set(lista_deptos) | depts_usados))
        
        if not todos_depts:
             st.info("Adicione um departamento.")
        else:
            abas = st.tabs(todos_depts)
            for i, depto in enumerate(todos_depts):
                with abas[i]:
                    df_d = df[df['departamento'] == depto]
                    if df_d.empty:
                        st.caption("Nenhum objetivo neste departamento.")
                        continue
                    
                    objs = [x for x in df_d['objetivo'].unique() if x]
                    for obj in objs:
                        mask_obj = (df['departamento'] == depto) & (df['objetivo'] == obj)
                        mask_krs = mask_obj & (df['kr'] != '')
                        if not df[mask_krs].empty:
                            prog = df[mask_krs]['progresso_pct'].mean()
                        else:
                            prog = 0.0
                        prog = max(0.0, min(1.0, float(prog)))
                        
                        with st.expander(f"{obj} | {int(prog*100)}%", expanded=True):
                            c1, c2 = st.columns([5,1])
                            with c1:
                                new_obj = st.text_input("Objetivo", value=obj, key=f"obj_{depto}_{obj}", label_visibility="collapsed")
                                if new_obj != obj:
                                    st.session_state['df_master'].loc[mask_obj, 'objetivo'] = new_obj
                                    salvar_dados_cliente(st.session_state['df_master'], cliente_atual)
                                    st.rerun()
                            with c2:
                                if st.button("Excluir", key=f"del_{depto}_{obj}"):
                                    st.session_state['df_master'] = st.session_state['df_master'][~mask_obj]
                                    salvar_dados_cliente(st.session_state['df_master'], cliente_atual)
                                    st.rerun()
                                    
                            krs = [x for x in df[mask_obj]['kr'].unique() if x]
                            for kr in krs:
                                mask_kr = mask_obj & (df['kr'] == kr)
                                df_kr = df[mask_kr]
                                prog_kr = df_kr['progresso_pct'].mean()
                                
                                st.markdown(f"**KR: {kr}**")
                                st.progress(prog_kr)
                                
                                OPCOES_STATUS = ["Não Iniciado", "Em Andamento", "Pausado", "Concluído"]
                                col_cfg = {
                                    "progresso_pct": st.column_config.ProgressColumn("Progresso", format="%.0f%%", min_value=0, max_value=1),
                                    "status": st.column_config.SelectboxColumn("Status", options=OPCOES_STATUS, required=True),
                                    "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
                                    "departamento": None, "objetivo": None, "kr": None, "cliente": None
                                }
                                edited = st.data_editor(
                                    df_kr, column_config=col_cfg, use_container_width=True, num_rows="dynamic", key=f"edit_{depto}_{obj}_{kr}"
                                )
                                if not edited.equals(df_kr):
                                    edited['progresso_pct'] = edited.apply(calcular_progresso, axis=1)
                                    edited['departamento'] = depto
                                    edited['objetivo'] = obj
                                    edited['kr'] = kr
                                    edited['cliente'] = cliente_atual
                                    idxs = df_kr.index
                                    st.session_state['df_master'] = st.session_state['df_master'].drop(idxs)
                                    st.session_state['df_master'] = pd.concat([st.session_state['df_master'], edited], ignore_index=True)
                                    salvar_dados_cliente(st.session_state['df_master'], cliente_atual)
                                    st.rerun()
                                    
                            with st.popover("Novo KR"):
                                nk = st.text_input("Nome", key=f"new_kr_{obj}")
                                if st.button("Salvar KR", key=f"btn_new_kr_{obj}"):
                                    if nk:
                                        dummy = {
                                            'departamento': depto, 'objetivo': obj, 'kr': nk,
                                            'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 
                                            'progresso_pct': 0.0, 'prazo': pd.to_datetime(date.today()),
                                            'tarefa': 'Nova Tarefa', 'responsavel': '', 'cliente': cliente_atual
                                        }
                                        df_novo = pd.concat([st.session_state['df_master'], pd.DataFrame([dummy])], ignore_index=True)
                                        st.session_state['df_master'] = df_novo
                                        salvar_dados_cliente(df_novo, cliente_atual)
                                        st.rerun()

    st.divider()
    with st.expander("Exportar Dados"):
        st.download_button("Baixar Excel", converter_excel(df), "okrs.xlsx")
