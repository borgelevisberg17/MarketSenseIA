##############################################
#Projeto: MarketSense AI - Agente de Inteligência de Mercado
#Autor: Borge Levisberg
#Baseado na Aula 5 da Imersão IA Alura + Google gemini
#####################################№######№#
import os
import textwrap
from datetime import date
import warnings
import json
from google import genai
from google.genai import types
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import google_search
import PIL.Image
from PIL import Image
import io
from io import BytesIO
import base64
import google.genai as genai_img
import asyncio
from telegram.constants import ChatAction
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import logging
import tempfile
import re
from telegram.ext import ConversationHandler
from config import(
  GOOGLE_API_KEY,
  TELEGRAM_TOKEN
  )
from dotenv import load_dotenv
load_dotenv()
# User data management
USER_DATA_FILE = 'user_data.json'

def registrar_usuario(chat_id):
    """Registra um novo usuário ou garante que um usuário existente tenha a estrutura de dados correta."""
    chat_id_str = str(chat_id)
    try:
        try:
            with open(USER_DATA_FILE, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"users": {}}

        if chat_id_str not in data.get("users", {}):
            data.setdefault("users", {})[chat_id_str] = {"email": None}
            with open(USER_DATA_FILE, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Novo usuário registrado: {chat_id_str}")

    except Exception as e:
        logger.error(f"Erro ao registrar usuário {chat_id_str}: {e}")

# Configuração do Logging -----
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='borg3_logs.txt'
)
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
console.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(console)
gpt_logger = logging.getLogger("genai_logger")
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")

# Configuração da API ----
API_KEY = GOOGLE_API_KEY
assert API_KEY, "API Key não encontrada."
os.environ["GOOGLE_API_KEY"] = API_KEY
client = genai.Client()
MODEL_ID = "gemini-2.0-flash"

# Gerenciamento de sessões por chat_id ----
async def get_session(chat_id, agent_name):
    """Cria uma nova sessão para o chat_id e agente especificado."""
    session_service = InMemorySessionService()
    session_id = f"{agent_name}_{chat_id}"
    session = session_service.create_session(
        app_name=agent_name,
        user_id=str(chat_id),
        session_id=session_id
    )
    logger.debug(f"Sessão criada para chat_id {chat_id}, agente {agent_name}: {session_id}")
    return session_service, session

#Configuração que chama o agente ----
async def call_agent(agent: Agent, message_text: str, chat_id: str, verbose=False) -> str:
    """Chama um agente com uma nova sessão para o chat_id."""
    try:
        session_service, session = await get_session(chat_id, agent.name)
        runner = Runner(agent=agent, app_name=agent.name, session_service=session_service)
        content = types.Content(role="user", parts=[types.Part(text=message_text)])

        final_response = ""
        async for event in runner.run_async(user_id=str(chat_id), session_id=session.id, new_message=content):
            if event.is_final_response():
                for part in event.content.parts:
                    if part.text:
                        final_response += part.text + "\n"
        if verbose:
            logger.debug(f"[DEBUG: Resposta do agente {agent.name} para chat_id {chat_id}]:\n{final_response}")
        return final_response.strip()
    except ValueError as e:
        logger.error(f"Erro ao chamar agente {agent.name} para chat_id {chat_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao chamar agente {agent.name} para chat_id {chat_id}: {e}")
        raise

def criar_agente_rastreador(topico, data):
    return Agent(
        name="agente_rastreador",
        model=MODEL_ID,
        instruction = f"""
Você é um assistente de pesquisa especializado em identificar tendências de mercado. Sua tarefa é analisar as principais fontes da internet (como Google, redes sociais, sites de notícias, fóruns e blogs) para descobrir os temas, hashtags e notícias mais relevantes e emergentes sobre o tópico: {topico}.

- Foque nos assuntos mais mencionados e engajadores dos últimos 30 dias, até {data}.
- Considere conteúdos virais, debates em alta, novos comportamentos de consumo, tecnologias emergentes, movimentos culturais e qualquer outro sinal de tendência relacionado a {topico}.
- Apresente uma lista objetiva com os principais temas, hashtags e manchetes mais relevantes e recentes.
- Caso não haja informações suficientes, sugira ao usuário refinar o tópico com algo mais específico ou atual.
- Seja claro, direto e conciso, evitando formatações desnecessárias como markdowns do Telegram.
        """,
        description="Agente rastreador de tendências",
        tools=[google_search]
    )

