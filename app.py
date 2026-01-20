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
    "Concluído": "#bef533",      # Verde Lima Neon
    "Em Andamento": "#7371ff",   # Roxo/Azul
    "Pausado": "#ffd166",        # Amarelo
    "Não Iniciado": "#ff5a34"    # Laranja
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

def carregar_dados_cliente(cliente_nome):
    try:
        query = text("SELECT * FROM okrs WHERE cliente = :cli")
        df = run_query(query, params={'cli': cliente_nome})
        colunas = ['departamento', 'objetivo', 'kr', 'tarefa', 'status', 'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct', 'cliente']
        if df.empty: return pd.DataFrame(columns=colunas)
        
        if 'prazo' in df.columns: df['prazo'] = pd.to_datetime(df['prazo'], errors='coerce')
        cols_num = ['avanco', 'alvo', 'progresso_pct']
        for c in cols_num: 
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
            
        if 'id' in df.columns: del df['id']
        if 'created_at' in df.columns: del df['created_at']
            
        return df
    except: return pd.DataFrame()

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
        return min(max(float(row['avanco']) / float(row['alvo']), 0.0), 1.0) if float(row['alvo']) > 0 else 0.0
    except: return 0.0

def converter_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp = df.copy()
        if 'prazo' in df_exp.columns: df_exp['prazo'] = df_exp['prazo'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '')
        df_exp.to_excel(writer, index=False)
    return output.getvalue()

