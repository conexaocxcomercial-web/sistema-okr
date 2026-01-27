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

# Estilização CSS customizada
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
    .stButton>button {
        border-radius: 5px;
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
        st.error("Configuração de banco de dados não encontrada.")
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
        st.error(f"Erro na base de dados: {e}")
        return None

# ==========================================
# 3. LÓGICA DE NEGÓCIO
# ==========================================

def carregar_dados_cliente(cliente_nome):
    query = "SELECT * FROM okrs WHERE cliente = :cli ORDER BY id ASC"
    df = run_query(query, params={'cli': cliente_nome})
    
    if df is None or df.empty:
        # Garante que created_at exista no dataframe vazio para evitar erro se for referenciado
        return pd.DataFrame(columns=['id', 'created_at', 'departamento', 'objetivo', 'kr', 'tarefa', 'status', 
                                   'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct', 'cliente'])
    
    if 'prazo' in df.columns:
        df['prazo'] = pd.to_datetime(df['prazo'], errors='coerce')
    
    for col in ['avanco', 'alvo', 'progresso_pct']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    return df

def salvar_dados_batch(df, cliente_nome):
    try:
        df_save = df.copy()
        # Removemos created_at aqui para não tentar reinserir (o banco gera automático se for novo)
        cols_to_drop = ['classificacao_prazo', 'mes_ano', 'id', 'created_at']
        df_save = df_save.drop(columns=[c for c in cols_to_drop if c in df_save.columns])
        df_save['cliente'] = cliente_nome
        
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM okrs WHERE cliente = :cli"), {"cli": cliente_nome})
            df_save.to_sql('okrs', conn, if_exists='append', index=False)
        return True
    except Exception as e:
        st.error(f"Falha ao persistir dados: {e}")
        return False

@st.cache_data(ttl=600)
def get_departamentos(cliente_nome):
    df = run_query("SELECT nome FROM departamentos WHERE cliente = :cli ORDER BY nome", {'cli': cliente_nome})
    return df['nome'].tolist() if df is not None else []

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
# 4. COMPONENTES DE UI
# ==========================================

# CORREÇÃO AQUI: Adicionado delta_color aos argumentos aceitos
def render_metric_card(label, value, delta=None, help_text=None, delta_color="normal"):
    """Componente de métrica padronizado"""
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color, help=help_text)

def show_login_page():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/1533/1533913.png", width=80)
        st.title("OKR Master")
        st.caption("Gestão de Performance e Objetivos Estratégicos")
        
        tab_login, tab_reg = st.tabs(["Acessar Conta", "Novo Registro"])
        
        with tab_login:
            with st.form("login_form"):
                u = st.text_input("Usuário", placeholder="seu_usuario")
                p = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                    # Login sem hash para compatibilidade com dados existentes
                    res = run_query("SELECT * FROM users WHERE username=:u AND password=:p", 
                                  {'u': u, 'p': p})
                    if res is not None and not res.empty:
                        st.session_state.user = res.iloc[0].to_dict()
                        st.session_state.df_master = carregar_dados_cliente(st.session_state.user['cliente'])
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")
        
        with tab_reg:
            with st.form("reg_form"):
                nu = st.text_input("Usuário")
                np_text = st.text_input("Senha", type="password")
                nn = st.text_input("Nome Completo")
                nc = st.text_input("Empresa/Cliente")
                if st.form_submit_button("Criar Conta", use_container_width=True):
                    if nu and np_text and nc:
                        exists = run_query("SELECT 1 FROM users WHERE username=:u", {'u': nu})
                        if exists is not None and exists.empty:
                            run_query("INSERT INTO users (username, password, name, cliente) VALUES (:u, :p, :n, :c)",
                                     {'u': nu, 'p': np_text, 'n': nn, 'c': nc}, is_select=False)
                            st.success("Conta criada! Acesse pelo login.")
                        else:
                            st.error("Usuário já existe.")
                    else:
                        st.warning("Preencha todos os campos obrigatórios.")

# ==========================================
# 5. DASHBOARD ANALÍTICO
# ==========================================