def criar_agente_analista(topico, dados):
    return Agent(
        name="agente_analista",
        model=MODEL_ID,
        instruction=f"""
Você é um analista de mercado sênior e estrategista de conteúdo. Sua missão é transformar dados brutos sobre o tópico "{topico}" em um plano de ação claro e detalhado.

Com base nos dados fornecidos, realize uma análise aprofundada e apresente suas descobertas nas seguintes seções, utilizando uma linguagem visualmente atraente com emojis estratégicos:

- **Análise de Tendências e Sentimento** 📈:
  - **Temas em Alta**: Identifique os 3-5 subtemas mais quentes e com maior engajamento.
  - **Sentimento Geral**: Classifique o sentimento predominante (positivo, negativo, neutro) e justifique com exemplos de menções ou contextos.
  - **Principais Influenciadores**: Liste os principais criadores de conteúdo, marcas ou veículos que estão liderando a conversa.

- **Perfil do Público-Alvo** 🎯:
  - **Demografia**: Descreva a faixa etária, gênero e localização do público mais engajado.
  - **Interesses e Comportamentos**: Detalhe os interesses, hobbies e comportamentos de consumo do público.
  - **Dores e Necessidades**: Identifique os principais problemas, desafios e necessidades que o público expressa.

- **Análise Competitiva** ⚔️:
  - **Principais Concorrentes**: Identifique 2-3 concorrentes diretos ou indiretos que atuam no mesmo nicho.
  - **Estratégias de Sucesso**: Analise o que está funcionando para eles (tipos de conteúdo, campanhas, etc.).
  - **Lacunas e Oportunidades**: Aponte as áreas que os concorrentes não estão explorando e que representam uma oportunidade.

- **Recomendações Estratégicas e de Conteúdo** 💡:
  - **Pilares de Conteúdo**: Sugira 3-4 pilares de conteúdo para abordar as dores e interesses do público.
  - **Formatos de Conteúdo**: Recomende os formatos mais eficazes (vídeos curtos, blog posts, infográficos, etc.) com base no perfil do público.
  - **Exemplos de Títulos**: Forneça 3 exemplos de títulos de conteúdo que poderiam ser criados para cada pilar.

Se os dados forem insuficientes, informe ao usuário de forma clara e sugira maneiras de refinar a pesquisa para obter melhores resultados. O objetivo é entregar um relatório que sirva como um verdadeiro guia estratégico.
        """,
        description="Agente de análise de tendências"
    )

def criar_agente_relatorio(topico, briefing):
    return Agent(
        name="agente_relatorio",
        model=MODEL_ID,
        instruction=f"""
Você é um especialista em marketing e comunicação, encarregado de traduzir a análise de tendências sobre "{topico}" em um plano de marketing acionável.

Com base no briefing fornecido, estruture sua resposta em três seções claras e diretas:

1. **Plano de Marketing Estratégico** 🚀:
   - **Objetivos da Campanha**: Defina 2-3 objetivos SMART (Específicos, Mensuráveis, Atingíveis, Relevantes, Temporais).
   - **Mensagem Chave**: Elabore uma mensagem central que ressoe com as "dores" e interesses do público-alvo.
   - **Canais de Marketing**: Recomende os canais mais eficazes (ex: Instagram, TikTok, Blog, E-mail Marketing) e justifique a escolha.
   - **KPIs (Indicadores-Chave de Desempenho)**: Liste os principais KPIs para medir o sucesso da campanha (ex: taxa de engajamento, crescimento de seguidores, tráfego do site, taxa de conversão).

2. **Prompt de Imagem para Infográfico** 🎨:
   - **Conceito Visual**: Descreva o conceito geral do infográfico (ex: "jornada do consumidor", "ecossistema de conteúdo", "pilares da estratégia").
   - **Estrutura e Layout**: Detalhe a organização visual, incluindo a disposição dos elementos, hierarquia de informações e fluxo de leitura.
   - **Elementos Gráficos**: Especifique os tipos de gráficos (barras, pizza, linha do tempo), ícones, ilustrações e a paleta de cores.
   - **Texto e Dados**: Indique os principais dados e textos que devem ser incluídos no infográfico.

   **Exemplo de Prompt de Imagem**:
   "Crie um infográfico vibrante e dinâmico para uma campanha de marketing sobre {topico}. O layout deve ser dividido em quatro seções: 'Nosso Público', 'Nossa Mensagem', 'Nossos Canais' e 'Nosso Sucesso'. Use um gráfico de pizza para a demografia do público, ícones para representar os canais e um gráfico de barras para os KPIs. A paleta de cores deve ser [cor 1], [cor 2] e [cor 3], transmitindo uma sensação de energia e inovação."

3. **Recomendação de Próximos Passos** 👣:
   - **Ações Imediatas**: Sugira as 2-3 primeiras ações que devem ser tomadas para colocar o plano em prática.
   - **Ferramentas Úteis**: Recomende ferramentas (ex: Canva, Google Analytics, Hootsuite) que possam auxiliar na execução e monitoramento da campanha.

O objetivo é fornecer um guia prático e inspirador que capacite o usuário a agir com base nos insights coletados.
        """,
        description="Gerador de relatório multimodal"
    )
