import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import date

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gestão de OKR", layout="wide", page_icon="🎯")

# --- 2. CSS CUSTOMIZADO (UI/UX PREMIUM) ---
# Aplicação de design minimalista, clean, white mode corporativo premium.
# Fonte: Helvetica Now (Fallback: Inter, SF Pro, Helvetica, Arial)
# Paleta de destaque (moderada): #7371ff (principal), #1e1e1e (texto)

custom_css = """
<style>
/* 1. Global & Font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background-color: #FFFFFF; /* Fundo branco absoluto */
    color: #1e1e1e; /* Grafite sofisticado */
    font-family: "Inter", "SF Pro", "Helvetica Neue", Helvetica, Arial, sans-serif;
}

/* 2. Sidebar */
[data-testid="stSidebar"] {
    background-color: #FFFFFF; /* Sidebar branca sofisticada */
    border-right: 1px solid #f0f0f0; /* Linha sutil */
    box-shadow: 2px 0 5px rgba(0, 0, 0, 0.05); /* Sombra leve */
}
[data-testid="stSidebar"] .stButton > button {
    border-radius: 8px;
    border: 1px solid #f0f0f0;
    background-color: #f8f8f8;
    color: #1e1e1e;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #e8e8e8;
    border-color: #e8e8e8;
}

/* 3. Containers/Cards (st.container, st.expander) */
.stContainer, [data-testid="stExpander"] {
    border-radius: 12px; /* Borda 12px+ */
    border: 1px solid #f0f0f0;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); /* Sombra leve */
    padding: 1rem;
    margin-bottom: 15px;
}

/* 4. Inputs (text_input, selectbox, date_input) */
.stTextInput > div > div > input,
.stSelectbox > div > div > button,
.stDateInput > div > div > input {
    border-radius: 8px;
    border: 1px solid #e0e0e0; /* Bordas suaves */
    padding: 10px 15px;
    color: #1e1e1e;
}
.stTextInput > div > div > input:focus,
.stSelectbox > div > div > button:focus,
.stDateInput > div > div > input:focus {
    border-color: #7371ff; /* Foco elegante */
    box-shadow: 0 0 0 2px rgba(115, 113, 255, 0.2);
}

/* 5. Botões Minimalistas */
.stButton > button {
    border-radius: 8px;
    border: 1px solid #7371ff;
    background-color: #7371ff;
    color: white;
    font-weight: 500;
    padding: 10px 20px;
    transition: all 0.2s ease-in-out;
}
.stButton > button:hover {
    background-color: #5a58e0;
    border-color: #5a58e0;
    color: white;
}
/* Botão de exclusão (lixeira) */
[data-testid^="stButton"] button[title="Excluir este Objetivo"] {
    background-color: #f8f8f8;
    border-color: #f0f0f0;
    color: #1e1e1e;
}
[data-testid^="stButton"] button[title="Excluir este Objetivo"]:hover {
    background-color: #ff43c0; /* Cor de destaque para ação perigosa */
    border-color: #ff43c0;
    color: white;
}

/* 6. Tabs Modernas */
[data-testid="stTabs"] button {
    border-radius: 8px 8px 0 0;
    border: none;
    background-color: #f8f8f8;
    color: #1e1e1e;
    font-weight: 500;
    padding: 10px 20px;
    margin-right: 5px;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    background-color: #FFFFFF;
    border-bottom: 3px solid #7371ff; /* Linha de destaque */
    color: #7371ff;
    font-weight: 600;
}

/* 7. Progress Bar (Elegante) */
.stProgress > div > div > div > div {
    background-color: #e0e0e0; /* Fundo cinza suave */
    border-radius: 4px;
}
.stProgress > div > div > div > div > div {
    background-color: #7371ff; /* Cor de destaque principal */
    border-radius: 4px;
}

/* 8. Data Editor (Tabelas) */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    border: 1px solid #f0f0f0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
}

/* 9. Títulos e Hierarquia Visual */
h1 { color: #1e1e1e; font-weight: 700; border-bottom: 1px solid #f0f0f0; padding-bottom: 10px; }
h2 { color: #1e1e1e; font-weight: 600; }
h3 { color: #1e1e1e; font-weight: 500; border-left: 4px solid #7371ff; padding-left: 10px; margin-top: 20px; }
h4 { color: #1e1e1e; font-weight: 400; }

/* Hierarquia de Expander (Objetivo) */
[data-testid="stExpander"] > div:first-child {
    background-color: #f8f8f8; /* Fundo leve para o cabeçalho do Objetivo */
    border-radius: 12px;
    padding: 15px;
    font-weight: 600;
    color: #1e1e1e;
    border: none;
}
[data-testid="stExpander"] > div:first-child:hover {
    background-color: #f0f0f0;
}

/* Container KR (Card) */
.stContainer:has(h4) {
    background-color: #FFFFFF;
    border: 1px solid #e0eeef;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
}

/* Ajuste para o texto do progresso no KR */
.stProgress + div > div > p {
    font-weight: 600;
    color: #1e1e1e;
}

</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- 3. ARQUIVOS E CONSTANTES ---
DATA_FILE = 'okr_base_dados.csv'
DEPT_FILE = 'config_departamentos.csv'
OPCOES_STATUS = ["Não Iniciado", "Em Andamento", "Pausado", "Concluído"]

# --- 4. FUNÇÕES DE DADOS ---

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

# --- 5. INICIALIZAÇÃO DA MEMÓRIA ---
if 'df_master' not in st.session_state:
    st.session_state['df_master'] = carregar_dados_seguro()

if 'password_correct' not in st.session_state:
    st.session_state['password_correct'] = False

# --- 6. TELA DE LOGIN ---
def check_password():
    if st.session_state["password_correct"]: return True
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("Login")
        st.markdown("---") # Separador visual
        senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Digite a senha...")
        if st.button("Entrar", use_container_width=True):
            if senha == "admin123":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    return False

# --- 7. APLICAÇÃO PRINCIPAL ---
if check_password():
    st.title("Painel de OKRs")

    df = st.session_state['df_master']
    lista_deptos = carregar_departamentos()

    # --- MENU LATERAL ---
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        with st.expander("Departamentos"):
            with st.form("add_dept"):
                novo = st.text_input("Novo:", label_visibility="collapsed", placeholder="Nome do novo departamento")
                if st.form_submit_button("Adicionar", use_container_width=True):
                    if novo and novo not in lista_deptos:
                        lista_deptos.append(novo)
                        salvar_departamentos(lista_deptos)
                        st.rerun()
            rm_dept = st.selectbox("Remover:", ["..."] + lista_deptos, label_visibility="collapsed")
            if st.button("Remover", use_container_width=True):
                if rm_dept != "...":
                    lista_deptos.remove(rm_dept)
                    salvar_departamentos(lista_deptos)
                    st.rerun()

        st.divider()
        
        st.subheader("Novo Objetivo")
        with st.form("quick_add"):
            d = st.selectbox("Departamento", lista_deptos)
            o = st.text_input("Objetivo Macro", placeholder="Ex: Aumentar a satisfação do cliente")
            if st.form_submit_button("Criar Objetivo", use_container_width=True):
                if o:
                    # AJUSTE: Cria o Objetivo com KR vazio e Tarefa vazia
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
                
                # --- HIERARQUIA 1: OBJETIVOS ---
                objs = [x for x in df_d['Objetivo'].unique() if x]
                for obj in objs:
                    mask_obj = (df['Departamento'] == depto) & (df['Objetivo'] == obj)
                    
                    # AJUSTE: Calcula média ignorando linhas onde KR está vazio (placeholders)
                    mask_validos = mask_obj & (df['Resultado Chave (KR)'] != '')
                    if not df[mask_validos].empty:
                        prog_obj = df[mask_validos]['Progresso (%)'].mean()
                    else:
                        prog_obj = 0.0

                    if pd.isna(prog_obj): prog_obj = 0.0
                    prog_obj = max(0.0, min(1.0, float(prog_obj)))
                    
                    label_obj = f"🎯 {obj} | {int(prog_obj*100)}%"
                    
                    with st.expander(label_obj, expanded=True):
                        
                        c_edit_obj, c_del_obj = st.columns([5, 1])
                        with c_edit_obj:
                            new_name = st.text_input("Nome do Objetivo", value=obj, key=f"n_o_{depto}_{obj}", label_visibility="collapsed")
                            if new_name != obj:
                                st.session_state['df_master'].loc[mask_obj, 'Objetivo'] = new_name
                                st.rerun()
                        with c_del_obj:
                            if st.button("🗑️", key=f"del_{depto}_{obj}", help="Excluir este Objetivo", use_container_width=True):
                                st.session_state['df_master'] = st.session_state['df_master'][~mask_obj]
                                st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                                st.rerun()

                        st.markdown("### Resultados Chave (KRs)")
                        
                        # --- HIERARQUIA 2: KRs ---
                        # O filtro 'if x' já garante que o KR vazio criado automaticamente não apareça aqui
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
                                    "Avanço": st.column_config.NumberColumn(format="%.2f"),
                                    "Alvo": st.column_config.NumberColumn(format="%.2f"),
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
                            nk = st.text_input("Nome do KR", key=f"nk_{obj}", placeholder="Ex: Atingir 95% de NPS")
                            if st.button("Criar KR", key=f"bk_{obj}", use_container_width=True):
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
