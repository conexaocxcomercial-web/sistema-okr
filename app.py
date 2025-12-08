import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import date

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gestão de OKR", layout="wide", page_icon="🎯")

# --- 2. ARQUIVOS E CONSTANTES ---
DATA_FILE = 'okr_base_dados.csv'
DEPT_FILE = 'config_departamentos.csv'
OPCOES_STATUS = ["Não Iniciado", "Em Andamento", "Pausado", "Concluído"]

# --- 3. FUNÇÕES DE DADOS ---

def carregar_dados_seguro():
    """Carrega dados, corrige datas e preenche buracos vazios."""
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=[
            'Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Tarefa', 
            'Status', 'Responsável', 'Prazo', 'Avanço', 'Alvo', 'Progresso (%)'
        ])
    
    try:
        df = pd.read_csv(DATA_FILE)
        
        # Limpeza e tipagem
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
    """Lê o arquivo de departamentos ou inicia vazio."""
    if os.path.exists(DEPT_FILE):
        try:
            return pd.read_csv(DEPT_FILE)['Departamento'].tolist()
        except:
            pass 
    
    # CORREÇÃO CRÍTICA: Inicia vazio para não criar departamentos fantasmas
    padrao = [] 
    pd.DataFrame(padrao, columns=['Departamento']).to_csv(DEPT_FILE, index=False)
    return padrao

def salvar_departamentos(lista_deptos):
    """Salva a lista atualizada no arquivo."""
    pd.DataFrame(lista_deptos, columns=['Departamento']).to_csv(DEPT_FILE, index=False)

def calcular_progresso(row):
    try:
        av = float(row['Avanço'])
        al = float(row['Alvo'])
        if al > 0:
            return min(av / al, 1.0)
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

def barra_progresso_html(valor):
    if pd.isna(valor): valor = 0.0
    pct = int(valor * 100)
    cor = "#ef4444" if pct < 30 else "#eab308" if pct < 70 else "#22c55e"
    return f"""
    <div style="width:100%; background-color:#e5e7eb; border-radius:4px; height:18px; display:flex; align-items:center;">
        <div style="background-color:{cor}; width:{pct}%; height:100%; border-radius:4px; transition:width 0.3s;"></div>
        <span style="margin-left:8px; font-size:12px; font-weight:bold; color:#333;">{pct}%</span>
    </div>
    """

# --- 4. LOGIN E SESSÃO ---
if 'df_master' not in st.session_state:
    st.session_state['df_master'] = carregar_dados_seguro()

if 'password_correct' not in st.session_state:
    st.session_state['password_correct'] = False

def check_password():
    if st.session_state["password_correct"]: return True
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🔒 Acesso Restrito")
        senha = st.text_input("Digite sua senha", type="password")
        if st.button("Entrar"):
            if senha == "admin123": # SUA SENHA AQUI
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    return False