#Extrai o prompt para gerar a imagem descritiva do relatorio feito pelo agente de relatorio----
def extrair_prompt_imagem(relatorio_texto):
    """Extrai o prompt de imagem do relatório."""
    marker = "Prompt da imagem:"
    if marker in relatorio_texto:
        partes = relatorio_texto.split(marker)
        if len(partes) > 1:
            prompt_bruto = partes[1].strip()
            return prompt_bruto
    return None
#gera a imagem e envia ao user----
async def gerar_e_enviar_imagem(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str):
    """Gera uma imagem e a envia ao usuário via Telegram."""
    chat_id = update.effective_chat.id
    logger.info(f"Iniciando geração de imagem para chat_id {chat_id} com prompt: {prompt}")
    
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
        
        image_model = client.models
        contents = [prompt]
        
        response = image_model.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=contents,
            config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE'])
        )
        
        # Verifica se a resposta contém candidatos válidos
        if not response.candidates or not response.candidates[0].content.parts:
            logger.warning(f"Nenhum conteúdo de imagem retornado pela API para chat_id {chat_id}")
            await update.message.reply_text("❌ Nenhuma imagem foi gerada pela API.")
            return

        found_image = False
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                try:
                    # Extrai os dados binários da imagem----
                    image_data = part.inline_data.data
                    logger.debug(f"Dados inline recebidos para chat_id {chat_id}: {image_data[:50]}... (tamanho: {len(image_data)} bytes)")
                    
                    # Tenta abrir os dados como imagem----
                    try:
                        image = Image.open(BytesIO(image_data))
                        logger.debug(f"Imagem aberta com sucesso para chat_id {chat_id}, formato: {image.format}")
                    except PIL.UnidentifiedImageError as img_error:
                        logger.error(f"Erro ao identificar imagem para chat_id {chat_id}: {img_error}")
                        await update.message.reply_text("⚠️ Erro: Não foi possível processar a imagem gerada.")
                        continue

                    # Salva e envia a imagem para o usuário----
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                        image.save(tmp_file, format="PNG")
                        tmp_file_path = tmp_file.name

                    await context.bot.send_photo(chat_id=chat_id, photo=open(tmp_file_path, 'rb'))
                    os.remove(tmp_file_path)
                    logger.info(f"Imagem enviada com sucesso para chat_id {chat_id}")
                    
                    found_image = True
                    break  

                except Exception as inner_e:
                    logger.error(f"Erro ao processar imagem para chat_id {chat_id}: {inner_e}")
                    continue

            elif part.text is not None:
                logger.debug(f"Parte contém texto para chat_id {chat_id}: {part.text[:50]}...")
            else:
                logger.debug(f"Parte sem inline_data ou texto para chat_id {chat_id}")
        
        if not found_image:
            logger.warning(f"Nenhuma imagem válida encontrada na resposta da API para chat_id {chat_id}")
            await update.message.reply_text("🧩 Hmm... Nada de imagem por aqui! Vamos tentar um prompt mais afiado?")

    except Exception as e:
        logger.error(f"Erro geral ao gerar imagem para chat_id {chat_id}: {e}")
        await update.message.reply_text("❌ Desculpe! Ocorreu um erro ao tentar gerar a imagem.")
