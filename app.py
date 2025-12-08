import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
import time

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gestão de OKR", layout="wide", page_icon="🎯")

# --- 2. CONEXÃO COM GOOGLE SHEETS ---

# Atualizado com o nome da sua planilha
NOME_PLANILHA_GOOGLE = "OKR_System_DB" 
ABA_DADOS = "Dados"   # Onde ficam os OKRs
ABA_CONFIG = "Config" # Onde ficam os Departamentos

def conectar_gsheets():
    """Conecta ao Google Sheets usando st.secrets"""
    try:
        # Define o escopo
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Pega as credenciais dos segredos do Streamlit
        # Certifique-se de ter colado o TOML corretamente nos Secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        # Autoriza e abre a planilha
        client = gspread.authorize(creds)
        sheet = client.open(NOME_PLANILHA_GOOGLE)
        return sheet
    except Exception as e:
        st.error(f"❌ Erro ao conectar no Google Sheets: {e}")
        st.info("Verifique se o nome da planilha está 'OKR_System_DB' e se o bot (client_email) foi adicionado como Editor.")
        return None

# --- 3. FUNÇÕES DE DADOS (LEITURA/ESCRITA NA NUVEM) ---

def carregar_dados_sheets(sheet):
    try:
        worksheet = sheet.worksheet(ABA_DADOS)
        dados = worksheet.get_all_records()
        df = pd.DataFrame(dados)
        
        # Se estiver vazio, retorna estrutura padrão
        if df.empty:
            return pd.DataFrame(columns=[
                'Departamento', 'Objetivo', 'Resultado Chave (KR)', 
                'Status', 'Prazo', 'Avanço', 'Alvo', 'Progresso (%)'
            ])
            
        # Tratamento de tipos
        if 'Prazo' in df.columns:
            df['Prazo'] = pd.to_datetime(df['Prazo'], errors='coerce')
            
        num_cols = ['Avanço', 'Alvo', 'Progresso (%)']
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                
        # Garante colunas de texto
        text_cols = ['Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Status']
        for col in text_cols:
            if col not in df.columns: df[col] = ""
            df[col] = df[col].astype(str)
            
        return df
    except gspread.exceptions.WorksheetNotFound:
        # Se a aba "Dados" não existe, cria ela
        sheet.add_worksheet(title=ABA_DADOS, rows=100, cols=10)
        return pd.DataFrame(columns=['Departamento', 'Objetivo', 'Resultado Chave (KR)', 'Status', 'Prazo', 'Avanço', 'Alvo', 'Progresso (%)'])

def carregar_departamentos_sheets(sheet):
    try:
        worksheet = sheet.worksheet(ABA_CONFIG)
        valores = worksheet.col_values(1) # Pega primeira coluna
        if len(valores) > 1:
            return valores[1:] # Ignora o cabeçalho
        return []
    except gspread.exceptions.WorksheetNotFound:
        # Se a aba "Config" não existe, cria ela
        sheet.add_worksheet(title=ABA_CONFIG, rows=100, cols=2)
        return []

def salvar_dados_sheets(sheet, df):
    try:
        worksheet = sheet.worksheet(ABA_DADOS)
        # Prepara dados para salvar (converte datas para string para o Excel ler bem)
        df_save = df.copy()
        if 'Prazo' in df_save.columns:
            df_save['Prazo'] = df_save['Prazo'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else '')
            
        worksheet.clear() # Limpa tudo
        # Escreve cabeçalho + dados
        worksheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        return True
    except Exception as e:
        st.error(f"Erro ao salvar OKRs: {e}")
        return False

def salvar_departamentos_sheets(sheet, lista_depts):
    try:
        worksheet = sheet.worksheet(ABA_CONFIG)
        worksheet.clear()
        worksheet.update([["Departamento"]] + [[x] for x in lista_depts])
        return True
    except Exception as e:
        st.error(f"Erro ao salvar Departamentos: {e}")
        return False

def calcular_progresso(row):
    try:
        av = float(row['Avanço'])
        al = float(row['Alvo'])
        if al > 0:
            return min(av / al, 1.0)
        return 0.0
    except:
        return 0.0

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

# --- 4. LOGIN E ESTADO ---
if 'password_correct' not in st.session_state:
    st.session_state['password_correct'] = False

def check_password():
    if st.session_state["password_correct"]: return True
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("🔒 Login")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if senha == "admin123":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    return False

# --- 5. APLICAÇÃO PRINCIPAL ---
if check_password():
    st.title("Painel de OKRs (Conectado ao Google Sheets)")
    
    # Mensagem de status discreta
    with st.empty():
        st.caption("Conectando ao banco de dados...")
        sheet = conectar_gsheets()
        if sheet:
            st.caption(f"✅ Conectado a: {NOME_PLANILHA_GOOGLE}")
        else:
            st.stop() # Para se não conectar

    if sheet:
        # Carrega dados da nuvem na primeira execução
        if 'df_master' not in st.session_state:
            st.session_state['df_master'] = carregar_dados_sheets(sheet)
        
        # Carrega departamentos sempre fresco
        lista_deptos = carregar_departamentos_sheets(sheet)
        
        df = st.session_state['df_master']

        # === MENU LATERAL ===
        with st.sidebar:
            st.header("Menu de Gestão")

            # A. Departamentos
            with st.expander("🏢 Departamentos", expanded=False):
                novo_dept = st.text_input("Novo Departamento:")
                if st.button("➕ Criar"):
                    if novo_dept and novo_dept not in lista_deptos:
                        lista_deptos.append(novo_dept)
                        salvar_departamentos_sheets(sheet, lista_deptos)
                        st.success("Salvo na nuvem!")
                        time.sleep(1)
                        st.rerun()
                
                if lista_deptos:
                    st.markdown("---")
                    dept_del = st.selectbox("Excluir:", ["Selecionar..."] + lista_deptos)
                    if st.button("🗑️ Excluir"):
                        if dept_del != "Selecionar...":
                            lista_deptos.remove(dept_del)
                            salvar_departamentos_sheets(sheet, lista_deptos)
                            st.success("Removido da nuvem!")
                            time.sleep(1)
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
                                'Prazo': pd.to_datetime(date.today())
                            }
                            # Atualiza sessão
                            st.session_state['df_master'] = pd.concat([df, pd.DataFrame([novo_dado])], ignore_index=True)
                            # Salva na nuvem
                            salvar_dados_sheets(sheet, st.session_state['df_master'])
                            st.success("Salvo no Google Sheets!")
                            st.rerun()
                        else:
                            st.warning("Preencha todos os campos.")
            else:
                st.info("Crie um departamento primeiro.")
                
            st.markdown("---")
            if st.button("Sair"):
                st.session_state["password_correct"] = False
                st.rerun()

        # === VISUAL PRINCIPAL ===
        if not lista_deptos:
            st.warning("Nenhum departamento cadastrado.")
        else:
            abas = st.tabs(lista_deptos)
            
            salvar_necessario = False

            for
