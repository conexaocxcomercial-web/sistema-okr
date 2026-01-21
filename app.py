import streamlit as st
import pandas as pd
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
    "Concluído": "#bef533",      # Verde Lima
    "Em Andamento": "#7371ff",   # Roxo/Azul
    "Pausado": "#ffd166",        # Amarelo
    "Não Iniciado": "#ff5a34"    # Laranja
}

CORES_PRAZO = {
    "Atrasado": "#ff5a34",         
    "Urgente (7 dias)": "#ff9f1c", 
    "Atenção (30 dias)": "#ffd166",
    "No Prazo": "#7371ff",         
    "Concluído": "#e0e0e0",        
    "Sem Prazo": "#f0f2f6"         
}

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
    query_check = text("SELECT * FROM users WHERE username = :usr")
    df_check = run_query(query_check, params={'usr': usuario})
    if not df_check.empty: return False, "Usuário já existe."
    
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (username, password, name, cliente) VALUES (:usr, :pwd, :name, :cli)"),
            {"usr": usuario, "pwd": senha, "name": nome, "cli": cliente}
        )
    return True, "Usuário criado com sucesso!"

@st.cache_data(ttl=0)
def carregar_dados_cliente(cliente_nome):
    try:
        query = text("SELECT * FROM okrs WHERE cliente = :cli ORDER BY id ASC")
        df = run_query(query, params={'cli': cliente_nome})
        colunas_padrao = ['id', 'departamento', 'objetivo', 'kr', 'tarefa', 'status', 'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct', 'cliente']
        
        if df.empty: return pd.DataFrame(columns=colunas_padrao)
        
        if 'prazo' in df.columns: df['prazo'] = pd.to_datetime(df['prazo'], errors='coerce')
        cols_num = ['avanco', 'alvo', 'progresso_pct']
        for c in cols_num:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
            
        if 'created_at' in df.columns: del df['created_at']
        return df
    except: return pd.DataFrame()

def salvar_dados_no_banco(df, cliente_nome):
    """Grava o DataFrame da memória no banco."""
    df_save = df.copy()
    cols_remove = ['created_at', 'classificacao_prazo', 'mes_ano']
    for c in cols_remove:
        if c in df_save.columns: del df_save[c]
    
    df_save['cliente'] = cliente_nome
    # Removemos o ID para forçar o banco a recriar os índices corretamente no insert em massa
    if 'id' in df_save.columns: del df_save['id'] 
    
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM okrs WHERE cliente = :cli"), {"cli": cliente_nome})
        df_save.to_sql('okrs', connection, if_exists='append', index=False)

def gerenciar_departamentos(cliente_nome):
    try:
        query = text("SELECT nome FROM departamentos WHERE cliente = :cli ORDER BY nome")
        df_dept = run_query(query, params={'cli': cliente_nome})
        return df_dept['nome'].tolist()
    except: return []

def adicionar_departamento(novo, cli):
    if novo:
        with engine.begin() as c:
            c.execute(text("INSERT INTO departamentos (nome, cliente) VALUES (:n, :c)"), {"n": novo, "c": cli})

def remover_departamento(nome, cli):
    with engine.begin() as c:
        c.execute(text("DELETE FROM departamentos WHERE nome = :n AND cliente = :c"), {"n": nome, "c": cli})

def calcular_progresso(row):
    try:
        return min(max(float(row.get('avanco', 0)) / float(row.get('alvo', 0)), 0.0), 1.0) if float(row.get('alvo', 0)) > 0 else 0.0
    except: return 0.0

def converter_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp = df.copy()
        if 'prazo' in df_exp.columns: df_exp['prazo'] = df_exp['prazo'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '')
        df_exp.to_excel(writer, index=False)
    return output.getvalue()

def classificar_prazo(row):
    if row.get('status') == 'Concluído': return "Concluído"
    if pd.isnull(row.get('prazo')): return "Sem Prazo"
    try:
        hoje = pd.to_datetime(date.today())
        delta = (row['prazo'] - hoje).days
        if delta < 0: return "Atrasado"
        elif delta <= 7: return "Urgente (7 dias)"
        elif delta <= 30: return "Atenção (30 dias)"
        else: return "No Prazo"
    except: return "Sem Prazo"

# --- 4. SESSÃO E ESTADO ---
if 'user' not in st.session_state: st.session_state['user'] = None
# Carrega dados na memória se estiver vazio
if 'df_master' not in st.session_state: st.session_state['df_master'] = pd.DataFrame()
if 'needs_save' not in st.session_state: st.session_state['needs_save'] = False

