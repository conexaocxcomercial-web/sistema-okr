import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import io

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="Sistema OKR - CX Data", layout="wide")

# --- CONEXÃO COM O GOOGLE SHEETS ---
def conectar_google_sheets():
    # Define o escopo de permissões
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Carrega as credenciais do arquivo JSON
    # Certifique-se de que o arquivo 'service_account.json' está na mesma pasta que este script
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    
    # Abre a planilha pelo ID
    sheet_id = "1EDaY5PdzTzLqCOS2w9iNNpIshmK5vRtUr8sXhLgwQc0"
    spreadsheet = client.open_by_key(sheet_id)
    return spreadsheet

# Função para carregar dados
def carregar_dados():
    sh = conectar_google_sheets()
    
    # Carrega aba de Dados
    try:
        worksheet_dados = sh.worksheet("Dados")
        data_dados = worksheet_dados.get_all_records()
        df_dados = pd.DataFrame(data_dados)
    except Exception:
        # Cria dataframe vazio se a aba estiver vazia ou não existir
        df_dados = pd.DataFrame()
        worksheet_dados = sh.worksheet("Dados")
    
    return df_dados, worksheet_dados

# --- INTERFACE E LÓGICA ---
def main():
    st.title("📊 Sistema de Gestão de OKRs")
    st.caption("Conectado a: OKR_System_DB")

    # Tentativa de conexão
    try:
        df_dados, worksheet_dados = carregar_dados()
        st.success("Conexão com banco de dados estabelecida com sucesso!")
    except Exception as e:
        st.error(f"Erro ao conectar na planilha: {e}")
        st.info("Verifique se o arquivo 'service_account.json' está na pasta e se o e-mail do bot tem permissão de editor na planilha.")
        return

    # --- MENU LATERAL ---
    menu = st.sidebar.selectbox("Navegação", ["Dashboard", "Registrar OKR", "Exportar Dados"])

    # --- 1. DASHBOARD ---
    if menu == "Dashboard":
        st.header("Visão Geral dos OKRs")
        
        if not df_dados.empty:
            st.dataframe(df_dados, use_container_width=True)
            
            # Exemplo de métrica simples: Contagem de status
            if "Status" in df_dados.columns:
                st.subheader("Distribuição de Status")
                st.bar_chart(df_dados["Status"].value_counts())
        else:
            st.warning("A aba 'Dados' está vazia ou não foi possível ler os registros.")

    # --- 2. REGISTRAR OKR ---
    elif menu == "Registrar OKR":
        st.header("Novo Registro")
        
        with st.form("form_okr"):
            col1, col2 = st.columns(2)
            objetivo = col1.text_input("Objetivo")
            key_result = col2.text_input("Key Result (KR)")
            
            responsavel = st.selectbox("Responsável", ["Jhonattan", "Colaborador 1", "Colaborador 2"])
            status = st.selectbox("Status", ["Não Iniciado", "Em Andamento", "Concluído"])
            progresso = st.slider("Progresso (%)", 0, 100, 0)
            
            submitted = st.form_submit_button("Salvar OKR")
            
            if submitted:
                if not objetivo or not key_result:
                    st.warning("Por favor, preencha o Objetivo e o KR.")
                else:
                    # Prepara a nova linha
                    nova_linha = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Data Registro
                        objetivo,
                        key_result,
                        responsavel,
                        status,
                        progresso
                    ]
                    
                    # Adiciona na planilha Google
                    try:
                        worksheet_dados.append_row(nova_linha)
                        st.success("OKR registrado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar no Google Sheets: {e}")

    # --- 3. EXPORTAR DADOS ---
    elif menu == "Exportar Dados":
        st.header("Exportação")
        st.write("Baixe os dados atuais da aba 'Dados' em formato Excel.")
        
        if not df_dados.empty:
            # Converte DataFrame para Excel em memória
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_dados.to_excel(writer, index=False, sheet_name='Dados')
                
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 Baixar Planilha (.xlsx)",
                data=excel_data,
                file_name="relatorio_okr_cxdata.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Não há dados para exportar.")

if __name__ == "__main__":
    main()
