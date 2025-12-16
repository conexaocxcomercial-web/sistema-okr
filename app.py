import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import date
from sqlalchemy import create_engine

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(
    page_title="Gestão de OKR", 
    layout="wide", 
    page_icon="🎯",
    initial_sidebar_state="expanded"
)

# --- CSS SEGURO (VISUAL PROFISSIONAL) ---
st.markdown("""
    <style>
        /* Importando Fonte Profissional (Inter) */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: #1e1e1e;
        }

        /* CARD DOS KRs */
        div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"][style*="border-color:"] {
            border: 1px solid #f0f0f0 !important;
            border-left: 5px solid #7371ff !important;
            background-color: white;
            border-radius: 8px;
            padding: 1.2rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.04);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"][style*="border-color:"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 15px rgba(0,0,0,0.08);
        }

        /* BARRA DE PROGRESSO NEON */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #bef533 0%, #a3d929 100%);
            border-radius: 10px;
        }
        .stProgress > div > div > div {
            background-color: #f0f0f0;
            height: 8px !important;
            border-radius: 10px;
        }
        
        /* ABAS (TABS) */
        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
            border-bottom: 1px solid #f0f0f0;
        }
        .stTabs [data-baseweb="tab"] {
            height: auto;
            border: none;
            font-weight: 500;
            color: #6b7280;
        }
        .stTabs [aria-selected="true"] {
            color: #7371ff !important;
            font-weight: 700;
            border-bottom: 2px solid #7371ff !important;
        }
        
        /* GERAL */
        .stApp { background-color: #fafafa; }
        section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #f0f0f0; }
        .stDeployButton {display:none;} footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 2. CONSTANTES ---
LISTA_DEPTOS_PADRAO = ["Comercial", "Financeiro", "Operacional", "RH", "Tecnologia", "Marketing"]
OPCOES_STATUS = ["Não Iniciado", "Em Andamento", "Pausado", "Concluído"]
LOGO_FILE = "cx_CXdata_LOGO-positiva.png"

# --- 3. CONEXÃO COM BANCO DE DADOS (SQL) ---
# Aqui está a mágica: Ele usa os SECRETS que você configurou para conectar no Supabase
conn = st.connection("postgresql", type="sql")

def carregar_dados_sql():
    try:
        # Puxa os dados da tabela 'okrs' do Supabase
        df = conn.query('SELECT * FROM okrs', ttl=0)
        
        if df.empty:
             return pd.DataFrame(columns=[
                'departamento', 'objetivo', 'kr', 'tarefa', 
                'status', 'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct'
            ])
            
        if 'prazo' in df.columns:
            df['prazo'] = pd.to_datetime(df['prazo'], errors='coerce')
        
        text_cols = ['departamento', 'objetivo', 'kr', 'tarefa', 'status', 'responsavel']
        for col in text_cols:
             if col in df.columns: df[col] = df[col].fillna('')
             
        num_cols = ['avanco', 'alvo', 'progresso_pct']
        for col in num_cols:
             if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
             
        return df
    except Exception as e:
        return pd.DataFrame(columns=[
            'departamento', 'objetivo', 'kr', 'tarefa', 
            'status', 'responsavel', 'prazo', 'avanco', 'alvo', 'progresso_pct'
        ])

def salvar_dados_sql(df):
    engine = conn.engine
    df_save = df.copy()
    # Removemos ID e Created_at para o banco gerar automaticamente
    if 'id' in df_save.columns: del df_save['id']
    if 'created_at' in df_save.columns: del df_save['created_at']
    
    # Salva no Supabase (sobrescrevendo a tabela)
    df_save.to_sql('okrs', engine, if_exists='replace', index=False)

def carregar_departamentos():
    if 'lista_deptos' not in st.session_state:
        st.session_state['lista_deptos'] = LISTA_DEPTOS_PADRAO
    return st.session_state['lista_deptos']

def calcular_progresso(row):
    try:
        av = float(row['avanco'])
        al = float(row['alvo'])
        if al > 0:
            return min(max(av / al, 0.0), 1.0)
        return 0.0
    except:
        return 0.0

def converter_para_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp = df.copy()
        if 'prazo' in df_exp.columns:
            df_exp['prazo'] = df_exp['prazo'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '')
        df_exp.to_excel(writer, index=False, sheet_name='OKRs')
    return output.getvalue()

# --- 4. INICIALIZAÇÃO DA MEMÓRIA ---
if 'df_master' not in st.session_state:
    st.session_state['df_master'] = carregar_dados_sql()

if 'password_correct' not in st.session_state:
    st.session_state['password_correct'] = False

# --- 5. TELA DE LOGIN ---
def check_password():
    if st.session_state["password_correct"]: return True
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Login")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if senha == "admin123":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    return False

# --- 6. APLICAÇÃO PRINCIPAL ---
if check_password():
    df = st.session_state['df_master']
    lista_deptos = carregar_departamentos()

    # --- MENU LATERAL ---
    with st.sidebar:
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, use_column_width=True)
            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h2 style='text-align: left; color: #7371ff;'>CX Data</h2>", unsafe_allow_html=True)
            
        st.markdown("### CONFIGURAÇÕES")
        
        with st.expander("Gerenciar Departamentos"):
            with st.form("add_dept"):
                novo = st.text_input("Novo Departamento")
                if st.form_submit_button("Adicionar"):
                    if novo and novo not in lista_deptos:
                        lista_deptos.append(novo)
                        st.session_state['lista_deptos'] = lista_deptos
                        st.rerun()
            rm_dept = st.selectbox("Remover", ["..."] + lista_deptos)
            if st.button("Remover Selecionado"):
                if rm_dept != "...":
                    lista_deptos.remove(rm_dept)
                    st.session_state['lista_deptos'] = lista_deptos
                    st.rerun()

        st.divider()
        
        st.markdown("### OPERACIONAL")
        with st.form("quick_add"):
            st.caption("Novo Objetivo Macro")
            d = st.selectbox("Departamento", lista_deptos)
            o = st.text_input("Nome do Objetivo")
            if st.form_submit_button("Criar Objetivo"):
                if o:
                    novo_okr = {
                        'departamento': d, 'objetivo': o, 'kr': '',
                        'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0,
                        'prazo': pd.to_datetime(date.today()), 'tarefa': '', 'responsavel': ''
                    }
                    df_novo = pd.concat([df, pd.DataFrame([novo_okr])], ignore_index=True)
                    st.session_state['df_master'] = df_novo
                    # AQUI ELE SALVA NO SUPABASE
                    salvar_dados_sql(df_novo)
                    st.rerun()
                else:
                    st.warning("Preencha o nome.")

    # --- ÁREA PRINCIPAL ---
    c_head_1, c_head_2 = st.columns([3,1])
    with c_head_1:
        st.markdown(f"<h2 style='font-weight: 700; color: #1e1e1e;'>Painel de Gestão</h2>", unsafe_allow_html=True)
        st.caption("Acompanhamento de Objetivos e Resultados Chave (Conectado ao Supabase)")

    if df.empty:
        st.info("Comece criando um Objetivo no menu lateral.")
    else:
        depts = sorted(list(set(df['departamento'].unique()) | set(lista_deptos)))
        abas = st.tabs(depts)
        
        for i, depto in enumerate(depts):
            with abas[i]:
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                df_d = df[df['departamento'] == depto]
                if df_d.empty:
                    st.info("Nenhum OKR iniciado neste departamento.")
                    continue
                
                # OBJETIVOS
                objs = [x for x in df_d['objetivo'].unique() if x]
                for obj in objs:
                    mask_obj = (df['departamento'] == depto) & (df['objetivo'] == obj)
                    
                    mask_validos = mask_obj & (df['kr'] != '')
                    if not df[mask_validos].empty:
                        prog_obj = df[mask_validos]['progresso_pct'].mean()
                    else:
                        prog_obj = 0.0

                    if pd.isna(prog_obj): prog_obj = 0.0
                    prog_obj = max(0.0, min(1.0, float(prog_obj)))
                    
                    label_obj = f"{obj}  •  {int(prog_obj*100)}%"
                    
                    with st.expander(label_obj, expanded=True):
                        
                        c_edit_obj, c_del_obj = st.columns([6, 1])
                        with c_edit_obj:
                            new_name = st.text_input("Título do Objetivo", value=obj, key=f"n_o_{depto}_{obj}", label_visibility="collapsed")
                            if new_name != obj:
                                st.session_state['df_master'].loc[mask_obj, 'objetivo'] = new_name
                                salvar_dados_sql(st.session_state['df_master'])
                                st.rerun()
                        with c_del_obj:
                            if st.button("🗑️", key=f"del_{depto}_{obj}", help="Excluir Objetivo"):
                                st.session_state['df_master'] = st.session_state['df_master'][~mask_obj]
                                salvar_dados_sql(st.session_state['df_master'])
                                st.rerun()

                        # KRs
                        st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
                        st.markdown("<div style='font-size: 0.8rem; color: #6b7280; font-weight: 600; text-transform: uppercase; margin-bottom: 0.5rem;'>Resultados Chave (KRs)</div>", unsafe_allow_html=True)
                        
                        krs = [x for x in df[mask_obj]['kr'].unique() if x]
                        
                        if not krs:
                            st.caption("Este objetivo ainda não possui KRs.")

                        for kr in krs:
                            mask_kr = mask_obj & (df['kr'] == kr)
                            df_kr = df[mask_kr] 
                            
                            prog_kr = df_kr['progresso_pct'].mean()
                            if pd.isna(prog_kr): prog_kr = 0.0
                            prog_kr = max(0.0, min(1.0, float(prog_kr)))

                            with st.container(border=True):
                                c_title, c_bar = st.columns([3, 1])
                                with c_title:
                                    st.markdown(f"<span style='font-size:1rem; font-weight:600; color:#1e1e1e;'>🎯 {kr}</span>", unsafe_allow_html=True)
                                    new_kr = st.text_input("Editar KR", value=kr, key=f"r_k_{depto}_{obj}_{kr}", label_visibility="collapsed")
                                    if new_kr != kr:
                                        st.session_state['df_master'].loc[mask_kr, 'kr'] = new_kr
                                        salvar_dados_sql(st.session_state['df_master'])
                                        st.rerun()
                                
                                with c_bar:
                                    st.progress(prog_kr, text=f"{int(prog_kr*100)}%")
                                
                                st.markdown("<div style='margin-top:12px; margin-bottom: 4px; font-size:0.75rem; font-weight:600; color:#6b7280; text-transform:uppercase;'>Tarefas & Ações</div>", unsafe_allow_html=True)
                                
                                col_cfg = {
                                    "progresso_pct": st.column_config.ProgressColumn(label="Progresso (%)", format="%.0f%%", min_value=0, max_value=1),
                                    "status": st.column_config.SelectboxColumn(label="Status", options=OPCOES_STATUS, required=True),
                                    "prazo": st.column_config.DateColumn(label="Prazo", format="DD/MM/YYYY"),
                                    "tarefa": st.column_config.TextColumn(label="Tarefa"),
                                    "responsavel": st.column_config.TextColumn(label="Responsável"),
                                    "avanco": st.column_config.NumberColumn(label="Avanço"),
                                    "alvo": st.column_config.NumberColumn(label="Alvo"),
                                    "departamento": None, "objetivo": None, "kr": None
                                }
                                
                                unique_key = f"edit_{hash(depto + obj + kr)}"
                                df_edit = st.data_editor(
                                    df_kr, 
                                    column_config=col_cfg, 
                                    use_container_width=True, 
                                    num_rows="dynamic",
                                    key=unique_key
                                )

                                if not df_edit.equals(df_kr):
                                    df_edit['progresso_pct'] = df_edit.apply(calcular_progresso, axis=1)
                                    df_edit['departamento'] = depto
                                    df_edit['objetivo'] = obj
                                    df_edit['kr'] = kr
                                    
                                    idxs = df_kr.index
                                    st.session_state['df_master'] = st.session_state['df_master'].drop(idxs)
                                    st.session_state['df_master'] = pd.concat([st.session_state['df_master'], df_edit], ignore_index=True)
                                    
                                    salvar_dados_sql(st.session_state['df_master'])
                                    st.rerun()

                        st.markdown("")
                        with st.popover("➕ Adicionar Novo KR"):
                            nk = st.text_input("Nome do KR", key=f"nk_{obj}")
                            if st.button("Criar KR", key=f"bk_{obj}"):
                                if nk:
                                    dummy = {
                                        'departamento': depto, 'objetivo': obj, 'kr': nk,
                                        'status': 'Não Iniciado', 'avanco': 0.0, 'alvo': 1.0, 'progresso_pct': 0.0,
                                        'prazo': pd.to_datetime(date.today()), 'tarefa': 'Nova Tarefa', 'responsavel': ''
                                    }
                                    df_novo = pd.concat([st.session_state['df_master'], pd.DataFrame([dummy])], ignore_index=True)
                                    st.session_state['df_master'] = df_novo
                                    salvar_dados_sql(df_novo)
                                    st.rerun()
    
    st.markdown("---")
    with st.expander("📂 Central de Exportação"):
        st.dataframe(st.session_state['df_master'], use_container_width=True)
        st.download_button(
            "📥 Baixar Excel Completo",
            converter_para_excel(st.session_state['df_master']),
            "okrs_imobanco.xlsx"
        )
