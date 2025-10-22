from dotenv import load_dotenv
import os

# Carrega variáveis do arquivo .env
load_dotenv()

# Pega os valores do ambiente
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")