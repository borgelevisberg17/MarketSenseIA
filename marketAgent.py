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
from config import(
  GOOGLE_API_KEY,
  TELEGRAM_TOKEN
  )
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
Você é um analista de mercado experiente e estratégico. Com base nas informações encontradas sobre o tópico: {topico}, sua missão é extrair insights valiosos e prontos para ação.

Analise os dados disponíveis e apresente as seguintes seções de forma clara, objetiva e visualmente atrativa com o uso moderado de emojis:

- Temas em Alta 🔥: destaque os assuntos mais discutidos e relevantes relacionados ao tópico.
- Sentimento Geral 📊: indique se o tom das menções é predominantemente positivo, negativo ou neutro.
- Público Dominante 🎯: identifique o perfil do público mais engajado (faixa etária, interesses, localização, etc.).
- Palavras-chave Frequentes 🧠: apresente os termos mais recorrentes que ajudam a entender o foco das conversas.
- Oportunidades 💡: sugira ideias de conteúdo, produtos ou estratégias com base nas lacunas ou interesses emergentes.

Caso os dados sejam insuficientes para uma análise completa:
- Avise o usuário de forma educada e direta.
- Sugira fornecer mais detalhes ou reformular com um tópico mais específico ou atual.

Resumo bem elaborado e direto ao ponto, com foco na clareza, utilidade e captação de insights. Evite rodeios e formatações complexas.
        """,
        description="Agente de análise de tendências"
    )

def criar_agente_relatorio(topico, briefing):
    return Agent(
        name="agente_relatorio",
        model=MODEL_ID,
        instruction=f"""
Você é um gerador de relatório profissional sobre o tema: {topico}.

Com base no briefing de dados coletados, sua tarefa é gerar três seções:

1. Resumo Executivo 
Apresente um resumo claro e direto com os principais insights do tema. Não utilize markdowns nem estilos de formatação. Use emojis de forma estratégica para destacar os pontos mais relevantes, mas mantenha um estilo conciso e objetivo.

2. Prompt de Imagem para o Gemini Image 
Forneça um prompt detalhado no seguinte formato, pronto para ser usado diretamente:

Prompt da imagem:  
Crie um infográfico moderno e tecnológico com fundo claro e visual estilo dashboard, ilustrando:  
- Principais temas de destaque encontrados no briefing (liste 2 ou 3)  
- Representação visual com gráficos: gráfico de barras (para mostrar crescimento ou comparação), gráfico de pizza (para distribuição de público ou categorias), ou outro formato ideal  
- Ícones ou elementos visuais que representem palavras-chave mencionadas  
- Público-alvo principal de forma simbólica (ex: silhuetas, avatares ou pictogramas)  
- Estilo moderno, tecnológico, com luz suave e boa hierarquia visual

Use vocabulário visual, técnico e descritivo. Evite ambiguidade e seja específico para evitar erros na geração da imagem.

3. Recomendação de Gráfico Ideal  
Indique o melhor tipo de gráfico para representar os dados obtidos (ex: barras, linhas, pizza, radar) e justifique brevemente com base nos dados apresentados, no tipo de informação e na clareza visual.

Se os dados forem insuficientes, sinalize de forma direta e sugira ao usuário complementar o briefing ou definir um tópico mais específico.
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
#Configuração dk telegram----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para o comando /start."""
    await update.message.reply_text("Analyzer está on! Mande o tópico que mando pra você tudo que precisa ✨!")

def main():
    """Configura e inicia o bot do Telegram."""
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, processar_topico))

    application.run_polling()

if __name__ == "__main__":
    main()