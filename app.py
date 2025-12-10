import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import date

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gestão de OKR", layout="wide", page_icon="🎯")

# --- ESTILOS CSS CUSTOMIZADOS ---
st.markdown("""
<style>
    @import url('https://fonts.cdnfonts.com/css/helvetica-neue-9');
    
    /* Fonte global */
    * {
        font-family: 'Helvetica Now', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    
    /* Background principal */
    .stApp {
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e1e1e 0%, #252525 100%);
        border-right: 1px solid #7371ff33;
    }
    
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #dbbfff;
        font-weight: 300;
        letter-spacing: 0.5px;
    }
    
    /* Títulos principais */
    h1 {
        color: #dbbfff;
        font-weight: 200;
        font-size: 2.8rem;
        letter-spacing: 1px;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #dbbfff 0%, #7371ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    h2, h3 {
        color: #dbbfff;
        font-weight: 300;
        letter-spacing: 0.5px;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
        padding: 0.5rem 0;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: linear-gradient(135deg, #2a2a2a 0%, #1e1e1e 100%);
        border: 1px solid #7371ff33;
        border-radius: 8px;
        color: #dbbfff;
        font-weight: 300;
        padding: 0.75rem 1.5rem;
        transition: all 0.3s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: linear-gradient(135deg, #7371ff22 0%, #dbbfff11 100%);
        border-color: #7371ff;
        transform: translateY(-2px);
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #7371ff 0%, #dbbfff 100%);
        border-color: #7371ff;
        color: #1e1e1e;
        font-weight: 400;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background: linear-gradient(135deg, #2a2a2a 0%, #1e1e1e 100%);
        border: 1px solid #7371ff33;
        border-radius: 12px;
        color: #dbbfff;
        font-weight: 300;
        font-size: 1.1rem;
        padding: 1rem 1.5rem;
        transition: all 0.3s ease;
    }
    
    .streamlit-expanderHeader:hover {
        border-color: #7371ff;
        background: linear-gradient(135deg, #7371ff11 0%, #dbbfff11 100%);
    }
    
    [data-testid="stExpander"] {
        background: transparent;
        border: none;
        margin-bottom: 1rem;
    }
    
    /* Containers */
    [data-testid="stVerticalBlock"] > div:has(> div.element-container) {
        background: linear-gradient(135deg, #2a2a2a99 0%, #1e1e1e99 100%);
        border: 1px solid #7371ff33;
        border-radius: 12px;
        padding: 1.5rem;
        backdrop-filter: blur(10px);
    }
    
    /* Botões */
    .stButton > button {
        background: linear-gradient(135deg, #7371ff 0%, #ff43c0 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        font-weight: 300;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(115, 113, 255, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(115, 113, 255, 0.5);
    }
    
    /* Inputs */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div,
    .stDateInput > div > div > input {
        background-color: #2a2a2a;
        border: 1px solid #7371ff33;
        border-radius: 8px;
        color: #dbbfff;
        font-weight: 300;
    }
    
    .stTextInput > div > div > input:focus,
    .stSelectbox > div > div > div:focus,
    .stDateInput > div > div > input:focus {
        border-color: #7371ff;
        box-shadow: 0 0 0 1px #7371ff33;
    }
    
    /* Progress bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #bef533 0%, #7371ff 50%, #ff43c0 100%);
    }
    
    /* Data editor */
    [data-testid="stDataFrame"] {
        background: linear-gradient(135deg, #2a2a2a 0%, #1e1e1e 100%);
        border: 1px solid #7371ff33;
        border-radius: 12px;
        overflow: hidden;
    }
    
    [data-testid="stDataFrame"] th {
        background: linear-gradient(135deg, #7371ff 0%, #dbbfff 100%);
        color: #1e1e1e;
        font-weight: 400;
        letter-spacing: 0.5px;
        border: none;
    }
    
    [data-testid="stDataFrame"] td {
        background-color: #2a2a2a;
        color: #dbbfff;
        border-color: #7371ff22;
    }
    
    /* Forms */
    [data-testid="stForm"] {
        background: linear-gradient(135deg, #2a2a2a 0%, #1e1e1e 100%);
        border: 1px solid #7371ff33;
        border-radius: 12px;
        padding: 1.5rem;
    }
    
    /* Popovers */
    [data-testid="stPopover"] {
        background: #1e1e1e;
        border: 1px solid #7371ff;
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(115, 113, 255, 0.3);
    }
    
    /* Dividers */
    hr {
        border-color: #7371ff33;
        margin: 2rem 0;
    }
    
    /* Badges de status */
    .stMarkdown p {
        color: #dbbfff;
        font-weight: 300;
    }
    
    .stMarkdown strong {
        color: #bef533;
        font-weight: 400;
    }
    
    /* Captions */
    .stCaption {
        color: #7371ff;
        font-weight: 300;
        font-style: italic;
    }
    
    /* Login screen */
    [data-testid="stVerticalBlock"]:has(> div > div > h1:contains("Login")) {
        background: linear-gradient(135deg, #1e1e1e 0%, #2a2a2a 100%);
        border: 1px solid #7371ff;
        border-radius: 20px;
        padding: 3rem;
        box-shadow: 0 8px 32px rgba(115, 113, 255, 0.3);
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #1e1e1e;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #7371ff 0%, #ff43c0 100%);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, #ff43c0 0%, #7371ff 100%);
    }
    
    /* Alertas */
    .stAlert {
        background: linear-gradient(135deg, #2a2a2a 0%, #1e1e1e 100%);
        border-left: 4px solid #7371ff;
        color: #dbbfff;
        border-radius: 8px;
    }
    
    /* Download button */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #bef533 0%, #7371ff 100%);
        color: #1e1e1e;
        font-weight: 400;
    }
    
    /* Emoji no botão de delete */
    button[kind="secondary"] {
        background: linear-gradient(135deg, #ff43c0 0%, #7371ff 100%);
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. ARQUIVOS E CONSTANTES ---
DATA_FILE = 'okr_base_dados.csv'
DEPT_FILE = 'config_departamentos.csv'
OPCOES_STATUS = ["Não Iniciado", "Em Andamento", "Pausado", "Concluído"]

# --- 3. FUNÇÕES DE DADOS ---

def carregar_dados_seguro():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=[
            'Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Tarefa', 
            'Status', 'Responsável', 'Prazo', 'Avanço', 'Alvo', 'Progresso (%)'
        ])
    try:
        df = pd.read_csv(DATA_FILE)
        text_cols = ['Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Tarefa', 'Status', 'Responsável']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', '').fillna('')
        
        if 'Prazo' in df.columns:
            df['Prazo'] = pd.to_datetime(df['Prazo'], errors='coerce')
        
        num_cols = ['Avanço', 'Alvo', 'Progresso (%)']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                
        return df
    except Exception as e:
        st.error(f"Erro ao ler banco de dados: {e}")
        return pd.DataFrame()

def carregar_departamentos():
    if os.path.exists(DEPT_FILE):
        try:
            return pd.read_csv(DEPT_FILE)['Departamento'].tolist()
        except:
            pass 
    padrao = ["Comercial", "Financeiro", "Operacional", "RH", "Tecnologia", "Marketing"]
    pd.DataFrame(padrao, columns=['Departamento']).to_csv(DEPT_FILE, index=False)
    return padrao

def salvar_departamentos(lista_deptos):
    pd.DataFrame(lista_deptos, columns=['Departamento']).to_csv(DEPT_FILE, index=False)

def calcular_progresso(row):
    try:
        av = float(row['Avanço'])
        al = float(row['Alvo'])
        if al > 0:
            return min(max(av / al, 0.0), 1.0)
        return 0.0
    except:
        return 0.0

def converter_para_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_exp = df.copy()
        df_exp['Prazo'] = df_exp['Prazo'].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else '')
        df_exp.to_excel(writer, index=False, sheet_name='OKRs')
    return output.getvalue()

# --- 4. INICIALIZAÇÃO DA MEMÓRIA ---
if 'df_master' not in st.session_state:
    st.session_state['df_master'] = carregar_dados_seguro()

if 'password_correct' not in st.session_state:
    st.session_state['password_correct'] = False

# --- 5. TELA DE LOGIN ---
def check_password():
    if st.session_state["password_correct"]: return True
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("Login")
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
    st.title("Painel de OKRs")

    df = st.session_state['df_master']
    lista_deptos = carregar_departamentos()

    # --- MENU LATERAL ---
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        with st.expander("Departamentos"):
            with st.form("add_dept"):
                novo = st.text_input("Novo:")
                if st.form_submit_button("Adicionar"):
                    if novo and novo not in lista_deptos:
                        lista_deptos.append(novo)
                        salvar_departamentos(lista_deptos)
                        st.rerun()
            rm_dept = st.selectbox("Remover:", ["..."] + lista_deptos)
            if st.button("Remover"):
                if rm_dept != "...":
                    lista_deptos.remove(rm_dept)
                    salvar_departamentos(lista_deptos)
                    st.rerun()

        st.divider()
        
        st.subheader("Novo Objetivo")
        with st.form("quick_add"):
            d = st.selectbox("Departamento", lista_deptos)
            o = st.text_input("Objetivo Macro")
            if st.form_submit_button("Criar Objetivo"):
                if o:
                    novo_okr = {
                        'Departamento': d, 'Objetivo': o, 'Resultado Chave (KR)': '',
                        'Status': 'Não Iniciado', 'Avanço': 0.0, 'Alvo': 1.0, 'Progresso (%)': 0.0,
                        'Prazo': pd.to_datetime(date.today()), 'Tarefa': '', 'Responsável': ''
                    }
                    st.session_state['df_master'] = pd.concat([df, pd.DataFrame([novo_okr])], ignore_index=True)
                    st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                    st.rerun()
                else:
                    st.warning("Digite um nome para o objetivo.")

    # --- ÁREA PRINCIPAL ---
    if df.empty:
        st.info("Comece criando um Objetivo no menu lateral.")
    else:
        depts = sorted(list(set(df['Departamento'].unique()) | set(lista_deptos)))
        abas = st.tabs(depts)
        
        for i, depto in enumerate(depts):
            with abas[i]:
                df_d = df[df['Departamento'] == depto]
                if df_d.empty:
                    st.caption("Sem dados.")
                    continue
                
                objs = [x for x in df_d['Objetivo'].unique() if x]
                for obj in objs:
                    mask_obj = (df['Departamento'] == depto) & (df['Objetivo'] == obj)
                    
                    mask_validos = mask_obj & (df['Resultado Chave (KR)'] != '')
                    if not df[mask_validos].empty:
                        prog_obj = df[mask_validos]['Progresso (%)'].mean()
                    else:
                        prog_obj = 0.0

                    if pd.isna(prog_obj): prog_obj = 0.0
                    prog_obj = max(0.0, min(1.0, float(prog_obj)))
                    
                    label_obj = f"{obj}  | {int(prog_obj*100)}%"
                    
                    with st.expander(label_obj, expanded=True):
                        
                        c_edit_obj, c_del_obj = st.columns([5, 1])
                        with c_edit_obj:
                            new_name = st.text_input("Nome do Objetivo", value=obj, key=f"n_o_{depto}_{obj}", label_visibility="collapsed")
                            if new_name != obj:
                                st.session_state['df_master'].loc[mask_obj, 'Objetivo'] = new_name
                                st.rerun()
                        with c_del_obj:
                            if st.button("🗑️", key=f"del_{depto}_{obj}", help="Excluir este Objetivo"):
                                st.session_state['df_master'] = st.session_state['df_master'][~mask_obj]
                                st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                                st.rerun()

                        st.markdown("### Resultados Chave (KRs)")
                        
                        krs = [x for x in df[mask_obj]['Resultado Chave (KR)'].unique() if x]
                        
                        if not krs:
                            st.caption("Nenhum KR criado ainda. Adicione o primeiro abaixo.")

                        for kr in krs:
                            mask_kr = mask_obj & (df['Resultado Chave (KR)'] == kr)
                            df_kr = df[mask_kr] 
                            
                            prog_kr = df_kr['Progresso (%)'].mean()
                            if pd.isna(prog_kr): prog_kr = 0.0
                            prog_kr = max(0.0, min(1.0, float(prog_kr)))

                            with st.container(border=True):
                                c_title, c_bar = st.columns([3, 1])
                                
                                with c_title:
                                    st.markdown(f"**KR:** {kr}")
                                    new_kr = st.text_input("Editar nome do KR", value=kr, key=f"r_k_{depto}_{obj}_{kr}", label_visibility="collapsed")
                                    if new_kr != kr:
                                        st.session_state['df_master'].loc[mask_kr, 'Resultado Chave (KR)'] = new_kr
                                        st.rerun()
                                
                                with c_bar:
                                    st.progress(prog_kr, text=f"**{int(prog_kr*100)}%**")
                                
                                st.markdown("**Tarefas & Ações**")
                                
                                col_cfg = {
                                    "Progresso (%)": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
                                    "Status": st.column_config.SelectboxColumn(options=OPCOES_STATUS, required=True),
                                    "Prazo": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                    "Departamento": None, "Objetivo": None, "Resultado Chave (KR)": None
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
                                    df_edit['Progresso (%)'] = df_edit.apply(calcular_progresso, axis=1)
                                    df_edit['Departamento'] = depto
                                    df_edit['Objetivo'] = obj
                                    df_edit['Resultado Chave (KR)'] = kr
                                    
                                    idxs = df_kr.index
                                    st.session_state['df_master'] = st.session_state['df_master'].drop(idxs)
                                    st.session_state['df_master'] = pd.concat([st.session_state['df_master'], df_edit], ignore_index=True)
                                    
                                    st.session_state['df_master'] = st.session_state['df_master'].sort_values(
                                        by=['Departamento', 'Objetivo', 'Resultado Chave (KR)']
                                    ).reset_index(drop=True)
                                    
                                    st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                                    st.rerun()

                        st.markdown("")
                        with st.popover("Novo KR"):
                            nk = st.text_input("Nome do KR", key=f"nk_{obj}")
                            if st.button("Criar", key=f"bk_{obj}"):
                                if nk:
                                    dummy = {
                                        'Departamento': depto, 'Objetivo': obj, 'Resultado Chave (KR)': nk,
                                        'Status': 'Não Iniciado', 'Avanço': 0.0, 'Alvo': 1.0, 'Progresso (%)': 0.0,
                                        'Prazo': pd.to_datetime(date.today()), 'Tarefa': 'Nova Tarefa', 'Responsável': ''
                                    }
                                    st.session_state['df_master'] = pd.concat([st.session_state['df_master'], pd.DataFrame([dummy])], ignore_index=True)
                                    
                                    st.session_state['df_master'] = st.session_state['df_master'].sort_values(
                                        by=['Departamento', 'Objetivo', 'Resultado Chave (KR)']
                                    ).reset_index(drop=True)
                                    
                                    st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                                    st.rerun()
    
    # --- RODAPÉ COM EXPORTAÇÃO ---
    st.markdown("---")
    with st.expander("Exportar Dados"):
        st.dataframe(st.session_state['df_master'], use_container_width=True)
        st.download_button(
            "Baixar Excel Completo",
            converter_para_excel(st.session_state['df_master']),
            "okrs_imobanco.xlsx"
        )