def render_dashboard(df):
    if df.empty:
        st.info("💡 Comece cadastrando seus objetivos no Painel de Gestão.")
        return

    df_krs = df[df['kr'].notna() & (df['kr'] != '')].copy()
    if df_krs.empty:
        st.warning("Nenhum KR definido para análise.")
        return

    df_krs['classificacao_prazo'] = classificar_prazo_vetorizado(df_krs)
    
    # KPI Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card("Total de KRs", len(df_krs))
    with m2:
        avg_prog = df_krs['progresso_pct'].mean()
        render_metric_card("Progresso Médio", f"{avg_prog:.1%}")
    with m3:
        atrasados = len(df_krs[df_krs['classificacao_prazo'] == "Atrasado"])
        # Agora funciona porque a função aceita delta_color
        render_metric_card("KRs Atrasados", atrasados, delta=-atrasados if atrasados > 0 else 0, delta_color="inverse")
    with m4:
        concluidos = len(df_krs[df_krs['status'] == "Concluído"])
        render_metric_card("Concluídos", concluidos)

    st.divider()

    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Progresso por Departamento")
        df_dept = df_krs.groupby('departamento')['progresso_pct'].mean().reset_index()
        fig_dept = px.bar(df_dept, x='departamento', y='progresso_pct', 
                         color='progresso_pct', color_continuous_scale='Blues',
                         labels={'progresso_pct': 'Progresso (%)'})
        fig_dept.update_layout(yaxis_tickformat='.0%', showlegend=False, height=350, margin=dict(t=20, b=20, l=0, r=0))
        st.plotly_chart(fig_dept, use_container_width=True)

    with c2:
        st.subheader("Distribuição por Status")
        df_status = df_krs['status'].value_counts().reset_index()
        fig_status = px.pie(df_status, names='status', values='count', 
                           color='status', color_discrete_map=CORES_STATUS,
                           hole=0.4)
        fig_status.update_layout(height=350, margin=dict(t=20, b=20, l=0, r=0))
        st.plotly_chart(fig_status, use_container_width=True)

    st.subheader("Análise de Prazos e Urgência")
    df_prazo = df_krs['classificacao_prazo'].value_counts().reindex(CORES_PRAZO.keys()).fillna(0).reset_index()
    fig_prazo = px.bar(df_prazo, x='classificacao_prazo', y='count', 
                      color='classificacao_prazo', color_discrete_map=CORES_PRAZO)
    fig_prazo.update_layout(showlegend=False, height=300, xaxis_title=None, yaxis_title="Qtd KRs")
    st.plotly_chart(fig_prazo, use_container_width=True)

# ==========================================
# 6. PAINEL DE GESTÃO (OPERACIONAL)
# ==========================================

def render_management_panel(df, cliente, depto_list):
    
    with st.expander("➕ Novo Objetivo Estratégico", expanded=False):
        with st.form("new_obj_form", clear_on_submit=True):
            col_d, col_o, col_b = st.columns([1, 2, 0.5])
            d_new = col_d.selectbox("Departamento", depto_list) if depto_list else col_d.text_input("Departamento")
            o_new = col_o.text_input("Título do Objetivo")
            if col_b.form_submit_button("Criar", type="primary", use_container_width=True):
                if o_new and d_new:
                    new_row = {
                        'departamento': d_new, 'objetivo': o_new, 'kr': '', 'tarefa': 'Definir tarefa',
                        'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0,
                        'prazo': date.today(), 'responsavel': st.session_state.user['name'], 'cliente': cliente
                    }
                    st.session_state.df_master = pd.concat([st.session_state.df_master, pd.DataFrame([new_row])], ignore_index=True)
                    st.session_state.needs_save = True
                    st.rerun()

    if df.empty:
        st.info("Nenhum dado encontrado.")
        return

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
                
                krs_validos = df_obj[df_obj['kr'] != '']
                prog_obj = krs_validos['progresso_pct'].mean() if not krs_validos.empty else 0.0
                
                with st.expander(f"🎯 {obj} — {prog_obj:.0%}", expanded=True):
                    c_title, c_del = st.columns([5, 1])
                    new_title = c_title.text_input("Editar Objetivo", value=obj, key=f"edit_obj_{depto}_{obj}")
                    if new_title != obj:
                        st.session_state.df_master.loc[mask_obj, 'objetivo'] = new_title
                        st.session_state.needs_save = True
                        st.rerun()
                    
                    if c_del.button("Excluir Objetivo", key=f"del_obj_{depto}_{obj}", type="secondary", use_container_width=True):
                        st.session_state.df_master = st.session_state.df_master[~mask_obj]
                        st.session_state.needs_save = True
                        st.rerun()

                    krs = df_obj['kr'].unique()
                    for kr in krs:
                        if not kr: continue
                        
                        mask_kr = mask_obj & (df['kr'] == kr)
                        df_kr_tasks = df[mask_kr].copy()
                        
                        st.markdown(f"**🔑 KR: {kr}**")
                        
                        # CORREÇÃO AQUI: Escondendo created_at e id
                        column_config = {
                            "tarefa": st.column_config.TextColumn("Tarefa", width="large", required=True),
                            "status": st.column_config.SelectboxColumn("Status", options=list(CORES_STATUS.keys()), required=True),
                            "avanco": st.column_config.NumberColumn("Real", min_value=0),
                            "alvo": st.column_config.NumberColumn("Meta", min_value=0.1),
                            "progresso_pct": st.column_config.ProgressColumn("%", format="%.0f%%", min_value=0, max_value=1),
                            "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
                            "responsavel": st.column_config.TextColumn("Responsável"),
                            # Esconder colunas técnicas
                            "id": None, 
                            "created_at": None,
                            "departamento": None, 
                            "objetivo": None, 
                            "kr": None, 
                            "cliente": None
                        }

                        edited_df = st.data_editor(
                            df_kr_tasks,
                            column_config=column_config,
                            key=f"editor_{depto}_{obj}_{kr}",
                            use_container_width=True,
                            num_rows="dynamic",
                            hide_index=True  # CORREÇÃO AQUI: Esconde a coluna de números (index)
                        )

                        if not edited_df.equals(df_kr_tasks):
                            edited_df['progresso_pct'] = calcular_progresso_vetorizado(edited_df)
                            edited_df['departamento'] = depto
                            edited_df['objetivo'] = obj
                            edited_df['kr'] = kr
                            edited_df['cliente'] = cliente
                            
                            st.session_state.df_master = pd.concat([
                                st.session_state.df_master.drop(df_kr_tasks.index),
                                edited_df
                            ], ignore_index=True)
                            st.session_state.needs_save = True
                            st.session_state.last_edit_time = time.time()

                    if st.button(f"➕ Adicionar KR em '{obj}'", key=f"add_kr_{depto}_{obj}"):
                        new_kr_row = {
                            'departamento': depto, 'objetivo': obj, 'kr': 'Novo KR', 'tarefa': 'Nova Tarefa',
                            'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0,
                            'prazo': date.today(), 'responsavel': st.session_state.user['name'], 'cliente': cliente
                        }
                        st.session_state.df_master = pd.concat([st.session_state.df_master, pd.DataFrame([new_kr_row])], ignore_index=True)
                        st.session_state.needs_save = True
                        st.rerun()