# --- 4. SESSÃO ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'df_master' not in st.session_state: st.session_state['df_master'] = pd.DataFrame()

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
                        st.session_state['df_master'] = carregar_dados_cliente(user_data['cliente'])
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
    df = st.session_state['df_master']
    lista_deptos = gerenciar_departamentos(cliente_atual)

    # --- MENU LATERAL ---
    with st.sidebar:
        st.markdown(f"### {cliente_atual}")
        st.caption(f"Olá, {user['name']}")
        
        pagina = st.radio("Menu", ["Painel de Gestão", "Dashboard"])
        
        if st.button("Sair"):
            st.session_state['user'] = None
            st.session_state['df_master'] = pd.DataFrame()
            st.rerun()
        
        st.divider()
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

            st.divider()
            if lista_deptos:
                with st.form("quick"):
                    d = st.selectbox("Depto", lista_deptos)
                    o = st.text_input("Objetivo")
                    if st.form_submit_button("Criar") and o:
                        novo = {'departamento': d, 'objetivo': o, 'kr': '', 'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0, 'prazo': pd.to_datetime(date.today()), 'tarefa': '', 'responsavel': '', 'cliente': cliente_atual}
                        df_novo = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                        st.session_state['df_master'] = df_novo
                        salvar_dados_cliente(df_novo, cliente_atual)
                        st.rerun()

    # --- PÁGINA: DASHBOARD ---
    if pagina == "Dashboard":
        st.title("Dashboard")
        
        if df.empty:
            st.info("Cadastre objetivos e KRs para visualizar os gráficos.")
        else:
            df_krs = df[df['kr'] != '']
            
            if df_krs.empty:
                st.warning("Adicione KRs para visualizar as métricas.")
            else:
                # --- DADOS ---
                total_krs = len(df_krs)
                media_progresso = df_krs['progresso_pct'].mean()
                pct_display = int(media_progresso * 100)
                
                # --- VISUALIZAÇÃO DE TOPO (KPIs + Anel) ---
                col_left, col_ring, col_right = st.columns([1, 2, 1])
                
                with col_left:
                    st.metric("Total de KRs", total_krs)
                    st.write("")
                    st.metric("Objetivos Macro", df['objetivo'].nunique())

                with col_ring:
                    # GRÁFICO DE ANEL (Progress Ring Moderno)
                    # Cria dois valores: O preenchido e o restante (vazio)
                    val_preenchido = media_progresso
                    val_vazio = 1.0 - media_progresso
                    
                    # Define a cor baseada no nível (para dar um charme)
                    cor_anel = "#bef533" # Verde padrão
                    if pct_display < 40: cor_anel = "#ff5a34" # Laranja se estiver baixo
                    
                    fig_ring = go.Figure(data=[go.Pie(
                        values=[val_preenchido, val_vazio],
                        hole=0.85, # Buraco grande para ficar fino
                        marker_colors=[cor_anel, '#e6e6e6'], # Cor vs Cinza Claro
                        direction='clockwise',
                        sort=False,
                        textinfo='none', # Sem texto nas fatias
                        hoverinfo='none'
                    )])
                    
                    # Texto no centro do anel
                    fig_ring.update_layout(
                        showlegend=False,
                        annotations=[dict(text=f"{pct_display}%", x=0.5, y=0.5, font_size=40, showarrow=False, font_weight='bold')],
                        margin=dict(l=20, r=20, t=20, b=20),
                        height=200
                    )
                    st.plotly_chart(fig_ring, use_container_width=True)
                    st.caption(f"<center>Atingimento Global</center>", unsafe_allow_html=True)

                with col_right:
                    krs_concluidos = len(df_krs[df_krs['progresso_pct'] >= 1.0])
                    st.metric("Concluídos", krs_concluidos)
                    st.write("")
                    krs_atrasados = len(df_krs[df_krs['status'] == 'Pausado']) # Exemplo
                    st.metric("Pausados", krs_atrasados)

                st.divider()

                # --- GRÁFICOS INFERIORES ---
                c1, c2 = st.columns([2, 1])
                
                with c1:
                    st.subheader("Volume por Departamento")
                    df_bar = df_krs.groupby(['departamento', 'status']).size().reset_index(name='contagem')
                    
                    # BARRA HORIZONTAL (orientation='h')
                    fig_bar = px.bar(
                        df_bar, 
                        y="departamento", # Y agora é a categoria
                        x="contagem",     # X agora é o valor
                        color="status",
                        orientation='h',  # Mágica aqui
                        color_discrete_map=CORES_STATUS, 
                        text_auto=True
                    )
                    # Limpeza visual do gráfico
                    fig_bar.update_layout(
                        xaxis_visible=False, # Remove números embaixo
                        yaxis_title=None,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        legend_title_text=''
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                    
                with c2:
                    st.subheader("Status Global")
                    df_pie = df_krs['status'].value_counts().reset_index()
                    df_pie.columns = ['status', 'contagem']
                    
                    # PIZZA (Sem hole)
                    fig_pie = px.pie(
                        df_pie, 
                        values='contagem', 
                        names='status',
                        color='status',
                        color_discrete_map=CORES_STATUS
                    )
                    # Borda branca para destacar as fatias
                    fig_pie.update_traces(marker=dict(line=dict(color='#ffffff', width=2)))
                    fig_pie.update_layout(
                        showlegend=True,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        margin=dict(l=0, r=0, t=0, b=0)
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

    # --- PÁGINA: PAINEL DE GESTÃO ---
    elif pagina == "Painel de Gestão":
        st.title(f"Painel de Gestão")
        
        if not lista_deptos:
            st.info("Comece adicionando departamentos no menu lateral.")
        elif df.empty:
            st.info("Nenhum objetivo cadastrado.")
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
                            mask_krs = mask_obj & (df['kr'] != '')
                            prog = df[mask_krs]['progresso_pct'].mean() if not df[mask_krs].empty else 0.0
                            prog = max(0.0, min(1.0, float(prog)))
                            
                            with st.expander(f"{obj} | {int(prog*100)}%", expanded=True):
                                c1, c2 = st.columns([5,1])
                                with c1:
                                    no = st.text_input("Objetivo", value=obj, key=f"o_{depto}_{obj}", label_visibility="collapsed")
                                    if no != obj:
                                        st.session_state['df_master'].loc[mask_obj, 'objetivo'] = no
                                        salvar_dados_cliente(st.session_state['df_master'], cliente_atual)
                                        st.rerun()
                                with c2:
                                    if st.button("Excluir", key=f"d_{depto}_{obj}"):
                                        st.session_state['df_master'] = st.session_state['df_master'][~mask_obj]
                                        salvar_dados_cliente(st.session_state['df_master'], cliente_atual)
                                        st.rerun()
                                        
                                krs = [x for x in df[mask_obj]['kr'].unique() if x]
                                for kr in krs:
                                    mask_kr = mask_obj & (df['kr'] == kr)
                                    df_kr = df[mask_kr]
                                    
                                    st.markdown(f"**KR: {kr}**")
                                    st.progress(df_kr['progresso_pct'].mean())
                                    
                                    OPCOES = list(CORES_STATUS.keys()) 
                                    
                                    cfg = {
                                        "progresso_pct": st.column_config.ProgressColumn("Progresso", format="%.0f%%", min_value=0, max_value=1),
                                        "status": st.column_config.SelectboxColumn("Status", options=OPCOES, required=True),
                                        "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
                                        "departamento": None, "objetivo": None, "kr": None, "cliente": None
                                    }
                                    
                                    ed = st.data_editor(
                                        df_kr, 
                                        column_config=cfg, 
                                        use_container_width=True, 
                                        num_rows="dynamic", 
                                        key=f"e_{depto}_{obj}_{kr}",
                                        hide_index=True 
                                    )
                                    
                                    if not ed.equals(df_kr):
                                        ed['progresso_pct'] = ed.apply(calcular_progresso, axis=1)
                                        ed['departamento'] = depto; ed['objetivo'] = obj; ed['kr'] = kr; ed['cliente'] = cliente_atual
                                        st.session_state['df_master'] = pd.concat([st.session_state['df_master'].drop(df_kr.index), ed], ignore_index=True)
                                        salvar_dados_cliente(st.session_state['df_master'], cliente_atual)
                                        st.rerun()
                                        
                                with st.popover("Novo KR"):
                                    nk = st.text_input("Nome", key=f"nk_{obj}")
                                    if st.button("Salvar KR", key=f"bk_{obj}") and nk:
                                        d = {'departamento': depto, 'objetivo': obj, 'kr': nk, 'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0, 'prazo': pd.to_datetime(date.today()), 'tarefa': '', 'responsavel': '', 'cliente': cliente_atual}
                                        st.session_state['df_master'] = pd.concat([st.session_state['df_master'], pd.DataFrame([d])], ignore_index=True)
                                        salvar_dados_cliente(st.session_state['df_master'], cliente_atual)
                                        st.rerun()

        st.divider()
        with st.expander("Exportar"):
            st.download_button("Excel", converter_excel(df), "okrs.xlsx")
