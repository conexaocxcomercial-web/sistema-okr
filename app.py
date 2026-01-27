import streamlit as st
import pandas as pd
import numpy as np
import os
import time
import hashlib
from io import BytesIO
from datetime import date, datetime
from sqlalchemy import create_engine, text
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. CONFIGURAÇÕES E CONSTANTES
# ==========================================
st.set_page_config(
    page_title="OKR Master | Gestão Estratégica",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Customizado
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { 
        background-color: white; 
        padding: 20px; 
        border-radius: 10px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stExpander"] {
        border: none !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        background: white;
        margin-bottom: 1rem;
    }
    /* Destaque para o botão de salvar quando ativo */
    div.stButton > button:first-child {
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

CORES_STATUS = {
    "Concluído": "#2ECC71",
    "Em Andamento": "#3498DB",
    "Pausado": "#F1C40F",
    "Não Iniciado": "#E74C3C"
}

CORES_PRAZO = {
    "Atrasado": "#E74C3C",
    "Urgente (7 dias)": "#E67E22",
    "Atenção (30 dias)": "#F1C40F",
    "No Prazo": "#3498DB",
    "Concluído": "#95A5A6",
    "Sem Prazo": "#BDC3C7"
}

# ==========================================
# 2. CAMADA DE DADOS
# ==========================================

@st.cache_resource
def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    if db_url:
        return create_engine(db_url)
    try:
        return st.connection("postgresql", type="sql").engine
    except:
        st.error("Erro: Banco de dados não configurado.")
        st.stop()

engine = get_engine()

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def run_query(query, params=None, is_select=True):
    try:
        with engine.connect() as conn:
            if is_select:
                return pd.read_sql(text(query) if isinstance(query, str) else query, conn, params=params)
            else:
                with conn.begin():
                    conn.execute(text(query) if isinstance(query, str) else query, params or {})
                return True
    except Exception as e:
        st.error(f"Erro no banco: {e}")
        return None

def carregar_dados_cliente(cliente_nome):
    query = "SELECT * FROM okrs WHERE cliente = :cli ORDER BY id ASC"
    df = run_query(query, params={'cli': cliente_nome})
    
    colunas_base = ['id', 'departamento', 'objetivo', 'kr', 'tarefa', 'status', 
                   'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct', 'cliente', 'created_at']
    
    if df is None or df.empty:
        return pd.DataFrame(columns=colunas_base)
    
    # Ajuste de tipos
    if 'prazo' in df.columns:
        df['prazo'] = pd.to_datetime(df['prazo'], errors='coerce')
    
    for col in ['avanco', 'alvo', 'progresso_pct']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    return df

def salvar_dados_batch(df, cliente_nome):
    """Salva os dados da memória no banco"""
    try:
        df_save = df.copy()
        # Remove colunas que não existem na tabela física ou que são geradas pelo banco
        cols_to_drop = ['classificacao_prazo', 'mes_ano', 'id', 'created_at']
        df_save = df_save.drop(columns=[c for c in cols_to_drop if c in df_save.columns])
        
        # Garante integridade
        df_save['cliente'] = cliente_nome
        
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM okrs WHERE cliente = :cli"), {"cli": cliente_nome})
            df_save.to_sql('okrs', conn, if_exists='append', index=False)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

@st.cache_data(ttl=600)
def get_departamentos(cliente_nome):
    df = run_query("SELECT nome FROM departamentos WHERE cliente = :cli ORDER BY nome", {'cli': cliente_nome})
    return df['nome'].tolist() if df is not None else []

# Funções vetorizadas (rápidas) para cálculos em memória
def calcular_progresso_vetorizado(df):
    if df.empty: return pd.Series(dtype=float)
    alvo = df['alvo'].where(df['alvo'] != 0, 1)
    return (df['avanco'] / alvo).clip(0, 1)

def classificar_prazo_vetorizado(df):
    if df.empty or 'prazo' not in df.columns: return pd.Series(dtype=str)
    hoje = pd.Timestamp(date.today())
    classif = pd.Series("Sem Prazo", index=df.index)
    
    mask_done = df['status'] == 'Concluído'
    mask_has_date = df['prazo'].notna() & ~mask_done
    
    classif[mask_done] = "Concluído"
    
    if mask_has_date.any():
        dias = (df.loc[mask_has_date, 'prazo'] - hoje).dt.days
        classif.loc[mask_has_date & (dias < 0)] = "Atrasado"
        classif.loc[mask_has_date & (dias >= 0) & (dias <= 7)] = "Urgente (7 dias)"
        classif.loc[mask_has_date & (dias > 7) & (dias <= 30)] = "Atenção (30 dias)"
        classif.loc[mask_has_date & (dias > 30)] = "No Prazo"
        
    return classif

# ==========================================
# 3. COMPONENTES DE UI
# ==========================================

def render_metric_card(label, value, delta=None, delta_color="normal", help_text=None):
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color, help=help_text)

def converter_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp = df.copy()
        if 'prazo' in df_exp.columns:
            df_exp['prazo'] = df_exp['prazo'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '')
        # Remove colunas técnicas da exportação
        cols_remove = ['id', 'created_at']
        df_exp = df_exp.drop(columns=[c for c in cols_remove if c in df_exp.columns])
        df_exp.to_excel(writer, index=False)
    return output.getvalue()

def show_login_page():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.title("🎯 OKR Master")
        st.caption("Gestão Estratégica Simplificada")
        
        tab_login, tab_reg = st.tabs(["Login", "Registro"])
        
        with tab_login:
            with st.form("login"):
                u = st.text_input("Usuário")
                p = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                    # Login simplificado (compatível com senhas antigas)
                    res = run_query("SELECT * FROM users WHERE username=:u AND password=:p", {'u': u, 'p': p})
                    if res is not None and not res.empty:
                        st.session_state.user = res.iloc[0].to_dict()
                        st.session_state.df_master = carregar_dados_cliente(st.session_state.user['cliente'])
                        st.session_state.needs_save = False
                        st.rerun()
                    else:
                        st.error("Dados incorretos.")
        
        with tab_reg:
            with st.form("reg"):
                nu = st.text_input("Usuário")
                np = st.text_input("Senha", type="password")
                nn = st.text_input("Nome")
                nc = st.text_input("Empresa")
                if st.form_submit_button("Criar Conta", use_container_width=True):
                    if nu and np and nc:
                        exists = run_query("SELECT 1 FROM users WHERE username=:u", {'u': nu})
                        if exists is not None and exists.empty:
                            run_query("INSERT INTO users (username, password, name, cliente) VALUES (:u, :p, :n, :c)",
                                     {'u': nu, 'p': np, 'n': nn, 'c': nc}, is_select=False)
                            st.success("Criado! Faça login.")
                        else:
                            st.error("Usuário já existe.")

# ==========================================
# 4. DASHBOARD E PAINEL
# ==========================================

def render_dashboard(df):
    if df.empty:
        st.info("Sem dados para exibir.")
        return

    # Filtra apenas linhas válidas (com KR)
    df_krs = df[df['kr'].notna() & (df['kr'] != '')].copy()
    if df_krs.empty:
        st.warning("Adicione KRs para ver os indicadores.")
        return

    df_krs['classificacao_prazo'] = classificar_prazo_vetorizado(df_krs)
    
    # KPIs
    m1, m2, m3, m4 = st.columns(4)
    with m1: render_metric_card("Total de KRs", len(df_krs))
    with m2: render_metric_card("Progresso Médio", f"{df_krs['progresso_pct'].mean():.1%}")
    with m3:
        atrasados = len(df_krs[df_krs['classificacao_prazo'] == "Atrasado"])
        render_metric_card("Atrasados", atrasados, delta=-atrasados if atrasados > 0 else 0, delta_color="inverse")
    with m4:
        concluidos = len(df_krs[df_krs['status'] == "Concluído"])
        render_metric_card("Concluídos", concluidos)

    st.divider()
    
    # Gráficos
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Progresso por Área")
        df_dept = df_krs.groupby('departamento')['progresso_pct'].mean().reset_index()
        fig = px.bar(df_dept, x='departamento', y='progresso_pct', color='progresso_pct', color_continuous_scale='Blues')
        fig.update_layout(yaxis_tickformat='.0%', height=300, margin=dict(t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)
    
    with c2:
        st.subheader("Status Geral")
        fig = px.pie(df_krs, names='status', color='status', color_discrete_map=CORES_STATUS, hole=0.4)
        fig.update_layout(height=300, margin=dict(t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)

def render_management_panel(df, cliente, depto_list):
    # Criação Rápida
    with st.expander("➕ Novo Objetivo", expanded=False):
        c1, c2, c3 = st.columns([1, 2, 0.5])
        d_new = c1.selectbox("Departamento", depto_list) if depto_list else c1.text_input("Departamento")
        o_new = c2.text_input("Objetivo Macro")
        if c3.button("Criar Objetivo", type="primary", use_container_width=True):
            if o_new and d_new:
                new_row = {
                    'departamento': d_new, 'objetivo': o_new, 'kr': '', 'tarefa': 'Tarefa Inicial',
                    'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0,
                    'prazo': date.today(), 'responsavel': st.session_state.user['name'], 'cliente': cliente
                }
                st.session_state.df_master = pd.concat([st.session_state.df_master, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state.needs_save = True
                st.rerun()

    if df.empty:
        st.info("Comece criando um objetivo acima.")
        return

    # Estrutura Hierárquica
    depts = sorted(df['departamento'].unique())
    if not depts: return
    
    tabs = st.tabs(depts)
    for i, depto in enumerate(depts):
        with tabs[i]:
            df_d = df[df['departamento'] == depto]
            objs = sorted(df_d['objetivo'].unique())
            
            for obj in objs:
                mask_obj = (df['departamento'] == depto) & (df['objetivo'] == obj)
                df_obj = df[mask_obj]
                
                # Progresso do Objetivo
                valid_krs = df_obj[df_obj['kr'] != '']
                prog = valid_krs['progresso_pct'].mean() if not valid_krs.empty else 0.0
                
                with st.expander(f"🎯 {obj} ({int(prog*100)}%)", expanded=True):
                    # Edição do Objetivo
                    c_edit, c_del = st.columns([5, 1])
                    new_title = c_edit.text_input("Nome do Objetivo", value=obj, key=f"title_{depto}_{obj}", label_visibility="collapsed")
                    if new_title != obj:
                        st.session_state.df_master.loc[mask_obj, 'objetivo'] = new_title
                        st.session_state.needs_save = True
                        st.rerun()
                    
                    if c_del.button("🗑️", key=f"del_{depto}_{obj}", help="Excluir Objetivo"):
                        st.session_state.df_master = st.session_state.df_master[~mask_obj]
                        st.session_state.needs_save = True
                        st.rerun()

                    st.markdown("---")
                    
                    # Loop de KRs
                    krs = [k for k in df_obj['kr'].unique() if k]
                    for kr in krs:
                        mask_kr = mask_obj & (df['kr'] == kr)
                        df_kr_tasks = df[mask_kr].copy()
                        
                        # --- CABEÇALHO DO KR (Renomear e Excluir) ---
                        c_kr_name, c_kr_del = st.columns([6, 0.5])
                        
                        # Campo de texto para renomear KR
                        new_kr_name = c_kr_name.text_input(
                            "KR", 
                            value=kr, 
                            key=f"name_kr_{depto}_{obj}_{kr}", 
                            label_visibility="collapsed",
                            placeholder="Nome do Resultado Chave"
                        )
                        
                        # Lógica de Renomear KR
                        if new_kr_name != kr:
                            st.session_state.df_master.loc[mask_kr, 'kr'] = new_kr_name
                            st.session_state.needs_save = True
                            st.rerun() # Rerun necessário para atualizar estrutura
                            
                        # Botão Excluir KR
                        if c_kr_del.button("❌", key=f"del_kr_{depto}_{obj}_{kr}", help="Excluir este KR e suas tarefas"):
                            st.session_state.df_master = st.session_state.df_master[~mask_kr]
                            st.session_state.needs_save = True
                            st.rerun()

                        # Barra de progresso do KR
                        prog_kr = df_kr_tasks['progresso_pct'].mean()
                        st.progress(prog_kr)

                        # --- TABELA DE TAREFAS (OTIMIZADA) ---
                        column_config = {
                            "tarefa": st.column_config.TextColumn("Tarefa", width="large", required=True),
                            "status": st.column_config.SelectboxColumn("Status", options=list(CORES_STATUS.keys()), required=True),
                            "avanco": st.column_config.NumberColumn("Real", min_value=0),
                            "alvo": st.column_config.NumberColumn("Meta", min_value=0.1),
                            "progresso_pct": st.column_config.ProgressColumn("%", format="%.0f%%", min_value=0, max_value=1),
                            "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
                            "responsavel": st.column_config.TextColumn("Resp."),
                            # Ocultar colunas técnicas
                            "id": None, "created_at": None, 
                            "departamento": None, "objetivo": None, "kr": None, "cliente": None
                        }

                        edited_df = st.data_editor(
                            df_kr_tasks,
                            column_config=column_config,
                            key=f"editor_{depto}_{obj}_{kr}",
                            use_container_width=True,
                            num_rows="dynamic",
                            hide_index=True # Remove a coluna numérica da esquerda
                        )

                        # Salvar edições na memória (sem rerun)
                        if not edited_df.equals(df_kr_tasks):
                            # Recalcula
                            edited_df['progresso_pct'] = calcular_progresso_vetorizado(edited_df)
                            # Garante integridade
                            edited_df['departamento'] = depto
                            edited_df['objetivo'] = obj
                            edited_df['kr'] = kr
                            edited_df['cliente'] = cliente
                            
                            # Atualiza Master
                            df_sem_kr = st.session_state.df_master.drop(df_kr_tasks.index)
                            st.session_state.df_master = pd.concat([df_sem_kr, edited_df], ignore_index=True)
                            
                            # Ativa botão de salvar
                            st.session_state.needs_save = True
                            # Nota: Sem st.rerun() aqui para não travar a digitação

                    # Botão para adicionar novo KR dentro do Objetivo
                    if st.button(f"➕ Adicionar KR em '{obj}'", key=f"add_new_kr_{depto}_{obj}"):
                        new_row = {
                            'departamento': depto, 'objetivo': obj, 'kr': 'Novo KR', 'tarefa': 'Tarefa 1',
                            'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0,
                            'prazo': date.today(), 'responsavel': st.session_state.user['name'], 'cliente': cliente
                        }
                        st.session_state.df_master = pd.concat([st.session_state.df_master, pd.DataFrame([new_row])], ignore_index=True)
                        st.session_state.needs_save = True
                        st.rerun()

# ==========================================
# 5. EXECUÇÃO PRINCIPAL
# ==========================================

def main():
    if 'user' not in st.session_state: st.session_state.user = None
    if 'df_master' not in st.session_state: st.session_state.df_master = pd.DataFrame()
    if 'needs_save' not in st.session_state: st.session_state.needs_save = False

    if not st.session_state.user:
        show_login_page()
        return

    # Sidebar: Onde a mágica do "Salvar" acontece
    with st.sidebar:
        st.title("🎯 OKR Master")
        st.caption(f"{st.session_state.user['name']} | {st.session_state.user['cliente']}")
        
        # Placeholder para o botão de salvar aparecer instantaneamente
        save_container = st.empty()
        
        st.divider()
        menu = st.radio("Menu", ["📊 Dashboard", "⚙️ Painel de Gestão", "🏢 Departamentos"])
        st.divider()
        
        if st.button("Sair", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # Renderiza o botão de salvar SE houver mudanças
    if st.session_state.needs_save:
        with save_container.container():
            st.warning("⚠️ Há alterações pendentes")
            if st.button("💾 SALVAR TUDO", type="primary", use_container_width=True):
                with st.spinner("Salvando..."):
                    if salvar_dados_batch(st.session_state.df_master, st.session_state.user['cliente']):
                        st.session_state.needs_save = False
                        st.success("Salvo com sucesso!")
                        time.sleep(0.5)
                        st.rerun()

    # Conteúdo Principal
    user = st.session_state.user
    if menu == "📊 Dashboard":
        st.title("Dashboard Analítico")
        render_dashboard(st.session_state.df_master)
    
    elif menu == "⚙️ Painel de Gestão":
        st.title("Painel de Gestão")
        depto_list = get_departamentos(user['cliente'])
        render_management_panel(st.session_state.df_master, user['cliente'], depto_list)
        
    elif menu == "🏢 Departamentos":
        st.title("Departamentos")
        with st.form("new_dep"):
            d = st.text_input("Nome")
            if st.form_submit_button("Adicionar") and d:
                run_query("INSERT INTO departamentos (nome, cliente) VALUES (:n, :c)", {'n': d, 'c': user['cliente']}, is_select=False)
                get_departamentos.clear()
                st.rerun()
        
        deps = get_departamentos(user['cliente'])
        if deps:
            for dep in deps:
                c1, c2 = st.columns([4, 1])
                c1.write(f"• {dep}")
                if c2.button("Excluir", key=f"del_dep_{dep}"):
                    run_query("DELETE FROM departamentos WHERE nome=:n AND cliente=:c", {'n': dep, 'c': user['cliente']}, is_select=False)
                    get_departamentos.clear()
                    st.rerun()

if __name__ == "__main__":
    main()
