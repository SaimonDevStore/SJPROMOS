import os
import asyncio
import logging
import signal
import sys
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Config:
    """Configurações do bot"""
    TRACKING_ID = os.getenv('TRACKING_ID', 'BOT_TELEGRAM')
    APP_KEY = os.getenv('APP_KEY', '521022')
    APP_SECRET = os.getenv('APP_SECRET', 'Ve15nlPdIv5U7WRwAsWFHCqY2LRnsBes')
    BOT_TOKEN = os.getenv('BOT_TOKEN', '8378547653:AAF6OxBv6x-UkeVR968u2nUmgwt23vyfmZw')
    CHANNEL_ID = os.getenv('CHANNEL_ID', '@SJPROMOS')
    POST_MIN_PER_HOUR = int(os.getenv('POST_MIN_PER_HOUR', '20'))
    POST_MAX_PER_HOUR = int(os.getenv('POST_MAX_PER_HOUR', '25'))
    START_TIME = os.getenv('START_TIME', '08:00')
    END_TIME = os.getenv('END_TIME', '22:00')
    TIMEZONE = os.getenv('TIMEZONE', 'America/Sao_Paulo')
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '123456789'))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Importar módulos
from telegram_bot import TelegramBot
from scheduler import PostingScheduler

class BotManager:
    """Gerenciador principal do bot"""
    
    def __init__(self):
        self.config = Config()
        self.telegram_bot = None
        self.scheduler = None
        self.running = False
        
    async def start(self):
        """Inicia o bot completo"""
        try:
            logger.info("Iniciando Bot AliExpress...")
            
            # Inicializar bot do Telegram
            self.telegram_bot = TelegramBot(self.config)
            
            # Inicializar agendador
            self.scheduler = PostingScheduler(self.config, self.telegram_bot)
            self.scheduler.start()
            
            self.running = True
            
            # Configurar handlers de sinal para shutdown graceful
            def signal_handler(signum, frame):
                logger.info(f"Sinal {signum} recebido. Iniciando shutdown...")
                asyncio.create_task(self.stop())
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            logger.info("Bot iniciado com sucesso!")
            
            # Iniciar bot do Telegram (bloqueia até parar)
            await self.telegram_bot.start()
            
        except Exception as e:
            logger.error(f"Erro ao iniciar bot: {e}")
            await self.stop()
    
    async def stop(self):
        """Para o bot de forma segura"""
        try:
            if not self.running:
                return
                
            logger.info("Parando bot...")
            self.running = False
            
            # Parar agendador
            if self.scheduler:
                self.scheduler.stop()
            
            # Parar bot do Telegram
            if self.telegram_bot:
                await self.telegram_bot.stop()
            
            logger.info("Bot parado com sucesso!")
            
        except Exception as e:
            logger.error(f"Erro ao parar bot: {e}")
        finally:
            sys.exit(0)

async def main():
    """Função principal"""
    bot_manager = BotManager()
    
    # Se estiver no Render (PORT definido), usar webhook
    if os.getenv('PORT'):
        logger.info("Detectado ambiente Render - configurando webhook")
        try:
            # Aguardar bot estar pronto
            await asyncio.sleep(2)
            
            # Configurar webhook básico para evitar conflitos
            webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_URL', 'localhost')}/webhook"
            await bot_manager.telegram_bot.bot.set_webhook(webhook_url)
            logger.info(f"Webhook configurado: {webhook_url}")
            
            # Parar polling e usar apenas webhook
            bot_manager.telegram_bot.use_webhook = True
            
        except Exception as e:
            logger.warning(f"Erro ao configurar webhook: {e}")
    
    await bot_manager.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        sys.exit(1)
