from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
import gspread
import os

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

CREDENTIALS = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
sheet_id = os.getenv("GOOGLE_SHEET_ID")

if not CREDENTIALS:
    raise Exception("Variável de ambiente 'GOOGLE_SHEETS_CREDENTIALS' não encontrada!")

if not os.path.isfile(CREDENTIALS):
    raise FileNotFoundError(f"Arquivo de credenciais não encontrado: {CREDENTIALS}")

creds = Credentials.from_service_account_file(CREDENTIALS, scopes=SCOPES)
gc = gspread.authorize(creds)

spreadsheet = gc.open_by_key(sheet_id)

print(spreadsheet.worksheets())

worksheet = spreadsheet.sheet1  # ou spreadsheet.worksheet('Página1')
data = worksheet.get_all_values()  # método do Worksheet, não do Spreadsheet

for row in data:
    print(row)