#Processador do topico----      
async def processar_topico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa o tópico enviado pelo usuário e executa o pipeline."""
    chat_id = update.effective_chat.id
    registrar_usuario(chat_id)
    topico = update.message.text
    hoje = str(date.today())
    logger.debug(f"Recebida mensagem do chat_id {chat_id}: {topico}")

    try:
        # Rastreamento----
        logger.info(f"Iniciando rastreamento para tópico '{topico}'")
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await update.message.reply_text("📊 Rastreamento de tendências em andamento... Isso pode levar alguns segundos.")
        rastreador = criar_agente_rastreador(topico, hoje)
        dados = await call_agent(rastreador, f"Tópico: {topico}\nData: {hoje}", chat_id)
        await update.message.reply_text(dados)
        logger.debug(f"Rastreamento concluído para chat_id {chat_id}")

        # Análise----
        logger.info(f"Iniciando análise para tópico '{topico}'")
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await update.message.reply_text("📈 Análise de dados iniciada. Preparando insights estratégicos...")
        analista = criar_agente_analista(topico, dados)
        briefing = await call_agent(analista, f"Dados: {dados}", chat_id)
        await update.message.reply_text(briefing)
        logger.debug(f"Análise concluída para chat_id {chat_id}")

        # Relatório----
        logger.info(f"Iniciando geração de relatório para tópico '{topico}'")
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await update.message.reply_text("🤖 Relatório multimodal em construção... Integrando dados e visualizações.")
        relator = criar_agente_relatorio(topico, briefing)
        relatorio = await call_agent(relator, f"Briefing: {briefing}", chat_id)
        await update.message.reply_text(relatorio)
        logger.debug(f"Relatório concluído para chat_id {chat_id}")

        # Geração de Imagem----
        logger.info(f"Extraindo prompt de imagem para chat_id {chat_id}")
        prompt_imagem = extrair_prompt_imagem(relatorio)
        if prompt_imagem:
            logger.info(f"Iniciando geração de infográfico para chat_id {chat_id}")
            await update.message.reply_text("🧬 Transformando dados em imagem... Infográfico em progresso!")
            await gerar_e_enviar_imagem(update, context, prompt_imagem)
            logger.debug(f"Infográfico enviado para chat_id {chat_id}")
        else:
            logger.warning(f"Não foi possível extrair prompt de imagem para chat_id {chat_id}")
            await update.message.reply_text("Desculpe! Não foi possível extrair o prompt da imagem do relatório.")
    except Exception as e:
        logger.error(f"Erro ao processar tópico para chat_id {chat_id}: {e}")
        await update.message.reply_text(
            f"Ocorreu um erro ao processar o tópico. Tente novamente ou envie um novo tópico."
        )

# Estados da conversa
ASKING_EMAIL = 0

async def promo_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia o funil de captura de leads."""
    await update.message.reply_text(
        "🎉 Quer receber um resumo semanal das tendências de mercado no seu e-mail?\n\n"
        "Deixe seu melhor e-mail abaixo para se inscrever!"
    )
    return ASKING_EMAIL

async def receber_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Salva o e-mail do usuário."""
    chat_id = update.effective_chat.id
    email = update.message.text

    # Validação simples de e-mail
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        await update.message.reply_text("🤔 E-mail inválido. Por favor, envie um e-mail válido.")
        return ASKING_EMAIL

    try:
        with open(USER_DATA_FILE, 'r') as f:
            data = json.load(f)

        data["users"][str(chat_id)]["email"] = email

        with open(USER_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)

        await update.message.reply_text("✅ Sucesso! Seu e-mail foi registrado. Fique de olho na sua caixa de entrada!")
        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Erro ao salvar e-mail para {chat_id}: {e}")
        await update.message.reply_text("❌ Ocorreu um erro ao salvar seu e-mail. Tente novamente.")
        return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela a operação."""
    await update.message.reply_text("Operação cancelada.")
    return ConversationHandler.END

#Configuração dk telegram----
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia uma mensagem para todos os usuários registrados."""
    admin_ids = [85732168, 5913164677] # Substitua pelo seu ID de admin do Telegram
    chat_id = update.effective_chat.id

    if chat_id not in admin_ids:
        await update.message.reply_text("Você não tem permissão para usar este comando.")
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Por favor, forneça uma mensagem para o broadcast. Uso: /broadcast <mensagem>")
        return

    try:
        with open(USER_DATA_FILE, 'r') as f:
            data = json.load(f)
        users = data.get("users", {}).keys()
    except (FileNotFoundError, json.JSONDecodeError):
        users = []

    if not users:
        await update.message.reply_text("Nenhum usuário registrado para receber o broadcast.")
        return

    success_count = 0
    failure_count = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            success_count += 1
            await asyncio.sleep(0.1)  # Evita rate limiting
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem para {user_id}: {e}")
            failure_count += 1

    await update.message.reply_text(
        f"Broadcast concluído!\n"
        f"Enviado para: {success_count} usuários\n"
        f"Falhas: {failure_count}"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para o comando /start."""
    chat_id = update.effective_chat.id
    registrar_usuario(chat_id)
    await update.message.reply_text("Analyzer está on! Mande o tópico que mando pra você tudo que precisa ✨!")
from flask import Flask
from threading import Thread

def start_ping_server():
    app = Flask("ping_server")

    @app.route("/ping")
    def ping():
        return "pong", 200

    app.run(host="0.0.0.0", port=8080)

# Inicia o mini servidor Flask em paralelo
Thread(target=start_ping_server).start()
def main():
    """Configura e inicia o bot do Telegram no modo webhook (Render)."""
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("promo", promo_start)],
        states={
            ASKING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_email)]
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_topico))

    # Configurações para Render
    PORT = int(os.environ.get("PORT", 8080))
    WEBHOOK_URL = f"https://{os.environ.get('RENDER_EXTERNAL_URL')}/"

    # Inicia com webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()