# ==========================================
# 7. EXECUÇÃO PRINCIPAL
# ==========================================

def main():
    if 'user' not in st.session_state: st.session_state.user = None
    if 'df_master' not in st.session_state: st.session_state.df_master = pd.DataFrame()
    if 'needs_save' not in st.session_state: st.session_state.needs_save = False
    if 'last_edit_time' not in st.session_state: st.session_state.last_edit_time = 0

    if not st.session_state.user:
        show_login_page()
        return

    user = st.session_state.user
    with st.sidebar:
        st.title("🎯 OKR Master")
        st.write(f"Olá, **{user['name']}**")
        st.caption(f"Empresa: {user['cliente']}")
        st.divider()
        
        menu = st.radio("Navegação", ["📊 Dashboard", "⚙️ Painel de Gestão", "🏢 Departamentos"])
        
        st.spacer = st.empty()
        st.divider()
        
        if st.session_state.needs_save:
            if st.button("💾 Salvar Alterações", type="primary", use_container_width=True):
                if salvar_dados_batch(st.session_state.df_master, user['cliente']):
                    st.session_state.needs_save = False
                    st.success("Dados salvos!")
                    time.sleep(1)
                    st.rerun()
            st.warning("Você tem alterações não salvas.")
        
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.user = None
            st.rerun()

    if menu == "📊 Dashboard":
        st.title("Dashboard Analítico")
        render_dashboard(st.session_state.df_master)
        
    elif menu == "⚙️ Painel de Gestão":
        st.title("Painel de Gestão")
        depto_list = get_departamentos(user['cliente'])
        render_management_panel(st.session_state.df_master, user['cliente'], depto_list)
        
    elif menu == "🏢 Departamentos":
        st.title("Gestão de Departamentos")
        with st.form("add_depto"):
            n_dep = st.text_input("Nome do Novo Departamento")
            if st.form_submit_button("Adicionar"):
                if n_dep:
                    run_query("INSERT INTO departamentos (nome, cliente) VALUES (:n, :c)", 
                             {'n': n_dep, 'c': user['cliente']}, is_select=False)
                    get_departamentos.clear()
                    st.success("Departamento adicionado!")
                    st.rerun()
        
        deps = get_departamentos(user['cliente'])
        if deps:
            st.write("### Departamentos Atuais")
            for d in deps:
                c1, c2 = st.columns([4, 1])
                c1.write(f"- {d}")
                if c2.button("Excluir", key=f"del_dep_{d}"):
                    run_query("DELETE FROM departamentos WHERE nome=:n AND cliente=:c", 
                             {'n': d, 'c': user['cliente']}, is_select=False)
                    get_departamentos.clear()
                    st.rerun()

if __name__ == "__main__":
    main()
