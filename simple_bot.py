import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import re
import random

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

class SimpleAliExpressBot:
    """Bot simples para criar anúncios a partir de links afiliados"""
    
    def __init__(self):
        self.bot = Bot(token=os.getenv('BOT_TOKEN'))
        self.dp = Dispatcher()
        self.channel_id = os.getenv('CHANNEL_ID', '@SJPROMOS')
        self.admin_id = int(os.getenv('ADMIN_USER_ID', '5782277642'))
        
        # Registrar comandos
        self._register_commands()
        
    def _register_commands(self):
        """Registra comandos do bot"""
        
        @self.dp.message(CommandStart())
        async def start_command(message: Message):
            if message.from_user.id != self.admin_id:
                await message.answer("❌ Acesso negado")
                return
                
            await message.answer(
                "🤖 Bot AliExpress Simplificado\n\n"
                "📝 Como usar:\n"
                "1. Envie um link afiliado da AliExpress\n"
                "2. O bot criará um anúncio automático\n"
                "3. Confirme para postar no canal\n\n"
                "💡 Exemplo de link:\n"
                "https://pt.aliexpress.com/item/1005001234567890.html?spm=a2g0o.home.BOT_TELEGRAM"
            )
        
        @self.dp.message(Command("status"))
        async def status_command(message: Message):
            if message.from_user.id != self.admin_id:
                await message.answer("❌ Acesso negado")
                return
                
            await message.answer(
                "🤖 Status do Bot\n\n"
                f"✅ Bot ativo\n"
                f"📺 Canal: {self.channel_id}\n"
                f"👤 Admin: {self.admin_id}\n"
                f"🕐 Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
        
        @self.dp.message()
        async def handle_message(message: Message):
            if message.from_user.id != self.admin_id:
                await message.answer("❌ Acesso negado")
                return
            
            # Verificar se é um link da AliExpress
            if self._is_aliexpress_link(message.text):
                await self._process_affiliate_link(message)
            else:
                await message.answer(
                    "❌ Link inválido\n\n"
                    "📝 Envie um link afiliado da AliExpress válido.\n"
                    "💡 Exemplo: https://pt.aliexpress.com/item/1005001234567890.html?spm=a2g0o.home.BOT_TELEGRAM"
                )
    
    def _is_aliexpress_link(self, text: str) -> bool:
        """Verifica se é um link válido da AliExpress"""
        patterns = [
            r'https?://[a-z]+\.aliexpress\.com/item/\d+\.html',
            r'https?://[a-z]+\.aliexpress\.com/item/\d+',
            r'https?://[a-z]+\.aliexpress\.com/store/product/\d+',
        ]
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    async def _process_affiliate_link(self, message: Message):
        """Processa link afiliado e cria anúncio"""
        try:
            link = message.text.strip()
            
            # Extrair informações do link
            product_info = self._extract_product_info(link)
            
            # Criar anúncio
            announcement = self._create_announcement(product_info, link)
            
            # Mostrar preview
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Postar no Canal", callback_data=f"post_{hash(link)}"),
                    InlineKeyboardButton(text="❌ Cancelar", callback_data="cancel")
                ]
            ])
            
            await message.answer(
                f"📝 Preview do Anúncio:\n\n{announcement}",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Erro ao processar link: {e}")
            await message.answer(f"❌ Erro ao processar link: {e}")
    
    def _extract_product_info(self, link: str) -> dict:
        """Extrai informações do produto do link"""
        # Extrair ID do produto
        product_id_match = re.search(r'/item/(\d+)', link)
        product_id = product_id_match.group(1) if product_id_match else "0000000000"
        
        # Gerar informações baseadas no ID (simulado)
        categories = [
            "Smartphone", "Fone Bluetooth", "Relógio Smart", "Câmera", "Tablet",
            "Notebook", "Mouse", "Teclado", "Carregador", "Cabo USB"
        ]
        
        brands = [
            "Xiaomi", "Samsung", "Huawei", "OnePlus", "Realme",
            "Oppo", "Vivo", "Honor", "Redmi", "Poco"
        ]
        
        # Usar ID para gerar dados consistentes
        random.seed(int(product_id[-6:]))  # Usar últimos 6 dígitos como seed
        
        category = random.choice(categories)
        brand = random.choice(brands)
        
        # Preços simulados baseados na categoria
        base_prices = {
            "Smartphone": (800, 2000),
            "Fone Bluetooth": (50, 300),
            "Relógio Smart": (100, 500),
            "Câmera": (200, 800),
            "Tablet": (300, 1000),
            "Notebook": (1500, 4000),
            "Mouse": (20, 100),
            "Teclado": (50, 200),
            "Carregador": (15, 80),
            "Cabo USB": (10, 50)
        }
        
        min_price, max_price = base_prices.get(category, (50, 500))
        original_price = random.randint(min_price, max_price)
        discount = random.randint(20, 70)
        sale_price = int(original_price * (1 - discount/100))
        
        return {
            'product_id': product_id,
            'title': f"{brand} {category} Premium",
            'original_price': original_price,
            'sale_price': sale_price,
            'discount': discount,
            'category': category,
            'brand': brand,
            'rating': round(random.uniform(4.0, 4.9), 1),
            'sales': random.randint(100, 5000)
        }
    
    def _create_announcement(self, product_info: dict, link: str) -> str:
        """Cria anúncio formatado"""
        title = product_info['title']
        original_price = product_info['original_price']
        sale_price = product_info['sale_price']
        discount = product_info['discount']
        rating = product_info['rating']
        sales = product_info['sales']
        category = product_info['category']
        
        # Emojis baseados na categoria
        category_emojis = {
            "Smartphone": "📱",
            "Fone Bluetooth": "🎧",
            "Relógio Smart": "⌚",
            "Câmera": "📷",
            "Tablet": "📱",
            "Notebook": "💻",
            "Mouse": "🖱️",
            "Teclado": "⌨️",
            "Carregador": "🔌",
            "Cabo USB": "🔌"
        }
        
        emoji = category_emojis.get(category, "🛍️")
        
        # Destaques baseados no desconto
        highlights = []
        if discount > 60:
            highlights.append("🔥 Super Oferta")
        if discount > 50:
            highlights.append("⚡ Desconto Relâmpago")
        if rating > 4.5:
            highlights.append("⭐ Alta Avaliação")
        if sales > 1000:
            highlights.append("📈 Mais Vendido")
        
        highlight_text = " | ".join(highlights) if highlights else "Promoção Especial"
        
        # Criar anúncio
        announcement = f"""{emoji} {title} | {highlight_text}

💵 De: R$ {original_price:.2f} ➜ R$ {sale_price:.2f}
🎯 Desconto: {discount}% | Cashback Disponível
🚚 Frete Grátis | Entrega Rápida
⭐ Avaliação: {rating} | {sales} vendas

🔗 Link com Desconto (Afiliado):
{link}

🏪 Loja Oficial AliExpress

#AliExpress #Promoção #Desconto #{category.replace(' ', '')}"""

        return announcement
    
    async def _handle_callback(self, callback_query: types.CallbackQuery):
        """Manipula callbacks dos botões"""
        if callback_query.from_user.id != self.admin_id:
            await callback_query.answer("❌ Acesso negado", show_alert=True)
            return
        
        data = callback_query.data
        
        if data.startswith("post_"):
            # Postar no canal
            announcement = callback_query.message.text.replace("📝 Preview do Anúncio:\n\n", "")
            
            try:
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=announcement
                )
                
                await callback_query.answer("✅ Anúncio postado no canal!")
                await callback_query.message.edit_text(
                    "✅ Anúncio postado com sucesso no canal!"
                )
                
            except Exception as e:
                logger.error(f"Erro ao postar no canal: {e}")
                await callback_query.answer(f"❌ Erro ao postar: {e}", show_alert=True)
        
        elif data == "cancel":
            await callback_query.answer("❌ Operação cancelada")
            await callback_query.message.edit_text("❌ Operação cancelada")
    
    async def start(self):
        """Inicia o bot"""
        logger.info("Bot AliExpress Simplificado iniciado!")
        
        # Registrar callback handler
        self.dp.callback_query.register(self._handle_callback)
        
        # Enviar mensagem de inicialização
        try:
            await self.bot.send_message(
                self.admin_id,
                "🤖 Bot AliExpress Simplificado iniciado!\n\n"
                "📝 Envie um link afiliado para criar um anúncio."
            )
        except Exception as e:
            logger.warning(f"Não foi possível enviar mensagem de inicialização: {e}")
        
        # Iniciar polling
        await self.dp.start_polling(self.bot)
    
    async def stop(self):
        """Para o bot"""
        await self.bot.session.close()
        logger.info("Bot parado!")

async def main():
    """Função principal"""
    bot = SimpleAliExpressBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário")
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
