import hashlib
import hmac
import time
import urllib.parse
from typing import List, Dict, Optional
import logging
from aiohttp import ClientSession, ClientTimeout
import json

logger = logging.getLogger(__name__)

class AliExpressAPI:
    """Classe para integração robusta com a API da AliExpress"""
    
    def __init__(self, app_key: str, app_secret: str, tracking_id: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.tracking_id = tracking_id
        self.base_url = "https://api-sg.aliexpress.com"
        self.timeout = ClientTimeout(total=30)
        
    def _generate_signature(self, params: Dict[str, str]) -> str:
        """Gera assinatura HMAC-SHA256 para a API"""
        # Ordenar parâmetros
        sorted_params = sorted(params.items())
        
        # Criar string de consulta
        query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        # Gerar assinatura
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        
        return signature
    
    def _build_params(self, method: str, extra_params: Dict = None) -> Dict[str, str]:
        """Constrói parâmetros base para a API"""
        timestamp = str(int(time.time() * 1000))
        
        params = {
            'app_key': self.app_key,
            'method': method,
            'format': 'json',
            'v': '2.0',
            'sign_method': 'sha256',
            'timestamp': timestamp,
            'tracking_id': self.tracking_id
        }
        
        if extra_params:
            params.update(extra_params)
            
        # Gerar assinatura
        params['sign'] = self._generate_signature(params)
        
        return params
    
    async def get_hot_products(self, category_id: str = None, limit: int = 50) -> List[Dict]:
        """Busca produtos em alta usando smartmatch"""
        try:
            extra_params = {
                'fields': 'product_id,product_title,product_url,target_sale_price,target_original_price,commission_rate,shop_title,product_main_image_url,shop_url,volume,rating,review_count,discount',
                'page_size': str(limit),
                'sort': 'SALE_PRICE_ASC',
                'min_commission_rate': '5',
                'platform_product_type': 'ALL',
                'country': 'BR'
            }
            
            if category_id:
                extra_params['category_id'] = category_id
                
            params = self._build_params('aliexpress.affiliate.product.smartmatch', extra_params)
            
            async with ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}/sop/rest", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_products_response(data)
                    else:
                        logger.error(f"Erro na API AliExpress: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Erro ao buscar produtos em alta: {e}")
            return []
    
    async def search_products(self, keywords: str, category_id: str = None, 
                           min_discount: int = 30, limit: int = 50) -> List[Dict]:
        """Busca produtos por palavras-chave"""
        try:
            extra_params = {
                'keywords': keywords,
                'fields': 'product_id,product_title,product_url,target_sale_price,target_original_price,commission_rate,shop_title,product_main_image_url,shop_url,volume,rating,review_count,discount',
                'page_size': str(limit),
                'sort': 'SALE_PRICE_ASC',
                'min_commission_rate': '5',
                'platform_product_type': 'ALL',
                'country': 'BR'
            }
            
            if category_id:
                extra_params['category_id'] = category_id
                
            params = self._build_params('aliexpress.affiliate.product.search', extra_params)
            
            async with ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}/sop/rest", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        products = self._parse_products_response(data)
                        return self._filter_by_discount(products, min_discount)
                    else:
                        logger.error(f"Erro na busca de produtos: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Erro ao buscar produtos: {e}")
            return []
    
    async def get_product_details(self, product_id: str) -> Optional[Dict]:
        """Obtém detalhes específicos de um produto"""
        try:
            extra_params = {
                'product_ids': product_id,
                'fields': 'product_id,product_title,product_url,target_sale_price,target_original_price,commission_rate,shop_title,product_main_image_url,shop_url,volume,rating,review_count,discount,product_property_list'
            }
            
            params = self._build_params('aliexpress.affiliate.product.detail', extra_params)
            
            async with ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}/sop/rest", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        products = self._parse_products_response(data)
                        return products[0] if products else None
                    else:
                        logger.error(f"Erro ao obter detalhes do produto: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Erro ao obter detalhes do produto: {e}")
            return None
    
    def _parse_products_response(self, data: Dict) -> List[Dict]:
        """Processa resposta da API e extrai produtos"""
        products = []
        
        try:
            # Tentar diferentes estruturas de resposta
            response_data = None
            
            if 'aliexpress_affiliate_product_smartmatch_response' in data:
                response_data = data['aliexpress_affiliate_product_smartmatch_response']
            elif 'aliexpress_affiliate_product_search_response' in data:
                response_data = data['aliexpress_affiliate_product_search_response']
            elif 'aliexpress_affiliate_product_detail_response' in data:
                response_data = data['aliexpress_affiliate_product_detail_response']
            
            if response_data and 'result' in response_data:
                products_data = response_data['result'].get('products', [])
                
                for product in products_data:
                    processed_product = self._process_product(product)
                    if processed_product:
                        products.append(processed_product)
                        
        except Exception as e:
            logger.error(f"Erro ao processar resposta da API: {e}")
            
        return products
    
    def _process_product(self, product: Dict) -> Optional[Dict]:
        """Processa dados de um produto individual"""
        try:
            # Extrair dados básicos
            product_id = product.get('product_id', '')
            title = product.get('product_title', '')
            original_price = float(product.get('target_original_price', 0))
            sale_price = float(product.get('target_sale_price', 0))
            
            if not product_id or not title or original_price <= 0 or sale_price <= 0:
                return None
            
            # Calcular desconto
            discount = ((original_price - sale_price) / original_price) * 100
            
            # Processar produto
            processed = {
                'product_id': product_id,
                'product_title': title,
                'target_original_price': original_price,
                'target_sale_price': sale_price,
                'calculated_discount': discount,
                'commission_rate': float(product.get('commission_rate', 0)),
                'shop_title': product.get('shop_title', ''),
                'product_main_image_url': product.get('product_main_image_url', ''),
                'product_url': product.get('product_url', ''),
                'shop_url': product.get('shop_url', ''),
                'volume': int(product.get('volume', 0)),
                'rating': float(product.get('rating', 0)),
                'review_count': int(product.get('review_count', 0)),
                'affiliate_url': self._generate_affiliate_url(product.get('product_url', '')),
                'country': 'BR'
            }
            
            return processed
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Erro ao processar produto: {e}")
            return None
    
    def _filter_by_discount(self, products: List[Dict], min_discount: int) -> List[Dict]:
        """Filtra produtos por desconto mínimo"""
        return [p for p in products if p.get('calculated_discount', 0) >= min_discount]
    
    def _generate_affiliate_url(self, product_url: str) -> str:
        """Gera URL afiliado com tracking ID"""
        if not product_url:
            return ""
        
        # Adicionar parâmetros de afiliado
        separator = "&" if "?" in product_url else "?"
        affiliate_url = f"{product_url}{separator}tracking_id={self.tracking_id}&aff_platform=api"
        
        return affiliate_url
    
    async def get_categories(self) -> List[Dict]:
        """Obtém lista de categorias disponíveis"""
        try:
            params = self._build_params('aliexpress.affiliate.category.get')
            
            async with ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}/sop/rest", params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_categories_response(data)
                    else:
                        logger.error(f"Erro ao obter categorias: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Erro ao obter categorias: {e}")
            return []
    
    def _parse_categories_response(self, data: Dict) -> List[Dict]:
        """Processa resposta de categorias"""
        categories = []
        
        try:
            if 'aliexpress_affiliate_category_get_response' in data:
                response_data = data['aliexpress_affiliate_category_get_response']
                if 'result' in response_data:
                    categories_data = response_data['result'].get('categories', [])
                    
                    for category in categories_data:
                        categories.append({
                            'category_id': category.get('category_id', ''),
                            'category_name': category.get('category_name', ''),
                            'parent_category_id': category.get('parent_category_id', '')
                        })
                        
        except Exception as e:
            logger.error(f"Erro ao processar categorias: {e}")
            
        return categories
    
    async def test_connection(self) -> bool:
        """Testa conexão com a API"""
        try:
            # Teste simples com busca de produtos
            products = await self.get_hot_products(limit=1)
            return len(products) > 0
        except Exception as e:
            logger.error(f"Erro no teste de conexão: {e}")
            return False
