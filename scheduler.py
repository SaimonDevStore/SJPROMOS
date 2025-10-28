import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from aliexpress_api import AliExpressAPI
from product_ai import ProductAI
from telegram_bot import TelegramBot

logger = logging.getLogger(__name__)

class PostingScheduler:
    """Sistema de agendamento inteligente para postagens automáticas"""
    
    def __init__(self, config, telegram_bot: TelegramBot):
        self.config = config
        self.telegram_bot = telegram_bot
        self.scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
        self.timezone = pytz.timezone(config.TIMEZONE)
        
        # Inicializar componentes
        self.aliexpress_api = AliExpressAPI(
            config.APP_KEY, 
            config.APP_SECRET, 
            config.TRACKING_ID
        )
        self.product_ai = ProductAI()
        
        # Configurações de postagem
        self.current_hour_posts = 0
        self.hourly_target = 0
        self.posted_this_hour = []
        
        # Categorias e palavras-chave para busca
        self.search_categories = [
            "electronics", "smartphone", "phone", "laptop", "tablet",
            "clothing", "fashion", "shoes", "bags", "accessories",
            "home", "kitchen", "decoration", "furniture", "garden",
            "beauty", "cosmetics", "skincare", "makeup", "health",
            "sports", "fitness", "outdoor", "camping", "automotive",
            "toys", "games", "kids", "baby", "pet"
        ]
        
        # Horários de pico (probabilidade maior de posts)
        self.peak_hours = [12, 13, 14, 20, 21]  # 12h-14h e 20h-21h
        
    def start(self):
        """Inicia o sistema de agendamento"""
        try:
            # Agendar verificação a cada hora
            self.scheduler.add_job(
                self._hourly_planning,
                CronTrigger(minute=0),  # A cada hora
                id='hourly_planning',
                replace_existing=True,
                max_instances=1
            )
            
            # Agendar limpeza de cache a cada 6 horas
            self.scheduler.add_job(
                self._cleanup_cache,
                CronTrigger(hour='*/6', minute=0),
                id='cleanup_cache',
                replace_existing=True
            )
            
            # Agendar backup de dados diário
            self.scheduler.add_job(
                self._daily_backup,
                CronTrigger(hour=2, minute=0),  # 2h da manhã
                id='daily_backup',
                replace_existing=True
            )
            
            # Iniciar scheduler
            self.scheduler.start()
            logger.info("Sistema de agendamento iniciado!")
            
            # Planejar primeira hora se estiver no horário de funcionamento
            asyncio.create_task(self._check_and_start_first_hour())
            
        except Exception as e:
            logger.error(f"Erro ao iniciar agendador: {e}")
    
    async def _check_and_start_first_hour(self):
        """Verifica se deve iniciar postagens imediatamente"""
        try:
            current_time = datetime.now(self.timezone)
            start_hour = int(self.config.START_TIME.split(':')[0])
            end_hour = int(self.config.END_TIME.split(':')[0])
            
            if start_hour <= current_time.hour < end_hour:
                logger.info("Iniciando planejamento da primeira hora")
                await self._hourly_planning()
                
        except Exception as e:
            logger.error(f"Erro ao verificar primeira hora: {e}")
    
    async def _hourly_planning(self):
        """Planejamento principal executado a cada hora"""
        try:
            current_time = datetime.now(self.timezone)
            start_hour = int(self.config.START_TIME.split(':')[0])
            end_hour = int(self.config.END_TIME.split(':')[0])
            
            # Verificar se está no horário de funcionamento
            if not (start_hour <= current_time.hour < end_hour):
                logger.info(f"Fora do horário de funcionamento: {current_time.hour}h")
                return
            
            # Calcular número de posts para esta hora
            self.hourly_target = self._calculate_hourly_posts(current_time.hour)
            self.current_hour_posts = 0
            self.posted_this_hour = []
            
            logger.info(f"Iniciando planejamento para {current_time.hour}h - Meta: {self.hourly_target} posts")
            
            # Buscar produtos
            products = await self._fetch_products_for_hour()
            
            if not products:
                logger.warning("Nenhum produto encontrado para esta hora!")
                return
            
            # Selecionar produtos usando IA
            selected_products = await self.product_ai.get_top_products(products, self.hourly_target)
            
            if len(selected_products) < self.hourly_target:
                logger.warning(f"Apenas {len(selected_products)} produtos válidos encontrados de {self.hourly_target} necessários")
            
            # Distribuir posts ao longo da hora
            await self._schedule_posts_for_hour(selected_products, current_time)
            
        except Exception as e:
            logger.error(f"Erro no planejamento horário: {e}")
    
    def _calculate_hourly_posts(self, hour: int) -> int:
        """Calcula número de posts para a hora atual"""
        # Base aleatória dentro do intervalo
        base_posts = random.randint(self.config.POST_MIN_PER_HOUR, self.config.POST_MAX_PER_HOUR)
        
        # Boost para horários de pico
        if hour in self.peak_hours:
            boost = random.randint(2, 5)
            base_posts = min(base_posts + boost, self.config.POST_MAX_PER_HOUR)
        
        # Variação aleatória para simular comportamento humano
        variation = random.randint(-2, 2)
        final_posts = max(base_posts + variation, self.config.POST_MIN_PER_HOUR)
        
        return min(final_posts, self.config.POST_MAX_PER_HOUR)
    
    async def _fetch_products_for_hour(self) -> List[Dict]:
        """Busca produtos para a hora atual"""
        try:
            all_products = []
            
            # Buscar produtos em alta
            hot_products = await self.aliexpress_api.get_hot_products(limit=30)
            all_products.extend(hot_products)
            
            # Buscar produtos por categorias aleatórias
            random_categories = random.sample(self.search_categories, 3)
            for category in random_categories:
                try:
                    category_products = await self.aliexpress_api.search_products(
                        keywords=category, 
                        min_discount=30, 
                        limit=20
                    )
                    all_products.extend(category_products)
                except Exception as e:
                    logger.warning(f"Erro ao buscar categoria {category}: {e}")
                    continue
            
            # Remover duplicatas baseado no product_id
            unique_products = {}
            for product in all_products:
                product_id = product.get('product_id', '')
                if product_id and product_id not in unique_products:
                    unique_products[product_id] = product
            
            final_products = list(unique_products.values())
            logger.info(f"Encontrados {len(final_products)} produtos únicos")
            
            return final_products
            
        except Exception as e:
            logger.error(f"Erro ao buscar produtos: {e}")
            return []
    
    async def _schedule_posts_for_hour(self, products: List[Dict], current_time: datetime):
        """Agenda posts ao longo da hora"""
        try:
            if not products:
                return
            
            # Calcular distribuição temporal
            posts_count = len(products)
            hour_start = current_time.replace(minute=0, second=0, microsecond=0)
            
            for i, product in enumerate(products):
                # Calcular delay aleatório dentro da hora
                delay_minutes = random.randint(0, 59)
                delay_seconds = delay_minutes * 60 + random.randint(0, 59)
                
                # Adicionar jitter para evitar padrões
                jitter = random.randint(-30, 30)  # ±30 segundos
                final_delay = max(0, delay_seconds + jitter)
                
                # Calcular horário exato
                post_time = hour_start + timedelta(seconds=final_delay)
                
                # Agendar post
                job_id = f'post_{product.get("product_id", i)}_{current_time.hour}_{i}'
                
                self.scheduler.add_job(
                    self._execute_post,
                    DateTrigger(run_date=post_time),
                    args=[product],
                    id=job_id,
                    replace_existing=True
                )
                
                logger.info(f"Post agendado para {post_time.strftime('%H:%M:%S')}: {product.get('product_title', 'Sem título')[:50]}...")
            
        except Exception as e:
            logger.error(f"Erro ao agendar posts: {e}")
    
    async def _execute_post(self, product: Dict):
        """Executa postagem do produto"""
        try:
            # Verificar se o bot está ativo
            if not self.telegram_bot.is_active:
                logger.info("Bot pausado - post cancelado")
                return
            
            # Verificar anti-repetição final
            product_id = product.get('product_id', '')
            if product_id in self.posted_this_hour:
                logger.info(f"Produto {product_id} já postado nesta hora - cancelando")
                return
            
            # Executar postagem
            await self.telegram_bot.post_product(product)
            
            # Registrar na hora atual
            self.posted_this_hour.append(product_id)
            self.current_hour_posts += 1
            
            logger.info(f"Post executado ({self.current_hour_posts}/{self.hourly_target}): {product.get('product_title', 'Sem título')[:50]}...")
            
        except Exception as e:
            logger.error(f"Erro ao executar post: {e}")
    
    async def _cleanup_cache(self):
        """Limpeza periódica de cache e dados antigos"""
        try:
            logger.info("Executando limpeza de cache...")
            
            # Limpar produtos antigos da tabela de tendências
            async with self.product_ai.db_path as db:
                await db.execute('''
                    DELETE FROM trending_products 
                    WHERE last_seen < datetime('now', '-7 days')
                ''')
                
                await db.execute('''
                    DELETE FROM product_history 
                    WHERE timestamp < datetime('now', '-30 days')
                ''')
                
                await db.commit()
            
            logger.info("Limpeza de cache concluída")
            
        except Exception as e:
            logger.error(f"Erro na limpeza de cache: {e}")
    
    async def _daily_backup(self):
        """Backup diário dos dados"""
        try:
            logger.info("Executando backup diário...")
            
            # Aqui você pode implementar backup para cloud storage
            # Por enquanto, apenas log
            stats = await self.product_ai.get_statistics()
            logger.info(f"Backup diário - Stats: {stats}")
            
        except Exception as e:
            logger.error(f"Erro no backup diário: {e}")
    
    async def force_post_now(self, product: Dict):
        """Força postagem imediata (para comandos administrativos)"""
        try:
            await self._execute_post(product)
        except Exception as e:
            logger.error(f"Erro na postagem forçada: {e}")
    
    async def get_scheduler_status(self) -> Dict:
        """Obtém status do agendador"""
        try:
            jobs = self.scheduler.get_jobs()
            
            status = {
                'scheduler_running': self.scheduler.running,
                'total_jobs': len(jobs),
                'current_hour_posts': self.current_hour_posts,
                'hourly_target': self.hourly_target,
                'next_job': None
            }
            
            if jobs:
                next_job = min(jobs, key=lambda x: x.next_run_time)
                status['next_job'] = {
                    'id': next_job.id,
                    'next_run': next_job.next_run_time.isoformat() if next_job.next_run_time else None
                }
            
            return status
            
        except Exception as e:
            logger.error(f"Erro ao obter status do agendador: {e}")
            return {}
    
    def stop(self):
        """Para o agendador"""
        try:
            self.scheduler.shutdown()
            logger.info("Sistema de agendamento parado!")
        except Exception as e:
            logger.error(f"Erro ao parar agendador: {e}")
    
    async def adjust_schedule(self, new_min: int, new_max: int):
        """Ajusta configurações de agendamento"""
        try:
            self.config.POST_MIN_PER_HOUR = new_min
            self.config.POST_MAX_PER_HOUR = new_max
            
            logger.info(f"Configurações de agendamento ajustadas: {new_min}-{new_max} posts/hora")
            
        except Exception as e:
            logger.error(f"Erro ao ajustar agendamento: {e}")
    
    async def emergency_stop(self):
        """Para todas as postagens imediatamente"""
        try:
            # Cancelar todos os jobs de postagem
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                if job.id.startswith('post_'):
                    job.remove()
            
            logger.info("Parada de emergência executada - todos os posts cancelados")
            
        except Exception as e:
            logger.error(f"Erro na parada de emergência: {e}")
    
    async def get_hourly_stats(self) -> Dict:
        """Obtém estatísticas da hora atual"""
        try:
            current_time = datetime.now(self.timezone)
            
            stats = {
                'current_hour': current_time.hour,
                'target_posts': self.hourly_target,
                'actual_posts': self.current_hour_posts,
                'posts_remaining': max(0, self.hourly_target - self.current_hour_posts),
                'is_peak_hour': current_time.hour in self.peak_hours,
                'time_remaining_minutes': 60 - current_time.minute
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas horárias: {e}")
            return {}