# --- 5. LOGIN ---
def check_login():
    if st.session_state['user']: return True
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## Sistema OKR")
        tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
        with tab1:
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Acessar", type="primary"):
                try:
                    df = run_query(text("SELECT * FROM users WHERE username=:u AND password=:p"), {'u':u, 'p':p})
                    if not df.empty:
                        user_data = df.iloc[0].to_dict()
                        st.session_state['user'] = user_data
                        # Carrega do banco apenas uma vez
                        st.session_state['df_master'] = carregar_dados_cliente(user_data['cliente'])
                        st.session_state['needs_save'] = False
                        st.rerun()
                    else: st.error("Inválido.")
                except Exception as e: st.error(f"Erro: {e}")
        with tab2:
            nu, np, nn, nc = st.text_input("Novo Usuário"), st.text_input("Nova Senha", type="password"), st.text_input("Nome"), st.text_input("Empresa")
            if st.button("Cadastrar"):
                if nu and np and nc:
                    ok, msg = criar_usuario(nu, np, nn, nc)
                    if ok: st.success(msg)
                    else: st.error(msg)
                else: st.warning("Preencha tudo.")
    return False

# --- 6. APLICAÇÃO ---
if check_login():
    user = st.session_state['user']
    cliente_atual = user['cliente']
    
    # Trabalhamos sempre com a cópia em memória
    df = st.session_state['df_master']
    lista_deptos = gerenciar_departamentos(cliente_atual)

    # --- MENU LATERAL ---
    with st.sidebar:
        st.markdown(f"### {cliente_atual}")
        st.caption(f"Olá, {user['name']}")
        
        # --- BOTÃO DE SALVAR (A SOLUÇÃO) ---
        if st.session_state.get('needs_save', False):
            st.warning("⚠️ Há alterações não salvas!")
            if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
                with st.spinner("Gravando no banco..."):
                    salvar_dados_no_banco(st.session_state['df_master'], cliente_atual)
                    st.session_state['needs_save'] = False
                    st.success("Salvo com sucesso!")
                    time.sleep(1)
                    st.rerun()
        else:
            st.success("Sistema atualizado.")
            
        st.divider()
        pagina = st.radio("Menu", ["Painel de Gestão", "Dashboard"])
        
        st.divider()
        if st.button("Sair"):
            st.session_state['user'] = None
            st.session_state['df_master'] = pd.DataFrame()
            st.rerun()

        if pagina == "Painel de Gestão":
            with st.expander("Departamentos", expanded=True):
                with st.form("add"):
                    n = st.text_input("Novo:")
                    if st.form_submit_button("Adicionar") and n and n not in lista_deptos:
                        adicionar_departamento(n, cliente_atual)
                        st.rerun()
                if lista_deptos:
                    rm = st.selectbox("Remover:", lista_deptos)
                    if st.button("Excluir") and rm:
                        remover_departamento(rm, cliente_atual)
                        st.rerun()

    # --- PÁGINA: DASHBOARD ---
    if pagina == "Dashboard":
        st.title("Dashboard")
        
        if df.empty:
            st.info("Cadastre objetivos e KRs para visualizar os gráficos.")
        else:
            df_krs = df[df['kr'] != ''].copy()
            
            if df_krs.empty:
                st.warning("Adicione KRs para visualizar as métricas.")
            else:
                df_krs['classificacao_prazo'] = df_krs.apply(classificar_prazo, axis=1)
                if 'prazo' in df_krs.columns and pd.api.types.is_datetime64_any_dtype(df_krs['prazo']):
                    df_krs['mes_ano'] = df_krs['prazo'].dt.strftime('%Y-%m')
                else: df_krs['mes_ano'] = "N/A"

                total_krs = len(df_krs)
                media_progresso = df_krs['progresso_pct'].mean()
                
                k1, k2 = st.columns(2)
                with k1:
                    st.markdown(f"<div style='text-align: center;'><h4 style='margin:0; color: #666; font-weight: normal;'>% Progresso Global</h4><h1 style='margin:0; font-size: 56px; color: #333; font-weight: bold;'>{media_progresso*100:.1f}%</h1></div>", unsafe_allow_html=True)
                with k2:
                    st.markdown(f"<div style='text-align: center;'><h4 style='margin:0; color: #666; font-weight: normal;'>Nº de Entregas (Tarefas/KRs)</h4><h1 style='margin:0; font-size: 56px; color: #333; font-weight: bold;'>{total_krs}</h1></div>", unsafe_allow_html=True)

                st.divider()
                c_left, c_right = st.columns(2)
                with c_left:
                    st.subheader("Status Global")
                    df_pie = df_krs['status'].value_counts().reset_index()
                    df_pie.columns = ['status', 'contagem']
                    fig_pie = px.pie(df_pie, values='contagem', names='status', color='status', color_discrete_map=CORES_STATUS)
                    fig_pie.update_traces(marker=dict(line=dict(color='#ffffff', width=2)))
                    fig_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", y=-0.1), height=350, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_pie, use_container_width=True)
                with c_right:
                    st.subheader("Status por Departamento")
                    df_bar = df_krs.groupby(['departamento', 'status']).size().reset_index(name='contagem')
                    fig_bar = px.bar(df_bar, y="departamento", x="contagem", color="status", orientation='h', color_discrete_map=CORES_STATUS, text_auto=True)
                    fig_bar.update_layout(xaxis_visible=False, yaxis_title=None, legend_title_text='', legend=dict(orientation="h", y=-0.1), height=350, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_bar, use_container_width=True)

                st.divider()
                st.subheader("Status por Responsável")
                df_resp = df_krs.copy()
                df_resp['responsavel'] = df_resp['responsavel'].replace('', 'Não Atribuído')
                df_resp_group = df_resp.groupby(['responsavel', 'status']).size().reset_index(name='contagem')
                fig_resp = px.bar(df_resp_group, y="responsavel", x="contagem", color="status", orientation='h', color_discrete_map=CORES_STATUS, text_auto=True)
                fig_resp.update_layout(xaxis_visible=False, yaxis_title=None, legend_title_text='', legend=dict(orientation="h", y=-0.15), height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_resp, use_container_width=True)
                
                st.divider()
                col_farol, col_heat = st.columns(2)
                with col_farol:
                    st.subheader("Farol de Prazos")
                    df_farol = df_krs['classificacao_prazo'].value_counts().reset_index()
                    df_farol.columns = ['classificacao', 'contagem']
                    ordem_farol = ["Atrasado", "Urgente (7 dias)", "Atenção (30 dias)", "No Prazo", "Concluído", "Sem Prazo"]
                    fig_farol = px.bar(df_farol, y="classificacao", x="contagem", color="classificacao", orientation='h', color_discrete_map=CORES_PRAZO, text_auto=True, category_orders={"classificacao": ordem_farol})
                    fig_farol.update_layout(xaxis_visible=False, yaxis_title=None, showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_farol, use_container_width=True)
                with col_heat:
                    st.subheader("Mapa de Calor")
                    if df_krs['mes_ano'].nunique() > 0:
                        df_heat = df_krs.groupby(['departamento', 'mes_ano']).size().reset_index(name='qtd')
                        fig_heat = px.density_heatmap(df_heat, x="mes_ano", y="departamento", z="qtd", color_continuous_scale="Blues", text_auto=True)
                        fig_heat.update_layout(xaxis_title="Mês de Entrega", yaxis_title=None, coloraxis_showscale=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                        st.plotly_chart(fig_heat, use_container_width=True)

    # --- PÁGINA: PAINEL DE GESTÃO ---
    elif pagina == "Painel de Gestão":
        st.title(f"Painel de Gestão")
        
        if lista_deptos:
            with st.form("quick_create"):
                c1, c2, c3 = st.columns([2, 3, 1])
                d_q = c1.selectbox("Departamento", lista_deptos)
                o_q = c2.text_input("Novo Objetivo")
                if c3.form_submit_button("Criar Objetivo", type="primary"):
                    if o_q:
                        novo = {'departamento': d_q, 'objetivo': o_q, 'kr': '', 'tarefa': '', 'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0, 'prazo': pd.to_datetime(date.today()), 'responsavel': '', 'cliente': cliente_atual}
                        st.session_state['df_master'] = pd.concat([st.session_state['df_master'], pd.DataFrame([novo])], ignore_index=True)
                        st.session_state['needs_save'] = True
                        st.rerun()

        st.divider()
        
        if not lista_deptos:
            st.info("Adicione departamentos no menu lateral.")
        elif df.empty:
            st.info("Nenhum objetivo.")
        else:
            depts_usados = {x for x in set(df['departamento'].unique()) if x and x != 'nan'}
            todos_depts = sorted(list(set(lista_deptos) | depts_usados))
            
            if not todos_depts: st.info("Adicione um departamento.")
            else:
                abas = st.tabs(todos_depts)
                for i, depto in enumerate(todos_depts):
                    with abas[i]:
                        df_d = df[df['departamento'] == depto]
                        if df_d.empty:
                            st.caption("Vazio.")
                            continue
                        
                        objs = [x for x in df_d['objetivo'].unique() if x]
                        for obj in objs:
                            mask_obj = (df['departamento'] == depto) & (df['objetivo'] == obj)
                            
                            # Filtra KRs válidos para calcular média do Objetivo
                            df_obj_calc = df[mask_obj & (df['kr'] != '')]
                            prog_obj = df_obj_calc['progresso_pct'].mean() if not df_obj_calc.empty else 0.0
                            
                            with st.expander(f"{obj} | {int(prog_obj*100)}%", expanded=True):
                                c1, c2 = st.columns([5,1])
                                with c1:
                                    no = st.text_input("Objetivo", value=obj, key=f"o_{depto}_{obj}", label_visibility="collapsed")
                                    if no != obj:
                                        st.session_state['df_master'].loc[mask_obj, 'objetivo'] = no
                                        st.session_state['needs_save'] = True
                                        st.rerun()
                                with c2:
                                    if st.button("Excluir", key=f"d_{depto}_{obj}"):
                                        st.session_state['df_master'] = st.session_state['df_master'][~mask_obj]
                                        st.session_state['needs_save'] = True
                                        st.rerun()
                                        
                                krs = [x for x in df[mask_obj]['kr'].unique() if x]
                                for kr in krs:
                                    mask_kr = mask_obj & (df['kr'] == kr)
                                    df_kr = df[mask_kr]
                                    
                                    # Cabeçalho do KR
                                    st.markdown(f"**KR: {kr}**")
                                    st.progress(df_kr['progresso_pct'].mean())
                                    
                                    OPCOES = list(CORES_STATUS.keys())
                                    cfg = {
                                        "tarefa": st.column_config.TextColumn("Tarefa", width="large", required=True),
                                        "progresso_pct": st.column_config.ProgressColumn("%", format="%.0f%%", min_value=0, max_value=1),
                                        "status": st.column_config.SelectboxColumn("Status", options=OPCOES, required=True),
                                        "responsavel": st.column_config.TextColumn("Resp."),
                                        "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
                                        "avanco": st.column_config.NumberColumn("Real"),
                                        "alvo": st.column_config.NumberColumn("Meta"),
                                        # Esconde colunas de contexto repetitivas
                                        "departamento": None, "objetivo": None, "kr": None, "cliente": None, "id": None
                                    }
                                    
                                    # EDITOR DE TAREFAS (Aqui você pode adicionar múltiplas tarefas por KR)
                                    edited_kr = st.data_editor(
                                        df_kr,
                                        column_config=cfg,
                                        use_container_width=True,
                                        num_rows="dynamic",
                                        key=f"ed_{depto}_{obj}_{kr}",
                                        hide_index=True
                                    )
                                    
                                    # SE HOUVER ALTERAÇÃO NO EDITOR
                                    if not edited_kr.equals(df_kr):
                                        # 1. Recalcula
                                        edited_kr['progresso_pct'] = edited_kr.apply(calcular_progresso, axis=1)
                                        # 2. Garante integridade (preenche colunas ocultas nas novas linhas)
                                        edited_kr['departamento'] = depto
                                        edited_kr['objetivo'] = obj
                                        edited_kr['kr'] = kr # Garante que novas linhas pertençam a este KR
                                        edited_kr['cliente'] = cliente_atual
                                        if 'status' in edited_kr.columns:
                                            edited_kr['status'] = edited_kr['status'].fillna('Não Iniciado')

                                        # 3. Atualiza Master na Memória (Remove antigas -> Põe novas)
                                        df_sem_kr = st.session_state['df_master'].drop(df_kr.index)
                                        st.session_state['df_master'] = pd.concat([df_sem_kr, edited_kr], ignore_index=True)
                                        
                                        # 4. Marca flag de salvar e atualiza interface
                                        st.session_state['needs_save'] = True
                                        st.rerun()

                                with st.popover("➕ Novo KR neste Objetivo"):
                                    novo_kr_nome = st.text_input("Nome do novo KR:", key=f"new_kr_in_{obj}")
                                    if st.button("Adicionar KR", key=f"btn_add_kr_{obj}"):
                                        if novo_kr_nome:
                                            # Cria uma linha inicial para o novo KR
                                            linha_nova = {
                                                'departamento': depto, 'objetivo': obj, 'kr': novo_kr_nome, 'tarefa': 'Tarefa Inicial',
                                                'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0, 
                                                'prazo': pd.to_datetime(date.today()), 'responsavel': '', 'cliente': cliente_atual
                                            }
                                            st.session_state['df_master'] = pd.concat([st.session_state['df_master'], pd.DataFrame([linha_nova])], ignore_index=True)
                                            st.session_state['needs_save'] = True
                                            st.rerun()

        st.divider()
        with st.expander("Exportar Dados"):
            st.download_button("Baixar Excel", converter_excel(df), "okrs.xlsx")
