import streamlit as st
import pandas as pd
import os
import time
from io import BytesIO
from datetime import date
from sqlalchemy import create_engine, text

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gestão de OKR", layout="wide", page_icon="🎯")

# --- 2. CONEXÃO HÍBRIDA (Local e Render) ---
# Tenta pegar a conexão dos Segredos (Render/Env) ou usa o padrão (Local)
db_url = os.getenv("DATABASE_URL")

if db_url:
    # Conexão Profissional (Render)
    # Correção para o Render: postgres:// deve ser postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(db_url)
    conn = engine
else:
    # Conexão Desenvolvimento (Streamlit Cloud/Local)
    conn = st.connection("postgresql", type="sql")
    engine = conn.engine

# --- 3. FUNÇÕES DE BANCO DE DADOS (MULTI-TENANT) ---

def run_query(query, params=None):
    """Executa query de forma compatível com ambos os métodos"""
    if db_url:
        with engine.connect() as connection:
            return pd.read_sql(query, connection, params=params)
    else:
        # Adaptação para st.connection que usa :param
        return conn.query(query, params=params, ttl=0)

def carregar_dados_cliente(cliente_nome):
    """Carrega APENAS dados da empresa do usuário logado"""
    try:
        # Filtra pelo cliente logado
        query = "SELECT * FROM okrs WHERE cliente = :cli"
        df = run_query(query, params={'cli': cliente_nome})
        
        # Estrutura padrão se vazio
        colunas_padrao = [
            'departamento', 'objetivo', 'kr', 'tarefa', 
            'status', 'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct', 'cliente'
        ]
        
        if df.empty:
            return pd.DataFrame(columns=colunas_padrao)
            
        # Tratamento de Tipos
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
        st.error(f"Erro ao carregar: {e}")
        return pd.DataFrame()

def salvar_dados_cliente(df, cliente_nome):
    """Salva dados deletando apenas os daquele cliente e reinsere"""
    df_save = df.copy()
    
    # Limpeza
    if 'id' in df_save.columns: del df_save['id']
    if 'created_at' in df_save.columns: del df_save['created_at']
    
    # Garante que a coluna cliente está correta (segurança)
    df_save['cliente'] = cliente_nome
    
    # Transação Segura: Delete + Insert
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM okrs WHERE cliente = :cli"), {"cli": cliente_nome})
        df_save.to_sql('okrs', connection, if_exists='append', index=False)

def carregar_deptos_cliente():
    # Para simplificar, mantemos fixo. No futuro, pode vir do banco também.
    return ["Comercial", "Financeiro", "Operacional", "RH", "Tecnologia", "Marketing"]

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

# --- 5. TELA DE LOGIN ---
def check_login():
    if st.session_state['user']: return True
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## 🔐 Acesso ao Sistema")
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        
        if st.button("Entrar"):
            # Busca usuário no banco
            query = "SELECT * FROM users WHERE username = :usr AND password = :pwd"
            # Nota: Em produção real, use hash para senhas!
            df_user = run_query(query, params={'usr': usuario, 'pwd': senha})
            
            if not df_user.empty:
                user_data = df_user.iloc[0].to_dict()
                st.session_state['user'] = user_data
                # Carrega dados IMEDIATAMENTE após login
                st.session_state['df_master'] = carregar_dados_cliente(user_data['cliente'])
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")
    return False

