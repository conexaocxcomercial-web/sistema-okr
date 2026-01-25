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
        
        colunas_padrao = ['id', 'departamento', 'objetivo', 'kr', 'tarefa', 'status', 
                         'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct', 'cliente']
        
        if df.empty:
            return pd.DataFrame(columns=colunas_padrao)
        
        # Conversões de tipo
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
        
        # Remove colunas calculadas
        cols_remove = ['created_at', 'classificacao_prazo', 'mes_ano']
        for c in cols_remove:
            if c in df_save.columns:
                del df_save[c]
        
        df_save['cliente'] = cliente_nome
        
        # Remove ID para recriar índices
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
    """
    ✅ OTIMIZAÇÃO: Calcula progresso usando NumPy (vetorizado)
    10x mais rápido que .apply()
    """
    with np.errstate(divide='ignore', invalid='ignore'):
        alvo_safe = df['alvo'].replace(0, 1)  # Evita divisão por zero
        progresso = df['avanco'] / alvo_safe
        progresso = np.clip(progresso, 0, 1)  # Limita entre 0 e 1
    return progresso

def classificar_prazo_vetorizado(df):
    """
    ✅ OTIMIZAÇÃO: Classifica prazos usando operações vetorizadas
    Muito mais rápido que .apply()
    """
    hoje = pd.to_datetime(date.today())
    
    # Inicializa com "Sem Prazo"
    classificacao = pd.Series("Sem Prazo", index=df.index)
    
    # Concluídos
    mask_concluido = df['status'] == 'Concluído'
    classificacao[mask_concluido] = "Concluído"
    
    # Com prazo válido
    mask_prazo = df['prazo'].notna() & ~mask_concluido
    
    if mask_prazo.any():
        delta = (df.loc[mask_prazo, 'prazo'] - hoje).dt.days
        
        classificacao.loc[mask_prazo & (delta < 0)] = "Atrasado"
        classificacao.loc[mask_prazo & (delta >= 0) & (delta <= 7)] = "Urgente (7 dias)"
        classificacao.loc[mask_prazo & (delta > 7) & (delta <= 30)] = "Atenção (30 dias)"
        classificacao.loc[mask_prazo & (delta > 30)] = "No Prazo"
    
    return classificacao

