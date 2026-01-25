import streamlit as st
import pandas as pd
import numpy as np
import os
import time
from io import BytesIO
from datetime import date, timedelta
from sqlalchemy import create_engine, text
import plotly.express as px

# --- 1. CONFIGURAÇÃO INICIAL E CSS ---
st.set_page_config(page_title="OKR com Conexao", layout="wide")

# CSS PERSONALIZADO (Identidade Visual)
st.markdown("""
<style>
    /* Esconde menu padrao e rodape */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Estilo dos Botoes */
    .stButton > button {
        border-radius: 6px;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 12px;
    }
    
    /* Estilo dos Inputs */
    .stTextInput > div > div > input {
        border-radius: 6px;
    }
    
    /* Titulos */
    h1, h2, h3, h4 {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #2c3e50;
        font-weight: 600;
    }
    
    /* Container de metricas */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 10px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- DEFINIÇÃO DE CORES ---
CORES_STATUS = {
    "Concluido": "#bef533",
    "Em Andamento": "#7371ff",
    "Pausado": "#ffd166",
    "Nao Iniciado": "#ff5a34"
}

# --- 2. CONEXÃO COM BANCO ---
@st.cache_resource
def get_engine():
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
    with engine.connect() as connection:
        return pd.read_sql(query, connection, params=params)

def criar_usuario(usuario, senha, nome, cliente):
    query_check = text("SELECT * FROM users WHERE username = :usr")
    df_check = run_query(query_check, params={'usr': usuario})
    if not df_check.empty:
        return False, "Usuario ja existe."
    
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (username, password, name, cliente) VALUES (:usr, :pwd, :name, :cli)"),
            {"usr": usuario, "pwd": senha, "name": nome, "cli": cliente}
        )
    return True, "Usuario criado com sucesso!"

def carregar_dados_cliente(cliente_nome):
    try:
        query = text("SELECT * FROM okrs WHERE cliente = :cli ORDER BY id ASC")
        df = run_query(query, params={'cli': cliente_nome})
        
        colunas_padrao = ['id', 'departamento', 'objetivo', 'kr', 'tarefa', 'status', 
                          'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct', 'cliente']
        
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
            connection.execute(text("DELETE FROM okrs WHERE cliente = :cli"), {"cli": cliente_nome})
            df_save.to_sql('okrs', connection, if_exists='append', index=False)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

@st.cache_data(ttl=3600)
def gerenciar_departamentos(cliente_nome):
    try:
        query = text("SELECT nome FROM departamentos WHERE cliente = :cli ORDER BY nome")
        df_dept = run_query(query, params={'cli': cliente_nome})
        return df_dept['nome'].tolist()
    except:
        return []

def adicionar_departamento(novo, cli):
    if novo:
        with engine.begin() as c:
            c.execute(text("INSERT INTO departamentos (nome, cliente) VALUES (:n, :c)"), {"n": novo, "c": cli})
        gerenciar_departamentos.clear()

def remover_departamento(nome, cli):
    with engine.begin() as c:
        c.execute(text("DELETE FROM departamentos WHERE nome = :n AND cliente = :c"), {"n": nome, "c": cli})
    gerenciar_departamentos.clear()

# --- 4. FUNÇÕES AUXILIARES E OTIMIZADAS ---
def calcular_progresso_vetorizado(df):
    with np.errstate(divide='ignore', invalid='ignore'):
        alvo_safe = df['alvo'].replace(0, 1)
        progresso = df['avanco'] / alvo_safe
        progresso = np.clip(progresso, 0, 1)
    return progresso

def classificar_prazo_vetorizado(df):
    hoje = pd.to_datetime(date.today())
    classificacao = pd.Series("Sem Prazo", index=df.index)
    
    mask_concluido = df['status'] == 'Concluido'
    classificacao[mask_concluido] = "Concluido"
    
    mask_prazo = df['prazo'].notna() & ~mask_concluido
    
    if mask_prazo.any():
        delta = (df.loc[mask_prazo, 'prazo'] - hoje).dt.days
        classificacao.loc[mask_prazo & (delta < 0)] = "Atrasado"
        classificacao.loc[mask_prazo & (delta >= 0) & (delta <= 7)] = "Urgente (7 dias)"
        classificacao.loc[mask_prazo & (delta > 7) & (delta <= 30)] = "Atencao (30 dias)"
        classificacao.loc[mask_prazo & (delta > 30)] = "No Prazo"
    return classificacao

def badge_status_html(texto, cor):
    return f"""
    <div style='
        display: inline-block;
        background-color: {cor}22; 
        color: {cor}; 
        padding: 4px 10px; 
        border-radius: 4px; 
        font-weight: 600; 
        font-size: 11px; 
        border: 1px solid {cor};
        letter-spacing: 0.5px;
    '>
    {texto.upper()}
    </div>
    """

@st.cache_data(ttl=0)
def processar_metricas_dashboard(_df):
    if _df.empty: return None
    df_krs = _df[_df['kr'].notna() & (_df['kr'] != '')].copy()
    if df_krs.empty: return None
    
    df_krs['classificacao_prazo'] = classificar_prazo_vetorizado(df_krs)
    if 'prazo' in df_krs.columns and pd.api.types.is_datetime64_any_dtype(df_krs['prazo']):
        df_krs['mes_ano'] = df_krs['prazo'].dt.strftime('%Y-%m')
    else:
        df_krs['mes_ano'] = "N/A"
    
    metricas = {
        'total_krs': len(df_krs),
        'media_progresso': df_krs['progresso_pct'].mean(),
        'df_krs': df_krs
    }
    return metricas

def converter_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp = df.copy()
        if 'prazo' in df_exp.columns:
            df_exp['prazo'] = df_exp['prazo'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '')
        df_exp.to_excel(writer, index=False)
    return output.getvalue()

# --- 5. INICIALIZAÇÃO DE SESSÃO ---
if 'user' not in st.session_state: st.session_state['user'] = None
if 'df_master' not in st.session_state: st.session_state['df_master'] = pd.DataFrame()
if 'needs_save' not in st.session_state: st.session_state['needs_save'] = False
if 'last_edit_time' not in st.session_state: st.session_state['last_edit_time'] = time.time()

# --- 6. TELA DE LOGIN ---
def check_login():
    if st.session_state['user']: return True
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## Gestao de OKR")
        st.caption("Acesse sua conta para continuar")
        tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
        
        with tab1:
            u = st.text_input("Usuario")
            p = st.text_input("Senha", type="password")
            if st.button("ACESSAR", type="primary", use_container_width=True):
                try:
                    df = run_query(text("SELECT * FROM users WHERE username=:u AND password=:p"), {'u': u, 'p': p})
                    if not df.empty:
                        user_data = df.iloc[0].to_dict()
                        st.session_state['user'] = user_data
                        st.session_state['df_master'] = carregar_dados_cliente(user_data['cliente'])
                        st.session_state['needs_save'] = False
                        st.rerun()
                    else:
                        st.error("Credenciais invalidas.")
                except Exception as e:
                    st.error(f"Erro: {e}")
        
        with tab2:
            nu = st.text_input("Novo Usuario")
            np_text = st.text_input("Nova Senha", type="password")
            nn = st.text_input("Nome Completo")
            nc = st.text_input("Nome da Empresa")
            if st.button("CADASTRAR", use_container_width=True):
                if nu and np_text and nc:
                    ok, msg = criar_usuario(nu, np_text, nn, nc)
                    if ok: st.success(f"{msg}")
                    else: st.error(f"{msg}")
                else:
                    st.warning("Preencha todos os campos.")
    return False

# --- 7. APLICAÇÃO PRINCIPAL ---
if check_login():
    user = st.session_state['user']
    cliente_atual = user['cliente']
    df = st.session_state['df_master']
    lista_deptos = gerenciar_departamentos(cliente_atual)

    # --- MENU LATERAL (Sidebar) ---
    with st.sidebar:
        st.markdown(f"**{cliente_atual}**")
        st.caption(f"Usuario: {user['name']}")
        
        st.divider()
        
        # BUSCA GLOBAL
        st.markdown("### Busca Rapida")
        termo_busca = st.text_input("Pesquisar tarefa ou KR...", placeholder="Digite para buscar")
        
        st.divider()
        
        # BOTÕES DE AÇÃO
        if st.session_state.get('needs_save', False):
            st.warning("Alteracoes pendentes")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("SALVAR", type="primary", use_container_width=True):
                    with st.spinner("Salvando..."):
                        if salvar_dados_no_banco(st.session_state['df_master'], cliente_atual):
                            st.session_state['needs_save'] = False
                            processar_metricas_dashboard.clear()
                            st.toast("Dados salvos com sucesso!", icon=None)
                            time.sleep(1)
                            st.rerun()
            with col2:
                if st.button("REVERTER", use_container_width=True):
                    st.session_state['df_master'] = carregar_dados_cliente(cliente_atual)
                    st.session_state['needs_save'] = False
                    st.rerun()
        else:
            st.info("Todos os dados salvos")
            
        st.divider()
        pagina = st.radio("Navegacao", ["Painel de Gestao", "Dashboard"])
        
        # RESUMO RÁPIDO
        if not df.empty:
            st.divider()
            total_pendente = len(df[df['status'] != 'Concluido'])
            st.metric("Tarefas Pendentes", total_pendente)
            
        st.divider()
        if st.button("SAIR", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        if pagina == "Painel de Gestao":
            with st.expander("Configuracoes"):
                st.caption("Gerenciar Departamentos")
                with st.form("add_dept"):
                    n = st.text_input("Novo Departamento:")
                    if st.form_submit_button("ADICIONAR", use_container_width=True):
                        if n and n not in lista_deptos:
                            adicionar_departamento(n, cliente_atual)
                            st.rerun()
                if lista_deptos:
                    rm = st.selectbox("Selecione para remover:", lista_deptos)
                    if st.button("REMOVER DEPARTAMENTO", use_container_width=True):
                        if rm:
                            remover_departamento(rm, cliente_atual)
                            st.rerun()

    # --- PÁGINA: DASHBOARD (COM GANTT) ---
    if pagina == "Dashboard":
        st.title("Dashboard Estrategico")
        
        if df.empty:
            st.info("Cadastre objetivos e KRs no Painel de Gestao para visualizar metricas.")
        else:
            metricas = processar_metricas_dashboard(df)
            if metricas is None:
                st.warning("Adicione KRs para visualizar as metricas.")
            else:
                df_krs = metricas['df_krs']
                
                # Indicadores Topo
                k1, k2, k3 = st.columns(3)
                k1.metric("Progresso Global", f"{metricas['media_progresso']*100:.1f}%")
                k2.metric("Total de Entregas", metricas['total_krs'])
                k3.metric("Concluidos", len(df_krs[df_krs['status'] == 'Concluido']))
                
                st.markdown("---")
                
                # CRONOGRAMA DE GANTT
                st.subheader("Cronograma de Entregas")
                df_gantt = df_krs[df_krs['prazo'].notna()].copy()
                if not df_gantt.empty:
                    df_gantt['inicio'] = df_gantt['prazo'] - pd.to_timedelta(30, unit='D')
                    
                    fig_gantt = px.timeline(
                        df_gantt, 
                        x_start="inicio", 
                        x_end="prazo", 
                        y="kr", 
                        color="status",
                        hover_data=["objetivo", "responsavel", "departamento"],
                        color_discrete_map=CORES_STATUS
                    )
                    fig_gantt.update_yaxes(autorange="reversed") 
                    fig_gantt.update_layout(height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis_title="Linha do Tempo")
                    st.plotly_chart(fig_gantt, use_container_width=True)
                else:
                    st.info("Defina prazos nos seus KRs para visualizar o cronograma.")

                # Gráficos Inferiores
                c_left, c_right = st.columns(2)
                with c_left:
                    st.caption("Status Global")
                    df_pie = df_krs['status'].value_counts().reset_index()
                    df_pie.columns = ['status', 'contagem']
                    fig_pie = px.pie(df_pie, values='contagem', names='status', color='status', color_discrete_map=CORES_STATUS)
                    fig_pie.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0))
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                with c_right:
                    st.caption("Entregas por Departamento")
                    df_bar = df_krs.groupby(['departamento', 'status']).size().reset_index(name='contagem')
                    fig_bar = px.bar(df_bar, y="departamento", x="contagem", color="status", orientation='h', color_discrete_map=CORES_STATUS, text_auto=True)
                    fig_bar.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0), yaxis_title=None)
                    st.plotly_chart(fig_bar, use_container_width=True)

    # --- PÁGINA: PAINEL DE GESTÃO ---
    elif pagina == "Painel de Gestao":
        
        # MODO BUSCA GLOBAL
        if termo_busca:
            st.subheader(f"Resultados da busca: '{termo_busca}'")
            mask_busca = df.apply(lambda row: row.astype(str).str.contains(termo_busca, case=False).any(), axis=1)
            df_busca = df[mask_busca]
            
            if not df_busca.empty:
                st.dataframe(
                    df_busca[['departamento', 'objetivo', 'kr', 'tarefa', 'status', 'prazo']],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("Nenhum resultado encontrado.")
        
        else:
            # MODO NORMAL (Master-Detail)
            col_header, col_btn = st.columns([6, 1])
            with col_header:
                st.title("Painel de Gestao")
            
            with col_btn:
                with st.popover("NOVO", use_container_width=True):
                    st.markdown("### Adicionar Objetivo")
                    if lista_deptos:
                        with st.form("quick_create_pop", clear_on_submit=True):
                            d_q = st.selectbox("Departamento", lista_deptos)
                            o_q = st.text_input("Novo Objetivo")
                            if st.form_submit_button("CRIAR", type="primary"):
                                if o_q:
                                    novo = {
                                        'departamento': d_q, 'objetivo': o_q, 'kr': '', 'tarefa': '',
                                        'status': 'Nao Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0,
                                        'prazo': pd.to_datetime(date.today()), 'responsavel': '', 'cliente': cliente_atual
                                    }
                                    st.session_state['df_master'] = pd.concat([st.session_state['df_master'], pd.DataFrame([novo])], ignore_index=True)
                                    st.session_state['needs_save'] = True
                                    st.toast("Objetivo criado!", icon=None)
                                    time.sleep(0.5)
                                    st.rerun()
                    else:
                        st.warning("Cadastre um departamento no menu lateral.")

            st.markdown("---")

            if not lista_deptos:
                st.info("Comece adicionando departamentos no menu lateral.")
            elif df.empty:
                st.info("Clique em 'NOVO' para começar.")
            else:
                # 1. FILTRO DE DEPARTAMENTO
                depts_usados = {x for x in df['departamento'].unique() if x and str(x) != 'nan'}
                todos_depts = sorted(list(set(lista_deptos) | depts_usados))
                
                c_filter1, c_filter2 = st.columns([1, 3])
                with c_filter1:
                    depto_selecionado = st.selectbox("Filtrar Departamento", todos_depts)
                
                df_depto = df[df['departamento'] == depto_selecionado]
                
                # 2. MASTER VIEW (Tabela de Objetivos)
                if not df_depto.empty:
                    resumo_objs = df_depto.groupby('objetivo').agg({
                        'progresso_pct': 'mean',
                        'status': lambda x: x.mode()[0] if not x.mode().empty else 'Nao Iniciado'
                    }).reset_index()
                    
                    with c_filter2:
                        st.info(f"{len(resumo_objs)} objetivos em **{depto_selecionado}**")
                    
                    st.caption("Selecione um objetivo para ver detalhes")
                    event = st.dataframe(
                        resumo_objs,
                        column_config={
                            "progresso_pct": st.column_config.ProgressColumn("Progresso", format="%.0f%%"),
                            "status": st.column_config.Column("Status Geral"),
                            "objetivo": st.column_config.TextColumn("Objetivo", width="large")
                        },
                        use_container_width=True,
                        hide_index=True,
                        on_select="rerun",
                        selection_mode="single-row"
                    )
                    
                    # 3. DETAIL VIEW (Detalhes do Objetivo)
                    if len(event.selection.rows) > 0:
                        index_selecionado = event.selection.rows[0]
                        obj_selecionado = resumo_objs.iloc[index_selecionado]['objetivo']
                        
                        st.markdown("---")
                        
                        # Cabeçalho do Objetivo
                        c_tit, c_act = st.columns([5, 1])
                        with c_tit:
                             st.markdown(f"## {obj_selecionado}")
                        with c_act:
                            if st.button("EXCLUIR OBJ", key=f"del_obj_{obj_selecionado}"):
                                mask_obj_del = (df['departamento'] == depto_selecionado) & (df['objetivo'] == obj_selecionado)
                                st.session_state['df_master'] = st.session_state['df_master'][~mask_obj_del]
                                st.session_state['needs_save'] = True
                                st.toast("Objetivo excluido")
                                st.rerun()

                        # Listagem de KRs
                        mask_obj = (df['departamento'] == depto_selecionado) & (df['objetivo'] == obj_selecionado)
                        krs = [x for x in df[mask_obj]['kr'].unique() if x and str(x) != 'nan']
                        
                        if not krs:
                            st.warning("Este objetivo nao possui Resultados Chave (KR).")
                        
                        for kr in krs:
                            mask_kr = mask_obj & (df['kr'] == kr)
                            df_kr = df[mask_kr].copy()
                            status_kr = df_kr['status'].iloc[0] if not df_kr.empty else "Nao Iniciado"
                            cor_badge = CORES_STATUS.get(status_kr, "#ccc")
                            
                            # --- CORREÇÃO AQUI ---
                            # Separação de Título e Badge em colunas para evitar conflito HTML
                            c_kr_title, c_kr_badge = st.columns([4, 1])
                            
                            with c_kr_title:
                                st.markdown(f"#### {kr}")
                            
                            with c_kr_badge:
                                st.markdown(
                                    f"<div style='text-align: right; margin-top: 10px;'>{badge_status_html(status_kr, cor_badge)}</div>", 
                                    unsafe_allow_html=True
                                )
                            # ---------------------
                            
                            st.progress(df_kr['progresso_pct'].mean(), text=f"{int(df_kr['progresso_pct'].mean()*100)}%")
                            
                            # Filtros e Ações do KR
                            c_tool1, c_tool2, c_tool3 = st.columns([3, 1, 1])
                            with c_tool2:
                                if st.button("DUPLICAR KR", key=f"dup_{obj_selecionado}_{kr}"):
                                    novo_df_kr = df_kr.copy()
                                    novo_df_kr['kr'] = f"{kr} (Copia)"
                                    novo_df_kr['status'] = "Nao Iniciado"
                                    novo_df_kr['progresso_pct'] = 0.0
                                    novo_df_kr['avanco'] = 0.0
                                    st.session_state['df_master'] = pd.concat([st.session_state['df_master'], novo_df_kr], ignore_index=True)
                                    st.session_state['needs_save'] = True
                                    st.toast("KR Duplicado!")
                                    st.rerun()
                                    
                            with c_tool3:
                                ver_concluidos = st.toggle("Ver Concluidos", value=False, key=f"tgl_{obj_selecionado}_{kr}")
                            
                            # Editor
                            df_editor_view = df_kr.copy()
                            if not ver_concluidos:
                                df_editor_view = df_editor_view[df_editor_view['status'] != 'Concluido']
                            
                            OPCOES = list(CORES_STATUS.keys())
                            cfg = {
                                "tarefa": st.column_config.TextColumn("Tarefa", width="large", required=True),
                                "progresso_pct": st.column_config.ProgressColumn("%", format="%.0f%%", min_value=0, max_value=1),
                                "status": st.column_config.SelectboxColumn("Status", options=OPCOES, required=True),
                                "responsavel": st.column_config.TextColumn("Responsavel"),
                                "prazo": st.column_config.DateColumn("Prazo", format="DD/MM/YYYY"),
                                "avanco": st.column_config.NumberColumn("Real"),
                                "alvo": st.column_config.NumberColumn("Meta"),
                                "departamento": None, "objetivo": None, "kr": None, "cliente": None, "id": None
                            }
                            
                            edited_kr = st.data_editor(
                                df_editor_view, column_config=cfg, use_container_width=True,
                                num_rows="dynamic", key=f"ed_{obj_selecionado}_{kr}", hide_index=True
                            )
                            
                            if not edited_kr.equals(df_editor_view):
                                edited_kr['progresso_pct'] = calcular_progresso_vetorizado(edited_kr)
                                edited_kr['departamento'] = depto_selecionado
                                edited_kr['objetivo'] = obj_selecionado
                                edited_kr['kr'] = kr
                                edited_kr['cliente'] = cliente_atual
                                if 'status' in edited_kr.columns: edited_kr['status'] = edited_kr['status'].fillna('Nao Iniciado')
                                
                                indices_visiveis = df_editor_view.index
                                df_temp = st.session_state['df_master'].drop(indices_visiveis)
                                st.session_state['df_master'] = pd.concat([df_temp, edited_kr], ignore_index=True)
                                st.session_state['needs_save'] = True
                                st.session_state['last_edit_time'] = time.time()
                        
                        # Adicionar KR
                        with st.popover("ADICIONAR NOVO KR"):
                            nk = st.text_input("Nome do KR:", key=f"nkr_{obj_selecionado}")
                            if st.button("SALVAR KR", key=f"bkr_{obj_selecionado}"):
                                if nk:
                                    linha = {'departamento': depto_selecionado, 'objetivo': obj_selecionado, 'kr': nk, 'tarefa': 'Tarefa Inicial', 'status': 'Nao Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0, 'prazo': pd.to_datetime(date.today()), 'responsavel': '', 'cliente': cliente_atual}
                                    st.session_state['df_master'] = pd.concat([st.session_state['df_master'], pd.DataFrame([linha])], ignore_index=True)
                                    st.session_state['needs_save'] = True
                                    st.toast("KR Adicionado")
                                    st.rerun()
                    else:
                        st.info("Clique em um objetivo na tabela acima para editar.")
            
        st.markdown("---")
        with st.expander("Exportar Dados para Excel"):
            st.download_button("BAIXAR PLANILHA", converter_excel(df), "okrs_conexao.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