# --- 6. APLICAÇÃO ---
if check_login():
    user = st.session_state['user']
    cliente_atual = user['cliente']
    df = st.session_state['df_master']
    lista_deptos = carregar_deptos_cliente()

    # --- MENU LATERAL ---
    with st.sidebar:
        # Cabeçalho Personalizado
        st.markdown(f"### 🏢 {cliente_atual}")
        st.caption(f"Olá, {user['name']}")
        
        if st.button("Sair"):
            st.session_state['user'] = None
            st.session_state['df_master'] = pd.DataFrame()
            st.rerun()
            
        st.divider()
        
        with st.expander("Departamentos"):
            with st.form("add_dept"):
                novo = st.text_input("Novo:")
                if st.form_submit_button("Adicionar"):
                    if novo and novo not in lista_deptos:
                        # Nota: Deptos ainda são locais/sessão neste exemplo
                        pass 
            st.info("Lista padrão carregada.")

        st.divider()
        st.markdown("### Novo Objetivo")
        with st.form("quick_add"):
            d = st.selectbox("Departamento", lista_deptos)
            o = st.text_input("Objetivo Macro")
            if st.form_submit_button("Criar"):
                if o:
                    novo_okr = {
                        'departamento': d, 'objetivo': o, 'kr': '',
                        'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0,
                        'prazo': pd.to_datetime(date.today()), 'tarefa': '', 'responsavel': '',
                        'cliente': cliente_atual # CARIMBA O CLIENTE
                    }
                    df_novo = pd.concat([df, pd.DataFrame([novo_okr])], ignore_index=True)
                    st.session_state['df_master'] = df_novo
                    salvar_dados_cliente(df_novo, cliente_atual)
                    st.rerun()
                else:
                    st.warning("Preencha o nome.")

    # --- ÁREA PRINCIPAL ---
    st.title(f"Painel OKR")
    
    if df.empty:
        st.info(f"Bem-vindo, equipe {cliente_atual}. Comece criando um objetivo.")
    else:
        depts = sorted(list(set(df['departamento'].unique()) | set(lista_deptos)))
        abas = st.tabs(depts)
        
        for i, depto in enumerate(depts):
            with abas[i]:
                df_d = df[df['departamento'] == depto]
                if df_d.empty:
                    st.caption("Sem dados.")
                    continue
                
                # Objetivos
                objs = [x for x in df_d['objetivo'].unique() if x]
                for obj in objs:
                    mask_obj = (df['departamento'] == depto) & (df['objetivo'] == obj)
                    
                    # Progresso
                    mask_krs = mask_obj & (df['kr'] != '')
                    if not df[mask_krs].empty:
                        prog = df[mask_krs]['progresso_pct'].mean()
                    else:
                        prog = 0.0
                    prog = max(0.0, min(1.0, float(prog)))
                    
                    with st.expander(f"{obj} | {int(prog*100)}%", expanded=True):
                        # Edição do Título do Objetivo
                        c1, c2 = st.columns([5,1])
                        with c1:
                            new_obj = st.text_input("Objetivo", value=obj, key=f"obj_{depto}_{obj}", label_visibility="collapsed")
                            if new_obj != obj:
                                st.session_state['df_master'].loc[mask_obj, 'objetivo'] = new_obj
                                salvar_dados_cliente(st.session_state['df_master'], cliente_atual)
                                st.rerun()
                        with c2:
                            if st.button("🗑️", key=f"del_{depto}_{obj}"):
                                st.session_state['df_master'] = st.session_state['df_master'][~mask_obj]
                                salvar_dados_cliente(st.session_state['df_master'], cliente_atual)
                                st.rerun()
                                
                        # KRs
                        krs = [x for x in df[mask_obj]['kr'].unique() if x]
                        for kr in krs:
                            mask_kr = mask_obj & (df['kr'] == kr)
                            df_kr = df[mask_kr]
                            prog_kr = df_kr['progresso_pct'].mean()
                            
                            st.markdown(f"**KR: {kr}**")
                            st.progress(prog_kr)
                            
                            col_cfg = {
                                "progresso_pct": st.column_config.ProgressColumn("Progresso", format="%.0f%%", min_value=0, max_value=1),
                                "status": st.column_config.SelectboxColumn("Status", options=OPCOES_STATUS, required=True),
                                "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
                                "departamento": None, "objetivo": None, "kr": None, "cliente": None
                            }
                            
                            edited = st.data_editor(
                                df_kr, 
                                column_config=col_cfg, 
                                use_container_width=True, 
                                num_rows="dynamic", 
                                key=f"edit_{depto}_{obj}_{kr}"
                            )
                            
                            if not edited.equals(df_kr):
                                edited['progresso_pct'] = edited.apply(calcular_progresso, axis=1)
                                edited['departamento'] = depto
                                edited['objetivo'] = obj
                                edited['kr'] = kr
                                edited['cliente'] = cliente_atual
                                
                                # Atualiza Master
                                idxs = df_kr.index
                                st.session_state['df_master'] = st.session_state['df_master'].drop(idxs)
                                st.session_state['df_master'] = pd.concat([st.session_state['df_master'], edited], ignore_index=True)
                                
                                salvar_dados_cliente(st.session_state['df_master'], cliente_atual)
                                st.rerun()
                                
                        # Novo KR
                        with st.popover("Novo KR"):
                            nk = st.text_input("Nome", key=f"new_kr_{obj}")
                            if st.button("Criar", key=f"btn_new_kr_{obj}"):
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
    with st.expander("Exportar"):
        st.download_button("Download Excel", converter_excel(df), "okrs.xlsx")