# --- 5. APLICAÇÃO PRINCIPAL ---
if check_password():
    st.title("Painel de OKRs")

    # Variáveis
    df = st.session_state['df_master']
    lista_deptos = carregar_departamentos()

    # === MENU LATERAL (A estrutura que você gosta) ===
    with st.sidebar:
        st.header("Menu de Gestão")

        # A. Gerenciar Departamentos
        with st.expander("🏢 Departamentos", expanded=False):
            # Adicionar
            novo_dept = st.text_input("Novo Departamento:")
            if st.button("➕ Criar"):
                if novo_dept and novo_dept not in lista_deptos:
                    lista_deptos.append(novo_dept)
                    salvar_departamentos(lista_deptos)
                    st.success("Criado!")
                    st.rerun() # Atualiza na hora
            
            # Remover
            if lista_deptos:
                st.markdown("---")
                dept_del = st.selectbox("Excluir:", ["Selecionar..."] + lista_deptos)
                if st.button("🗑️ Excluir"):
                    if dept_del != "Selecionar...":
                        lista_deptos.remove(dept_del)
                        salvar_departamentos(lista_deptos)
                        st.success("Removido!")
                        st.rerun()

        # B. Novo OKR
        st.subheader("📝 Novo OKR")
        if lista_deptos:
            with st.form("form_okr", clear_on_submit=True):
                f_dept = st.selectbox("Departamento", lista_deptos)
                f_obj = st.text_input("Objetivo")
                f_kr = st.text_input("Key Result (KR)")
                
                if st.form_submit_button("Salvar OKR"):
                    if f_obj and f_kr:
                        novo_dado = {
                            'Departamento': f_dept, 'Objetivo': f_obj, 'Resultado Chave (KR)': f_kr,
                            'Status': 'Não Iniciado', 'Avanço': 0.0, 'Alvo': 1.0, 'Progresso (%)': 0.0,
                            'Prazo': pd.to_datetime(date.today()), 'Tarefa': '', 'Responsável': ''
                        }
                        st.session_state['df_master'] = pd.concat([df, pd.DataFrame([novo_dado])], ignore_index=True)
                        st.session_state['df_master'].to_csv(DATA_FILE, index=False)
                        st.rerun() # Atualiza na hora
                    else:
                        st.warning("Preencha todos os campos.")
        else:
            st.info("👆 Crie um departamento acima para começar.")
            
        st.markdown("---")
        if st.button("Sair (Logout)"):
            st.session_state["password_correct"] = False
            st.rerun()

    # === VISUAL PRINCIPAL (Abas e Tabelas) ===
    
    # Verifica se tem departamentos para mostrar as abas
    if not lista_deptos:
        st.warning("Nenhum departamento encontrado. Cadastre o primeiro no menu lateral.")
    
    else:
        # Cria as abas com base nos departamentos cadastrados
        abas = st.tabs(lista_deptos)
        
        salvar_auto = False

        for i, depto in enumerate(lista_deptos):
            with abas[i]:
                # Filtra dados do departamento da aba atual
                df_depto = df[df['Departamento'] == depto]
                
                if df_depto.empty:
                    st.info(f"Sem OKRs cadastrados para {depto}.")
                else:
                    # Agrupa por Objetivo (Visual de Expander)
                    objs_unicos = df_depto['Objetivo'].unique()
                    
                    for obj in objs_unicos:
                        # Dados apenas deste objetivo
                        df_obj = df_depto[df_depto['Objetivo'] == obj]
                        media_obj = df_obj['Progresso (%)'].mean()
                        
                        with st.expander(f"🎯 {obj}", expanded=True):
                            # Barra de progresso visual
                            st.markdown(barra_progresso_html(media_obj), unsafe_allow_html=True)
                            st.markdown("")

                            # Configuração da Tabela Editável
                            col_config = {
                                "Progresso (%)": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.0f%%"),
                                "Status": st.column_config.SelectboxColumn(options=OPCOES_STATUS, required=True),
                                "Prazo": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                "Departamento": None, # Esconde coluna
                                "Objetivo": None      # Esconde coluna
                            }
                            
                            # Tabela
                            df_editado = st.data_editor(
                                df_obj,
                                column_config=col_config,
                                use_container_width=True,
                                key=f"edit_{depto}_{obj}",
                                num_rows="dynamic"
                            )
                            
                            # Lógica de Salvamento ao editar tabela
                            if not df_editado.equals(df_obj):
                                # 1. Recalcula progresso
                                df_editado['Progresso (%)'] = df_editado.apply(calcular_progresso, axis=1)
                                # 2. Garante integridade (se o usuário tentar apagar dept/obj sem querer)
                                df_editado['Departamento'] = depto
                                df_editado['Objetivo'] = obj
                                
                                # 3. Atualiza o DataFrame Mestre
                                indices = df_obj.index
                                st.session_state['df_master'] = st.session_state['df_master'].drop(indices)
                                st.session_state['df_master'] = pd.concat([st.session_state['df_master'], df_editado], ignore_index=True)
                                
                                salvar_auto = True

        # Salva no disco se houve edição nas tabelas
        if salvar_auto:
            st.session_state['df_master'].to_csv(DATA_FILE, index=False)
            # Desta vez sem rerun, para não fechar o editor enquanto você digita

    # === RODAPÉ (Exportação) ===
    st.markdown("---")
    with st.expander("📥 Exportar Relatório"):
        st.download_button(
            "Baixar Excel (.xlsx)",
            converter_para_excel(st.session_state['df_master']),
            "okrs_completo.xlsx"
        )
