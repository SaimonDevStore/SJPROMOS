import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import json
import os

from aliexpress_api import AliExpressAPI
from product_ai import ProductAI

logger = logging.getLogger(__name__)

class AdminStates(StatesGroup):
    """Estados para comandos administrativos"""
    waiting_frequency = State()
    waiting_category = State()
    waiting_manual_link = State()

class TelegramBot:
    """Bot principal do Telegram com comandos administrativos"""
    
    def __init__(self, config):
        self.config = config
        self.bot = Bot(token=config.BOT_TOKEN)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.channel_id = config.CHANNEL_ID
        self.admin_id = config.ADMIN_USER_ID
        self.is_active = True
        
        # Inicializar componentes
        self.aliexpress_api = AliExpressAPI(
            config.APP_KEY, 
            config.APP_SECRET, 
            config.TRACKING_ID
        )
        self.product_ai = ProductAI()
        
        # Registrar comandos e callbacks
        self._register_commands()
        self._register_callbacks()
    
    def _register_commands(self):
        """Registra todos os comandos administrativos"""
        
        @self.dp.message(CommandStart())
        async def start_command(message: Message):
            if message.from_user.id != self.admin_id:
                await message.answer("❌ Acesso negado. Apenas administradores autorizados.")
                return
            
            welcome_text = """
🤖 **Bot AliExpress - Painel Administrativo**

Bem-vindo ao painel de controle do bot automático!

**Comandos disponíveis:**
/status - Status atual do bot
/pausar - Pausar postagens automáticas
/retomar - Retomar postagens
/frequencia - Alterar frequência de posts
/categoria - Gerenciar categorias
/estatisticas - Ver estatísticas
/forcar_post - Postar produto manualmente
/logs - Ver logs recentes
/teste_api - Testar conexão com API
/ajustar_horario - Alterar horário de funcionamento

Digite /help para ver ajuda detalhada.
            """
            await message.answer(welcome_text, parse_mode='Markdown')
        
        @self.dp.message(Command("help"))
        async def help_command(message: Message):
            if message.from_user.id != self.admin_id:
                return
            
            help_text = """
📖 **Ajuda - Comandos Administrativos**

**Controle Básico:**
• `/status` - Ver status atual do bot
• `/pausar` - Pausar todas as postagens
• `/retomar` - Retomar postagens automáticas

**Configuração:**
• `/frequencia <min> <max>` - Alterar posts por hora
• `/ajustar_horario <inicio> <fim>` - Alterar horário (ex: 08:00 22:00)
• `/categoria ativar|desativar <nome>` - Gerenciar categorias

**Monitoramento:**
• `/estatisticas [periodo]` - Ver estatísticas (hoje, semana, mês)
• `/logs` - Ver logs recentes
• `/teste_api` - Testar conexão com AliExpress

**Postagem Manual:**
• `/forcar_post <link>` - Postar produto específico
• `/buscar <termo>` - Buscar produtos por termo

**Exemplos:**
• `/frequencia 15 20` - 15-20 posts por hora
• `/categoria ativar electronics` - Ativar categoria eletrônicos
• `/estatisticas semana` - Estatísticas da semana
            """
            await message.answer(help_text, parse_mode='Markdown')
        
        @self.dp.message(Command("status"))
        async def status_command(message: Message):
            if message.from_user.id != self.admin_id:
                return
            
            try:
                # Obter estatísticas
                stats = await self.product_ai.get_statistics()
                
                status_text = f"""
🤖 **Status do Bot AliExpress**

✅ **Estado**: {'🟢 Ativo' if self.is_active else '🔴 Pausado'}
📊 **Configurações**:
• Posts/hora: {self.config.POST_MIN_PER_HOUR}-{self.config.POST_MAX_PER_HOUR}
• Horário: {self.config.START_TIME} - {self.config.END_TIME}
• Timezone: {self.config.TIMEZONE}
• Canal: {self.config.CHANNEL_ID}

📈 **Estatísticas**:
• Total de posts: {stats.get('total_posts', 0)}
• Total de cliques: {stats.get('total_clicks', 0)}
• Score médio: {stats.get('avg_score', 0):.1f}

🕐 **Última atualização**: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
                """
                
                # Adicionar botões de controle rápido
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="⏸️ Pausar" if self.is_active else "▶️ Retomar", 
                                           callback_data="toggle_status"),
                        InlineKeyboardButton(text="📊 Estatísticas", callback_data="show_stats")
                    ],
                    [
                        InlineKeyboardButton(text="🔧 Configurações", callback_data="show_config"),
                        InlineKeyboardButton(text="📋 Logs", callback_data="show_logs")
                    ]
                ])
                
                await message.answer(status_text, parse_mode='Markdown', reply_markup=keyboard)
                
            except Exception as e:
                logger.error(f"Erro no comando status: {e}")
                await message.answer(f"❌ Erro ao obter status: {e}")
        
        @self.dp.message(Command("pausar"))
        async def pause_command(message: Message):
            if message.from_user.id != self.admin_id:
                return
            
            self.is_active = False
            await message.answer("⏸️ **Bot pausado!**\n\nAs postagens automáticas foram interrompidas.", parse_mode='Markdown')
            logger.info("Bot pausado pelo administrador")
        
        @self.dp.message(Command("retomar"))
        async def resume_command(message: Message):
            if message.from_user.id != self.admin_id:
                return
            
            self.is_active = True
            await message.answer("▶️ **Bot retomado!**\n\nAs postagens automáticas foram reativadas.", parse_mode='Markdown')
            logger.info("Bot retomado pelo administrador")
        
        @self.dp.message(Command("frequencia"))
        async def frequency_command(message: Message):
            if message.from_user.id != self.admin_id:
                return
            
            try:
                args = message.text.split()[1:]
                if len(args) == 2:
                    min_posts = int(args[0])
                    max_posts = int(args[1])
                    
                    if min_posts < 1 or max_posts < min_posts or max_posts > 50:
                        await message.answer("❌ Valores inválidos! Use: /frequencia <min> <max>\nExemplo: /frequencia 20 25")
                        return
                    
                    self.config.POST_MIN_PER_HOUR = min_posts
                    self.config.POST_MAX_PER_HOUR = max_posts
                    
                    await message.answer(
                        f"✅ **Frequência alterada!**\n\n"
                        f"Posts por hora: {min_posts}-{max_posts}\n"
                        f"A alteração será aplicada na próxima hora.",
                        parse_mode='Markdown'
                    )
                    logger.info(f"Frequência alterada para {min_posts}-{max_posts} posts/hora")
                else:
                    await message.answer("❌ **Uso incorreto!**\n\nUse: `/frequencia <min> <max>`\nExemplo: `/frequencia 20 25`", parse_mode='Markdown')
                    
            except ValueError:
                await message.answer("❌ **Valores inválidos!**\n\nUse números inteiros.\nExemplo: `/frequencia 20 25`", parse_mode='Markdown')
            except Exception as e:
                logger.error(f"Erro no comando frequencia: {e}")
                await message.answer(f"❌ Erro ao alterar frequência: {e}")
        
        @self.dp.message(Command("estatisticas"))
        async def statistics_command(message: Message):
            if message.from_user.id != self.admin_id:
                return
            
            try:
                args = message.text.split()[1:]
                period = args[0] if args else "hoje"
                
                stats = await self.product_ai.get_statistics()
                
                # Calcular período
                now = datetime.now()
                if period == "hoje":
                    period_text = "Hoje"
                elif period == "semana":
                    period_text = "Esta semana"
                elif period == "mes":
                    period_text = "Este mês"
                else:
                    period_text = "Todos os tempos"
                
                stats_text = f"""
📊 **Estatísticas - {period_text}**

📈 **Performance Geral:**
• Total de posts: {stats.get('total_posts', 0)}
• Total de cliques: {stats.get('total_clicks', 0)}
• Score médio: {stats.get('avg_score', 0):.1f}/100
• Taxa de engajamento: {(stats.get('total_clicks', 0) / max(stats.get('total_posts', 1), 1)):.2f} cliques/post

🏆 **Top 5 Produtos Mais Clicados:**
                """
                
                top_products = stats.get('top_products', [])
                for i, (title, clicks) in enumerate(top_products[:5], 1):
                    short_title = title[:50] + "..." if len(title) > 50 else title
                    stats_text += f"\n{i}. {short_title} - {clicks} cliques"
                
                if not top_products:
                    stats_text += "\nNenhum produto postado ainda."
                
                stats_text += f"\n\n🕐 **Atualizado em**: {now.strftime('%d/%m/%Y %H:%M:%S')}"
                
                await message.answer(stats_text, parse_mode='Markdown')
                
            except Exception as e:
                logger.error(f"Erro no comando estatisticas: {e}")
                await message.answer(f"❌ Erro ao obter estatísticas: {e}")
        
        @self.dp.message(Command("logs"))
        async def logs_command(message: Message):
            if message.from_user.id != self.admin_id:
                return
            
            try:
                with open('bot.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    last_lines = ''.join(lines[-30:])  # Últimas 30 linhas
                    
                    if len(last_lines) > 4000:  # Limite do Telegram
                        last_lines = last_lines[-4000:]
                    
                    await message.answer(f"📋 **Últimos logs**:\n```\n{last_lines}\n```", parse_mode='Markdown')
                    
            except FileNotFoundError:
                await message.answer("📋 Nenhum log encontrado")
            except Exception as e:
                logger.error(f"Erro ao ler logs: {e}")
                await message.answer(f"❌ Erro ao ler logs: {e}")
        
        @self.dp.message(Command("teste_api"))
        async def test_api_command(message: Message):
            if message.from_user.id != self.admin_id:
                return
            
            await message.answer("🔄 Testando conexão com API da AliExpress...")
            
            try:
                # Testar conexão
                is_connected = await self.aliexpress_api.test_connection()
                
                if is_connected:
                    # Buscar alguns produtos de teste
                    products = await self.aliexpress_api.get_hot_products(limit=5)
                    
                    if products:
                        test_result = f"""
✅ **Teste da API - Sucesso!**

🔗 Conexão: OK
📦 Produtos encontrados: {len(products)}
🎯 Tracking ID: {self.config.TRACKING_ID}

**Produtos de teste:**
                        """
                        
                        for i, product in enumerate(products[:3], 1):
                            title = product.get('product_title', 'Sem título')[:40]
                            discount = product.get('calculated_discount', 0)
                            test_result += f"\n{i}. {title}... - {discount:.0f}% desconto"
                        
                        await message.answer(test_result, parse_mode='Markdown')
                    else:
                        await message.answer("⚠️ **API conectada mas nenhum produto encontrado**\n\nVerifique os parâmetros de busca.")
                else:
                    await message.answer("❌ **Falha na conexão com a API**\n\nVerifique as credenciais e conexão de internet.")
                    
            except Exception as e:
                logger.error(f"Erro no teste da API: {e}")
                await message.answer(f"❌ **Erro no teste da API**:\n\n{e}")
        
        @self.dp.message(Command("forcar_post"))
        async def force_post_command(message: Message):
            if message.from_user.id != self.admin_id:
                return
            
            try:
                args = message.text.split()[1:]
                if not args:
                    await message.answer("❌ **Uso incorreto!**\n\nUse: `/forcar_post <link_do_produto>`", parse_mode='Markdown')
                    return
                
                product_url = args[0]
                await message.answer("🔄 Buscando produto...")
                
                # Extrair ID do produto do URL (simplificado)
                product_id = self._extract_product_id(product_url)
                
                if product_id:
                    # Buscar detalhes do produto
                    product = await self.aliexpress_api.get_product_details(product_id)
                    
                    if product:
                        # Postar produto
                        await self.post_product(product)
                        await message.answer("✅ **Produto postado com sucesso!**")
                    else:
                        await message.answer("❌ **Produto não encontrado**\n\nVerifique se o link está correto.")
                else:
                    await message.answer("❌ **Link inválido**\n\nUse um link válido da AliExpress.")
                    
            except Exception as e:
                logger.error(f"Erro no comando forcar_post: {e}")
                await message.answer(f"❌ Erro ao postar produto: {e}")
        
        @self.dp.message(Command("buscar"))
        async def search_command(message: Message):
            if message.from_user.id != self.admin_id:
                return
            
            try:
                args = message.text.split()[1:]
                if not args:
                    await message.answer("❌ **Uso incorreto!**\n\nUse: `/buscar <termo_de_busca>`", parse_mode='Markdown')
                    return
                
                search_term = " ".join(args)
                await message.answer(f"🔍 Buscando produtos com: '{search_term}'...")
                
                # Buscar produtos
                products = await self.aliexpress_api.search_products(search_term, limit=10)
                
                if products:
                    search_result = f"""
🔍 **Resultados da busca: '{search_term}'**

Encontrados {len(products)} produtos:
                    """
                    
                    for i, product in enumerate(products[:5], 1):
                        title = product.get('product_title', 'Sem título')[:50]
                        discount = product.get('calculated_discount', 0)
                        price = product.get('target_sale_price', 0)
                        
                        search_result += f"\n{i}. {title}...\n   💰 R$ {price:.2f} | 🎯 {discount:.0f}% desconto"
                    
                    # Adicionar botão para postar o primeiro produto
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📤 Postar Primeiro Produto", callback_data=f"post_first_{products[0].get('product_id', '')}")]
                    ])
                    
                    await message.answer(search_result, parse_mode='Markdown', reply_markup=keyboard)
                else:
                    await message.answer(f"❌ **Nenhum produto encontrado** para: '{search_term}'")
                    
            except Exception as e:
                logger.error(f"Erro no comando buscar: {e}")
                await message.answer(f"❌ Erro na busca: {e}")
    
    def _register_callbacks(self):
        """Registra callbacks dos botões inline"""
        
        @self.dp.callback_query()
        async def handle_callback(callback: CallbackQuery):
            if callback.from_user.id != self.admin_id:
                await callback.answer("❌ Acesso negado", show_alert=True)
                return
            
            data = callback.data
            
            if data == "toggle_status":
                self.is_active = not self.is_active
                status_text = "⏸️ Pausado" if not self.is_active else "▶️ Ativo"
                await callback.message.edit_text(
                    callback.message.text + f"\n\n🔄 Status alterado para: {status_text}",
                    parse_mode='Markdown'
                )
                await callback.answer(f"Status alterado para: {status_text}")
            
            elif data == "show_stats":
                await callback.answer("Carregando estatísticas...")
                # Reutilizar comando de estatísticas
                await self.statistics_command(callback.message)
            
            elif data == "show_config":
                await callback.answer("Carregando configurações...")
                config_text = f"""
🔧 **Configurações Atuais**

📊 **Postagem:**
• Posts/hora: {self.config.POST_MIN_PER_HOUR}-{self.config.POST_MAX_PER_HOUR}
• Horário: {self.config.START_TIME} - {self.config.END_TIME}
• Timezone: {self.config.TIMEZONE}

🔗 **API:**
• Tracking ID: {self.config.TRACKING_ID}
• Canal: {self.config.CHANNEL_ID}

Use os comandos para alterar as configurações.
                """
                await callback.message.answer(config_text, parse_mode='Markdown')
            
            elif data == "show_logs":
                await callback.answer("Carregando logs...")
                # Reutilizar comando de logs
                await self.logs_command(callback.message)
            
            elif data.startswith("post_first_"):
                product_id = data.replace("post_first_", "")
                await callback.answer("Postando produto...")
                
                try:
                    product = await self.aliexpress_api.get_product_details(product_id)
                    if product:
                        await self.post_product(product)
                        await callback.message.answer("✅ Produto postado com sucesso!")
                    else:
                        await callback.message.answer("❌ Erro ao obter detalhes do produto")
                except Exception as e:
                    await callback.message.answer(f"❌ Erro: {e}")
    
    def _extract_product_id(self, url: str) -> Optional[str]:
        """Extrai ID do produto do URL da AliExpress"""
        try:
            # Padrões comuns de URL da AliExpress
            import re
            
            patterns = [
                r'/item/(\d+)',
                r'product_id=(\d+)',
                r'/(\d+)\.html'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            return None
        except Exception:
            return None
    
    async def format_post(self, product: Dict) -> str:
        """Formata post do produto para o canal"""
        try:
            title = product.get('product_title', 'Produto sem título')
            if len(title) > 100:
                title = title[:97] + "..."
            
            original_price = float(product.get('target_original_price', 0))
            sale_price = float(product.get('target_sale_price', 0))
            discount = product.get('calculated_discount', 0)
            rating = product.get('rating', 0)
            volume = product.get('volume', 0)
            shop_title = product.get('shop_title', 'Loja')
            
            # Determinar destaque
            highlights = []
            if discount > 50:
                highlights.append("🔥 Super Desconto")
            if rating >= 4.5:
                highlights.append("⭐ Alta Avaliação")
            if volume > 1000:
                highlights.append("📈 Mais Vendido")
            if discount > 70:
                highlights.append("⚡ Oferta Relâmpago")
            
            highlight_text = " | ".join(highlights) if highlights else "Promoção Especial"
            
            # Formatação do post
            post_text = f"""**{title}** | {highlight_text}

💵 De: R$ {original_price:.2f} ➜ **R$ {sale_price:.2f}**
🎯 Desconto: {discount:.0f}% | Cashback Disponível
🚚 Frete Grátis | Entrega Rápida
⭐ Avaliação: {rating} | {volume} vendas

🔗 **Link com Desconto (Afiliado):**
{product.get('affiliate_url', '')}

🏪 Loja: {shop_title}

#AliExpress #Promoção #Desconto"""
            
            return post_text
            
        except Exception as e:
            logger.error(f"Erro ao formatar post: {e}")
            return f"Erro ao formatar produto: {e}"
    
    async def post_product(self, product: Dict):
        """Posta produto no canal"""
        try:
            if not self.is_active:
                logger.info("Bot pausado - produto não postado")
                return
            
            post_text = await self.format_post(product)
            image_url = product.get('product_main_image_url', '')
            
            # Postar com imagem se disponível
            if image_url:
                await self.bot.send_photo(
                    chat_id=self.channel_id,
                    photo=image_url,
                    caption=post_text,
                    parse_mode='Markdown'
                )
            else:
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=post_text,
                    parse_mode='Markdown'
                )
            
            # Registrar postagem
            score = await self.product_ai.score_product(product)
            await self.product_ai.record_post(product, score)
            
            logger.info(f"Produto postado: {product.get('product_title', 'Sem título')[:50]}...")
            
        except Exception as e:
            logger.error(f"Erro ao postar produto: {e}")
    
    async def start(self):
        """Inicia o bot"""
        await self.product_ai.init_db()
        logger.info("Bot Telegram iniciado!")
        
        # Limpar updates pendentes para evitar conflitos
        try:
            await self.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook deletado - iniciando polling limpo")
        except Exception as e:
            logger.warning(f"Erro ao deletar webhook: {e}")
        
        # Enviar mensagem de inicialização para o admin
        try:
            await self.bot.send_message(
                self.admin_id,
                "🤖 **Bot AliExpress iniciado!**\n\nDigite /status para ver o painel de controle.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Não foi possível enviar mensagem de inicialização: {e}")
        
        # Iniciar polling
        await self.dp.start_polling(self.bot, skip_updates=True)
    
    async def stop(self):
        """Para o bot"""
        await self.bot.session.close()
        logger.info("Bot Telegram parado!")