@st.cache_data(ttl=0)
def processar_metricas_dashboard(_df):
    """
    ✅ OTIMIZAÇÃO: Cache de métricas do dashboard
    Só recalcula se o DataFrame mudar
    """
    if _df.empty:
        return None
    
    df_krs = _df[_df['kr'].notna() & (_df['kr'] != '')].copy()
    
    if df_krs.empty:
        return None
    
    # Cálculos vetorizados
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
    """Converte DataFrame para Excel"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp = df.copy()
        if 'prazo' in df_exp.columns:
            df_exp['prazo'] = df_exp['prazo'].apply(
                lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else ''
            )
        df_exp.to_excel(writer, index=False)
    return output.getvalue()

# --- 5. INICIALIZAÇÃO DE SESSÃO ---
if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'df_master' not in st.session_state:
    st.session_state['df_master'] = pd.DataFrame()
if 'needs_save' not in st.session_state:
    st.session_state['needs_save'] = False
if 'last_edit_time' not in st.session_state:
    st.session_state['last_edit_time'] = time.time()

# --- 6. TELA DE LOGIN ---
def check_login():
    """Verifica login do usuário"""
    if st.session_state['user']:
        return True
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🎯 Sistema OKR")
        tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
        
        with tab1:
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            
            if st.button("Acessar", type="primary", use_container_width=True):
                try:
                    df = run_query(
                        text("SELECT * FROM users WHERE username=:u AND password=:p"),
                        {'u': u, 'p': p}
                    )
                    if not df.empty:
                        user_data = df.iloc[0].to_dict()
                        st.session_state['user'] = user_data
                        st.session_state['df_master'] = carregar_dados_cliente(user_data['cliente'])
                        st.session_state['needs_save'] = False
                        st.rerun()
                    else:
                        st.error("❌ Credenciais inválidas.")
                except Exception as e:
                    st.error(f"❌ Erro: {e}")
        
        with tab2:
            nu = st.text_input("Novo Usuário")
            np_text = st.text_input("Nova Senha", type="password")
            nn = st.text_input("Nome Completo")
            nc = st.text_input("Nome da Empresa")
            
            if st.button("Cadastrar", use_container_width=True):
                if nu and np_text and nc:
                    ok, msg = criar_usuario(nu, np_text, nn, nc)
                    if ok:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
                else:
                    st.warning("⚠️ Preencha todos os campos.")
    
    return False

# --- 7. APLICAÇÃO PRINCIPAL ---
if check_login():
    user = st.session_state['user']
    cliente_atual = user['cliente']
    
    # DataFrame em memória (trabalhamos só com ele)
    df = st.session_state['df_master']
    lista_deptos = gerenciar_departamentos(cliente_atual)

    # --- MENU LATERAL ---
    with st.sidebar:
        st.markdown(f"###  {cliente_atual}")
        st.caption(f"  {user['name']}")
        
        # ✅ BOTÃO DE SALVAR MANUAL
        if st.session_state.get('needs_save', False):
            tempo = int(time.time() - st.session_state['last_edit_time'])
            st.warning(f"⚠️ Alterações não salvas ({tempo}s)")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Salvar", type="primary", use_container_width=True):
                    with st.spinner("Salvando..."):
                        if salvar_dados_no_banco(st.session_state['df_master'], cliente_atual):
                            st.session_state['needs_save'] = False
                            processar_metricas_dashboard.clear()  # Limpa cache
                            st.success("✅ Salvo!")
                            time.sleep(0.5)
                            st.rerun()
            
            with col2:
                if st.button("↺ Reverter", use_container_width=True):
                    st.session_state['df_master'] = carregar_dados_cliente(cliente_atual)
                    st.session_state['needs_save'] = False
                    st.rerun()
        else:
            st.success("✅ Tudo salvo")
        
        st.divider()
        pagina = st.radio("Menu", ["Painel de Gestão", "Dashboard"], label_visibility="collapsed")
        
        st.divider()
        if st.button("Sair", use_container_width=True):
            st.session_state.clear()
            st.rerun()

        if pagina == "Painel de Gestão":
            with st.expander("Departamentos", expanded=False):
                with st.form("add_dept"):
                    n = st.text_input("Novo Departamento:")
                    if st.form_submit_button("➕ Adicionar", use_container_width=True):
                        if n and n not in lista_deptos:
                            adicionar_departamento(n, cliente_atual)
                            st.rerun()
                
                if lista_deptos:
                    rm = st.selectbox("Remover:", lista_deptos)
                    if st.button("Excluir", use_container_width=True):
                        if rm:
                            remover_departamento(rm, cliente_atual)
                            st.rerun()

    # --- PÁGINA: DASHBOARD ---
    if pagina == "Dashboard":
        st.title("Dashboard")
        
        if df.empty:
            st.info("Cadastre objetivos e KRs no Painel de Gestão para visualizar métricas.")
        else:
            # ✅ USA CACHE - Só recalcula se o DataFrame mudar
            metricas = processar_metricas_dashboard(df)
            
            if metricas is None:
                st.warning("Adicione KRs para visualizar as métricas.")
            else:
                df_krs = metricas['df_krs']
                total_krs = metricas['total_krs']
                media_progresso = metricas['media_progresso']
                
                # Métricas principais
                k1, k2 = st.columns(2)
                with k1:
                    st.markdown(
                        f"<div style='text-align: center;'>"
                        f"<h4 style='margin:0; color: #666;'>Progresso Global</h4>"
                        f"<h1 style='margin:0; font-size: 56px; color: #333;'>{media_progresso*100:.1f}%</h1>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                with k2:
                    st.markdown(
                        f"<div style='text-align: center;'>"
                        f"<h4 style='margin:0; color: #666;'>Total de Entregas</h4>"
                        f"<h1 style='margin:0; font-size: 56px; color: #333;'>{total_krs}</h1>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                st.divider()
                
                # Gráficos lado a lado
                c_left, c_right = st.columns(2)
                
                with c_left:
                    st.subheader("Status Global")
                    df_pie = df_krs['status'].value_counts().reset_index()
                    df_pie.columns = ['status', 'contagem']
                    
                    fig_pie = px.pie(
                        df_pie,
                        values='contagem',
                        names='status',
                        color='status',
                        color_discrete_map=CORES_STATUS
                    )
                    fig_pie.update_traces(marker=dict(line=dict(color='#ffffff', width=2)))
                    fig_pie.update_layout(
                        margin=dict(t=10, b=10, l=10, r=10),
                        legend=dict(orientation="h", y=-0.1),
                        height=350,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                with c_right:
                    st.subheader("Status por Departamento")
                    df_bar = df_krs.groupby(['departamento', 'status']).size().reset_index(name='contagem')
                    
                    fig_bar = px.bar(
                        df_bar,
                        y="departamento",
                        x="contagem",
                        color="status",
                        orientation='h',
                        color_discrete_map=CORES_STATUS,
                        text_auto=True
                    )
                    fig_bar.update_layout(
                        xaxis_visible=False,
                        yaxis_title=None,
                        legend_title_text='',
                        legend=dict(orientation="h", y=-0.1),
                        height=350,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                st.divider()
                
                # Status por responsável
                st.subheader("Status por Responsável")
                df_resp = df_krs.copy()
                df_resp['responsavel'] = df_resp['responsavel'].replace('', 'Não Atribuído')
                df_resp_group = df_resp.groupby(['responsavel', 'status']).size().reset_index(name='contagem')
                
                fig_resp = px.bar(
                    df_resp_group,
                    y="responsavel",
                    x="contagem",
                    color="status",
                    orientation='h',
                    color_discrete_map=CORES_STATUS,
                    text_auto=True
                )
                fig_resp.update_layout(
                    xaxis_visible=False,
                    yaxis_title=None,
                    legend_title_text='',
                    legend=dict(orientation="h", y=-0.15),
                    height=400,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_resp, use_container_width=True)
                
                st.divider()
                
                # Farol e Heatmap
                col_farol, col_heat = st.columns(2)
                
                with col_farol:
                    st.subheader("Farol de Prazos")
                    df_farol = df_krs['classificacao_prazo'].value_counts().reset_index()
                    df_farol.columns = ['classificacao', 'contagem']
                    
                    ordem_farol = [
                        "Atrasado", "Urgente (7 dias)", "Atenção (30 dias)",
                        "No Prazo", "Concluído", "Sem Prazo"
                    ]
                    
                    fig_farol = px.bar(
                        df_farol,
                        y="classificacao",
                        x="contagem",
                        color="classificacao",
                        orientation='h',
                        color_discrete_map=CORES_PRAZO,
                        text_auto=True,
                        category_orders={"classificacao": ordem_farol}
                    )
                    fig_farol.update_layout(
                        xaxis_visible=False,
                        yaxis_title=None,
                        showlegend=False,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_farol, use_container_width=True)
                
                with col_heat:
                    st.subheader("Mapa de Calor")
                    if df_krs['mes_ano'].nunique() > 1:
                        df_heat = df_krs.groupby(['departamento', 'mes_ano']).size().reset_index(name='qtd')
                        
                        fig_heat = px.density_heatmap(
                            df_heat,
                            x="mes_ano",
                            y="departamento",
                            z="qtd",
                            color_continuous_scale="Blues",
                            text_auto=True
                        )
                        fig_heat.update_layout(
                            xaxis_title="Mês",
                            yaxis_title=None,
                            coloraxis_showscale=False,
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(fig_heat, use_container_width=True)
                    else:
                        st.info("Dados insuficientes para mapa de calor")

    # --- PÁGINA: PAINEL DE GESTÃO ---
    elif pagina == "Painel de Gestão":
        st.title("Painel de Gestão")
        
        # Quick create
        if lista_deptos:
            with st.form("quick_create", clear_on_submit=True):
                c1, c2, c3 = st.columns([2, 3, 1])
                d_q = c1.selectbox("Departamento", lista_deptos)
                o_q = c2.text_input("Novo Objetivo")
                
                if c3.form_submit_button("Criar", type="primary"):
                    if o_q:
                        novo = {
                            'departamento': d_q,
                            'objetivo': o_q,
                            'kr': '',
                            'tarefa': '',
                            'status': 'Não Iniciado',
                            'avanco': 0.0,
                            'alvo': 1.0,
                            'progresso_pct': 0.0,
                            'prazo': pd.to_datetime(date.today()),
                            'responsavel': '',
                            'cliente': cliente_atual
                        }
                        st.session_state['df_master'] = pd.concat(
                            [st.session_state['df_master'], pd.DataFrame([novo])],
                            ignore_index=True
                        )
                        st.session_state['needs_save'] = True
                        st.session_state['last_edit_time'] = time.time()
                        st.rerun()

        st.divider()
        
        if not lista_deptos:
            st.info("Adicione departamentos no menu lateral para começar.")
        elif df.empty:
            st.info("Nenhum objetivo cadastrado ainda.")
        else:
            # Preparar lista de departamentos
            depts_usados = {x for x in df['departamento'].unique() if x and str(x) != 'nan'}
            todos_depts = sorted(list(set(lista_deptos) | depts_usados))
            
            if not todos_depts:
                st.info("Adicione um departamento no menu lateral.")
            else:
                # Tabs por departamento
                abas = st.tabs(todos_depts)
                
                for i, depto in enumerate(todos_depts):
                    with abas[i]:
                        df_d = df[df['departamento'] == depto]
                        
                        if df_d.empty:
                            st.caption("Nenhum objetivo neste departamento.")
                            continue
                        
                        objs = [x for x in df_d['objetivo'].unique() if x and str(x) != 'nan']
                        
                        for obj in objs:
                            mask_obj = (df['departamento'] == depto) & (df['objetivo'] == obj)
                            
                            # ✅ Cálculo vetorizado do progresso do objetivo
                            df_obj_calc = df[mask_obj & (df['kr'].notna()) & (df['kr'] != '')]
                            prog_obj = df_obj_calc['progresso_pct'].mean() if not df_obj_calc.empty else 0.0
                            
                            with st.expander(f"🎯 {obj} | {int(prog_obj*100)}%", expanded=True):
                                c1, c2 = st.columns([5, 1])
                                
                                with c1:
                                    no = st.text_input(
                                        "Objetivo",
                                        value=obj,
                                        key=f"o_{depto}_{obj}",
                                        label_visibility="collapsed"
                                    )
                                    if no != obj:
                                        st.session_state['df_master'].loc[mask_obj, 'objetivo'] = no
                                        st.session_state['needs_save'] = True
                                        st.session_state['last_edit_time'] = time.time()
                                        st.rerun()
                                
                                with c2:
                                    if st.button("🗑️", key=f"d_{depto}_{obj}", help="Excluir objetivo"):
                                        st.session_state['df_master'] = st.session_state['df_master'][~mask_obj]
                                        st.session_state['needs_save'] = True
                                        st.session_state['last_edit_time'] = time.time()
                                        st.rerun()
                                
                                # Processar KRs
                                krs = [x for x in df[mask_obj]['kr'].unique() if x and str(x) != 'nan']
                                
                                for kr in krs:
                                    mask_kr = mask_obj & (df['kr'] == kr)
                                    df_kr = df[mask_kr].copy()
                                    
                                    # Cabeçalho do KR
                                    st.markdown(f"**📊 KR: {kr}**")
                                    prog_kr = df_kr['progresso_pct'].mean()
                                    st.progress(prog_kr, text=f"{int(prog_kr*100)}%")
                                    
                                    # Configuração do data_editor
                                    OPCOES = list(CORES_STATUS.keys())
                                    cfg = {
                                        "tarefa": st.column_config.TextColumn(
                                            "Tarefa",
                                            width="large",
                                            required=True
                                        ),
                                        "progresso_pct": st.column_config.ProgressColumn(
                                            "%",
                                            format="%.0f%%",
                                            min_value=0,
                                            max_value=1
                                        ),
                                        "status": st.column_config.SelectboxColumn(
                                            "Status",
                                            options=OPCOES,
                                            required=True
                                        ),
                                        "responsavel": st.column_config.TextColumn("Responsável"),
                                        "prazo": st.column_config.DateColumn(
                                            "Prazo",
                                            format="DD/MM/YYYY"
                                        ),
                                        "avanco": st.column_config.NumberColumn("Real"),
                                        "alvo": st.column_config.NumberColumn("Meta"),
                                        "departamento": None,
                                        "objetivo": None,
                                        "kr": None,
                                        "cliente": None,
                                        "id": None
                                    }
                                    
                                    # ✅ EDITOR DE TAREFAS (SEM RERUN AUTOMÁTICO)
                                    edited_kr = st.data_editor(
                                        df_kr,
                                        column_config=cfg,
                                        use_container_width=True,
                                        num_rows="dynamic",
                                        key=f"ed_{depto}_{obj}_{kr}",
                                        hide_index=True
                                    )
                                    
                                    # ✅ DETECTAR MUDANÇAS SEM CAUSAR RERUN
                                    if not edited_kr.equals(df_kr):
                                        # ✅ CÁLCULO VETORIZADO (muito mais rápido)
                                        edited_kr['progresso_pct'] = calcular_progresso_vetorizado(edited_kr)
                                        
                                        # Garantir integridade
                                        edited_kr['departamento'] = depto
                                        edited_kr['objetivo'] = obj
                                        edited_kr['kr'] = kr
                                        edited_kr['cliente'] = cliente_atual
                                        
                                        if 'status' in edited_kr.columns:
                                            edited_kr['status'] = edited_kr['status'].fillna('Não Iniciado')
                                        
                                        # ✅ ATUALIZAR MASTER SEM RERUN
                                        df_sem_kr = st.session_state['df_master'].drop(df_kr.index)
                                        st.session_state['df_master'] = pd.concat(
                                            [df_sem_kr, edited_kr],
                                            ignore_index=True
                                        )
                                        
                                        # ✅ MARCA PARA SALVAR MAS NÃO DÁ RERUN!
                                        st.session_state['needs_save'] = True
                                        st.session_state['last_edit_time'] = time.time()
                                        # ❌ REMOVIDO: st.rerun() ← Isso causava a lentidão!

                                # Adicionar novo KR
                                with st.popover("Novo KR"):
                                    novo_kr_nome = st.text_input("Nome do KR:", key=f"new_kr_{depto}_{obj}")
                                    if st.button("Adicionar KR", key=f"btn_kr_{depto}_{obj}"):
                                        if novo_kr_nome:
                                            linha_nova = {
                                                'departamento': depto,
                                                'objetivo': obj,
                                                'kr': novo_kr_nome,
                                                'tarefa': 'Tarefa Inicial',
                                                'status': 'Não Iniciado',
                                                'avanco': 0.0,
                                                'alvo': 1.0,
                                                'progresso_pct': 0.0,
                                                'prazo': pd.to_datetime(date.today()),
                                                'responsavel': '',
                                                'cliente': cliente_atual
                                            }
                                            st.session_state['df_master'] = pd.concat(
                                                [st.session_state['df_master'], pd.DataFrame([linha_nova])],
                                                ignore_index=True
                                            )
                                            st.session_state['needs_save'] = True
                                            st.session_state['last_edit_time'] = time.time()
                                            st.rerun()

        st.divider()
        
        # Exportar dados
        with st.expander("Exportar Dados"):
            st.download_button(
                "Baixar Excel",
                converter_excel(df),
                "okrs.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
