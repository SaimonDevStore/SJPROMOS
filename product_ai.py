import asyncio
import aiosqlite
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import random
import math

logger = logging.getLogger(__name__)

class ProductAI:
    """Sistema de IA híbrida para seleção inteligente de produtos"""
    
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.weights = {
            'discount': 0.25,
            'rating': 0.20,
            'volume': 0.15,
            'commission': 0.15,
            'trending': 0.10,
            'historical': 0.10,
            'freshness': 0.05
        }
        
    async def init_db(self):
        """Inicializa banco de dados com tabelas necessárias"""
        async with aiosqlite.connect(self.db_path) as db:
            # Tabela de produtos postados
            await db.execute('''
                CREATE TABLE IF NOT EXISTS posted_products (
                    product_id TEXT PRIMARY KEY,
                    posted_at TIMESTAMP,
                    clicks INTEGER DEFAULT 0,
                    conversion_score REAL DEFAULT 0.0,
                    engagement_score REAL DEFAULT 0.0,
                    last_click_at TIMESTAMP,
                    category TEXT,
                    discount REAL,
                    rating REAL,
                    volume INTEGER
                )
            ''')
            
            # Tabela de histórico de ações
            await db.execute('''
                CREATE TABLE IF NOT EXISTS product_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT,
                    action TEXT,
                    timestamp TIMESTAMP,
                    metadata TEXT,
                    score_impact REAL DEFAULT 0.0
                )
            ''')
            
            # Tabela de métricas por categoria
            await db.execute('''
                CREATE TABLE IF NOT EXISTS category_metrics (
                    category TEXT PRIMARY KEY,
                    avg_conversion REAL DEFAULT 0.0,
                    total_posts INTEGER DEFAULT 0,
                    total_clicks INTEGER DEFAULT 0,
                    last_updated TIMESTAMP
                )
            ''')
            
            # Tabela de produtos em tendência
            await db.execute('''
                CREATE TABLE IF NOT EXISTS trending_products (
                    product_id TEXT PRIMARY KEY,
                    trend_score REAL DEFAULT 0.0,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    click_velocity REAL DEFAULT 0.0
                )
            ''')
            
            # Índices para performance
            await db.execute('CREATE INDEX IF NOT EXISTS idx_posted_at ON posted_products(posted_at)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_category ON posted_products(category)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_trending_score ON trending_products(trend_score)')
            
            await db.commit()
    
    async def score_product(self, product: Dict) -> float:
        """Calcula score híbrido do produto (0-100)"""
        try:
            scores = {}
            
            # 1. Score de desconto
            scores['discount'] = self._calculate_discount_score(product)
            
            # 2. Score de avaliação
            scores['rating'] = self._calculate_rating_score(product)
            
            # 3. Score de volume de vendas
            scores['volume'] = self._calculate_volume_score(product)
            
            # 4. Score de comissão
            scores['commission'] = self._calculate_commission_score(product)
            
            # 5. Score de tendência
            scores['trending'] = await self._calculate_trending_score(product)
            
            # 6. Score histórico
            scores['historical'] = await self._get_historical_score(product.get('product_id', ''))
            
            # 7. Score de frescor (produtos novos têm vantagem)
            scores['freshness'] = await self._calculate_freshness_score(product)
            
            # Calcular score final ponderado
            final_score = sum(scores[key] * self.weights[key] for key in scores)
            
            # Aplicar boost para produtos premium
            final_score = self._apply_premium_boost(product, final_score)
            
            # Normalizar para 0-100
            final_score = min(max(final_score, 0), 100)
            
            logger.debug(f"Score do produto {product.get('product_id', '')}: {final_score:.2f} - {scores}")
            
            return final_score
            
        except Exception as e:
            logger.error(f"Erro ao calcular score do produto: {e}")
            return 0.0
    
    def _calculate_discount_score(self, product: Dict) -> float:
        """Calcula score baseado no desconto"""
        discount = product.get('calculated_discount', 0)
        
        if discount >= 70:
            return 100
        elif discount >= 50:
            return 80
        elif discount >= 30:
            return 60
        elif discount >= 20:
            return 40
        elif discount >= 10:
            return 20
        else:
            return 0
    
    def _calculate_rating_score(self, product: Dict) -> float:
        """Calcula score baseado na avaliação"""
        rating = float(product.get('rating', 0))
        review_count = int(product.get('review_count', 0))
        
        # Score baseado na nota
        if rating >= 4.8:
            base_score = 100
        elif rating >= 4.5:
            base_score = 80
        elif rating >= 4.0:
            base_score = 60
        elif rating >= 3.5:
            base_score = 40
        elif rating >= 3.0:
            base_score = 20
        else:
            base_score = 0
        
        # Boost baseado no número de avaliações
        if review_count >= 1000:
            boost = 20
        elif review_count >= 500:
            boost = 15
        elif review_count >= 100:
            boost = 10
        elif review_count >= 50:
            boost = 5
        else:
            boost = 0
        
        return min(base_score + boost, 100)
    
    def _calculate_volume_score(self, product: Dict) -> float:
        """Calcula score baseado no volume de vendas"""
        volume = int(product.get('volume', 0))
        
        if volume >= 10000:
            return 100
        elif volume >= 5000:
            return 80
        elif volume >= 1000:
            return 60
        elif volume >= 500:
            return 40
        elif volume >= 100:
            return 20
        else:
            return 0
    
    def _calculate_commission_score(self, product: Dict) -> float:
        """Calcula score baseado na comissão"""
        commission = float(product.get('commission_rate', 0))
        
        if commission >= 10:
            return 100
        elif commission >= 8:
            return 80
        elif commission >= 6:
            return 60
        elif commission >= 4:
            return 40
        elif commission >= 2:
            return 20
        else:
            return 0
    
    async def _calculate_trending_score(self, product: Dict) -> float:
        """Calcula score de tendência baseado em dados históricos"""
        try:
            product_id = product.get('product_id', '')
            
            async with aiosqlite.connect(self.db_path) as db:
                # Verificar se está na tabela de tendências
                cursor = await db.execute(
                    'SELECT trend_score, click_velocity FROM trending_products WHERE product_id = ?',
                    (product_id,)
                )
                result = await cursor.fetchone()
                
                if result:
                    trend_score, click_velocity = result
                    return min(trend_score + click_velocity, 100)
                
                # Calcular tendência baseada em cliques recentes
                cursor = await db.execute('''
                    SELECT COUNT(*) as clicks, MAX(timestamp) as last_click
                    FROM product_history 
                    WHERE product_id = ? AND action = 'click' 
                    AND timestamp > datetime('now', '-24 hours')
                ''', (product_id,))
                
                result = await cursor.fetchone()
                if result:
                    clicks, last_click = result
                    if clicks > 0:
                        # Score baseado em cliques nas últimas 24h
                        return min(clicks * 10, 100)
                
                return 0
                
        except Exception as e:
            logger.error(f"Erro ao calcular score de tendência: {e}")
            return 0
    
    async def _get_historical_score(self, product_id: str) -> float:
        """Obtém score baseado no histórico de performance"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    SELECT conversion_score, engagement_score, clicks
                    FROM posted_products 
                    WHERE product_id = ?
                ''', (product_id,))
                
                result = await cursor.fetchone()
                if result:
                    conversion_score, engagement_score, clicks = result
                    
                    # Score histórico baseado em performance anterior
                    historical_score = (conversion_score + engagement_score) / 2
                    
                    # Boost para produtos com muitos cliques
                    if clicks > 100:
                        historical_score += 20
                    elif clicks > 50:
                        historical_score += 10
                    elif clicks > 10:
                        historical_score += 5
                    
                    return min(historical_score, 100)
                
                return 0
                
        except Exception as e:
            logger.error(f"Erro ao obter score histórico: {e}")
            return 0
    
    async def _calculate_freshness_score(self, product: Dict) -> float:
        """Calcula score de frescor (produtos novos têm vantagem)"""
        try:
            product_id = product.get('product_id', '')
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    'SELECT posted_at FROM posted_products WHERE product_id = ?',
                    (product_id,)
                )
                result = await cursor.fetchone()
                
                if not result:
                    # Produto nunca foi postado - score alto
                    return 50
                
                posted_at = datetime.fromisoformat(result[0])
                days_since_post = (datetime.now() - posted_at).days
                
                # Score decresce com o tempo
                if days_since_post == 0:
                    return 0  # Postado hoje
                elif days_since_post <= 1:
                    return 10
                elif days_since_post <= 7:
                    return 20
                elif days_since_post <= 30:
                    return 30
                else:
                    return 40
                    
        except Exception as e:
            logger.error(f"Erro ao calcular score de frescor: {e}")
            return 0
    
    def _apply_premium_boost(self, product: Dict, base_score: float) -> float:
        """Aplica boost para produtos premium"""
        boost = 0
        
        # Boost para produtos com múltiplos critérios positivos
        rating = float(product.get('rating', 0))
        volume = int(product.get('volume', 0))
        discount = product.get('calculated_discount', 0)
        
        if rating >= 4.5 and volume >= 1000 and discount >= 30:
            boost += 15  # Produto premium
        elif rating >= 4.0 and volume >= 500 and discount >= 20:
            boost += 10  # Produto bom
        elif rating >= 3.5 and volume >= 100:
            boost += 5   # Produto decente
        
        return min(base_score + boost, 100)
    
    async def can_post_product(self, product_id: str, force_post: bool = False) -> bool:
        """Verifica se o produto pode ser postado (anti-repetição inteligente)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    SELECT posted_at, conversion_score, clicks
                    FROM posted_products 
                    WHERE product_id = ?
                ''', (product_id,))
                
                result = await cursor.fetchone()
                
                if not result:
                    return True  # Produto nunca foi postado
                
                posted_at, conversion_score, clicks = result
                posted_datetime = datetime.fromisoformat(posted_at)
                hours_since_post = (datetime.now() - posted_datetime).total_seconds() / 3600
                
                # Regra básica: não repetir dentro de 48 horas
                if hours_since_post < 48:
                    # Exceção: produtos com alta performance podem ser repetidos antes
                    if force_post or (conversion_score > 80 and clicks > 50):
                        logger.info(f"Repetindo produto de alta performance: {product_id}")
                        return True
                    return False
                
                # Produtos com baixa performance têm intervalo maior
                if conversion_score < 30 and hours_since_post < 72:
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Erro ao verificar anti-repetição: {e}")
            return True
    
    async def record_post(self, product: Dict, score: float):
        """Registra postagem do produto"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO posted_products 
                    (product_id, posted_at, conversion_score, category, discount, rating, volume) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product.get('product_id', ''),
                    datetime.now().isoformat(),
                    score,
                    self._extract_category(product),
                    product.get('calculated_discount', 0),
                    product.get('rating', 0),
                    product.get('volume', 0)
                ))
                
                # Registrar no histórico
                await db.execute('''
                    INSERT INTO product_history 
                    (product_id, action, timestamp, score_impact) 
                    VALUES (?, ?, ?, ?)
                ''', (
                    product.get('product_id', ''),
                    'post',
                    datetime.now().isoformat(),
                    score
                ))
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Erro ao registrar post: {e}")
    
    async def record_click(self, product_id: str):
        """Registra clique no produto"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Atualizar contador de cliques
                await db.execute('''
                    UPDATE posted_products 
                    SET clicks = clicks + 1, last_click_at = ?
                    WHERE product_id = ?
                ''', (datetime.now().isoformat(), product_id))
                
                # Registrar no histórico
                await db.execute('''
                    INSERT INTO product_history 
                    (product_id, action, timestamp) 
                    VALUES (?, ?, ?)
                ''', (product_id, 'click', datetime.now().isoformat()))
                
                # Atualizar score de tendência
                await self._update_trending_score(product_id)
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Erro ao registrar clique: {e}")
    
    async def _update_trending_score(self, product_id: str):
        """Atualiza score de tendência do produto"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Calcular velocidade de cliques (cliques por hora)
                cursor = await db.execute('''
                    SELECT COUNT(*) as clicks
                    FROM product_history 
                    WHERE product_id = ? AND action = 'click' 
                    AND timestamp > datetime('now', '-1 hour')
                ''', (product_id,))
                
                result = await cursor.fetchone()
                click_velocity = result[0] if result else 0
                
                # Atualizar ou inserir na tabela de tendências
                await db.execute('''
                    INSERT OR REPLACE INTO trending_products 
                    (product_id, trend_score, click_velocity, last_seen) 
                    VALUES (?, ?, ?, ?)
                ''', (
                    product_id,
                    min(click_velocity * 10, 100),
                    click_velocity,
                    datetime.now().isoformat()
                ))
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Erro ao atualizar score de tendência: {e}")
    
    def _extract_category(self, product: Dict) -> str:
        """Extrai categoria do produto (simplificado)"""
        title = product.get('product_title', '').lower()
        
        # Categorias básicas baseadas no título
        if any(word in title for word in ['phone', 'celular', 'smartphone']):
            return 'electronics'
        elif any(word in title for word in ['clothes', 'roupa', 'camiseta']):
            return 'clothing'
        elif any(word in title for word in ['home', 'casa', 'decoration']):
            return 'home'
        elif any(word in title for word in ['beauty', 'cosmetic', 'makeup']):
            return 'beauty'
        else:
            return 'general'
    
    async def get_top_products(self, products: List[Dict], limit: int = 25) -> List[Dict]:
        """Seleciona os melhores produtos baseado no score híbrido"""
        try:
            # Filtrar produtos válidos
            valid_products = []
            for product in products:
                if await self.can_post_product(product.get('product_id', '')):
                    score = await self.score_product(product)
                    valid_products.append((product, score))
            
            # Ordenar por score
            valid_products.sort(key=lambda x: x[1], reverse=True)
            
            # Selecionar top produtos
            selected = valid_products[:limit]
            
            logger.info(f"Selecionados {len(selected)} produtos de {len(products)} disponíveis")
            
            return [product for product, score in selected]
            
        except Exception as e:
            logger.error(f"Erro ao selecionar top produtos: {e}")
            return products[:limit] if products else []
    
    async def get_statistics(self) -> Dict:
        """Obtém estatísticas do sistema de IA"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                stats = {}
                
                # Total de produtos postados
                cursor = await db.execute('SELECT COUNT(*) FROM posted_products')
                stats['total_posts'] = (await cursor.fetchone())[0]
                
                # Total de cliques
                cursor = await db.execute('SELECT SUM(clicks) FROM posted_products')
                stats['total_clicks'] = (await cursor.fetchone())[0] or 0
                
                # Produtos mais clicados
                cursor = await db.execute('''
                    SELECT product_title, clicks 
                    FROM posted_products 
                    ORDER BY clicks DESC 
                    LIMIT 5
                ''')
                stats['top_products'] = await cursor.fetchall()
                
                # Score médio
                cursor = await db.execute('SELECT AVG(conversion_score) FROM posted_products')
                stats['avg_score'] = (await cursor.fetchone())[0] or 0
                
                return stats
                
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {}
