import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import Update
import json

from telegram_bot import TelegramBot
from scheduler import PostingScheduler
from main import Config

logger = logging.getLogger(__name__)

class WebhookServer:
    def __init__(self):
        self.config = Config()
        self.telegram_bot = TelegramBot(self.config)
        self.scheduler = PostingScheduler(self.config, self.telegram_bot)
        
    async def init_app(self):
        """Inicializa aplicação webhook"""
        app = web.Application()
        
        # Configurar webhook
        webhook_path = f"/webhook/{self.config.BOT_TOKEN}"
        
        # Handler para webhook
        webhook_handler = SimpleRequestHandler(
            dispatcher=self.telegram_bot.dp,
            bot=self.telegram_bot.bot,
            secret_token="webhook_secret"
        )
        
        webhook_handler.register(app, path=webhook_path)
        
        # Endpoint de health check
        async def health_check(request):
            return web.Response(text="Bot OK")
        
        app.router.add_get("/health", health_check)
        
        # Endpoint raiz
        async def root(request):
            return web.Response(text="Bot AliExpress Webhook Server")
        
        app.router.add_get("/", root)
        
        # Inicializar componentes
        await self.telegram_bot.product_ai.init_db()
        self.scheduler.start()
        
        logger.info("Webhook server iniciado!")
        
        return app
    
    async def start_webhook(self):
        """Inicia servidor webhook"""
        app = await self.init_app()
        
        # Configurar webhook no Telegram
        webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_URL', 'localhost')}/webhook/{self.config.BOT_TOKEN}"
        
        await self.telegram_bot.bot.set_webhook(
            url=webhook_url,
            secret_token="webhook_secret"
        )
        
        logger.info(f"Webhook configurado: {webhook_url}")
        
        # Iniciar servidor
        runner = web.AppRunner(app)
        await runner.setup()
        
        port = int(os.getenv('PORT', 8000))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"Servidor webhook rodando na porta {port}")
        
        # Manter rodando
        try:
            await asyncio.Future()
        except KeyboardInterrupt:
            logger.info("Parando servidor...")
            await runner.cleanup()

if __name__ == "__main__":
    server = WebhookServer()
    asyncio.run(server.start_webhook())
