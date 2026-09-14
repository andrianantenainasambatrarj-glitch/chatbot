import base64
import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path
from PIL import Image
import io

logger = logging.getLogger(__name__)

VISION_PROMPT_BASE = """Tu es un expert en analyse technique de trading avec 20 ans d'expérience.

Analyse cette image de graphique de trading en détail. Décris:

1. TENDANCE GÉNÉRALE: haussière, baissière, latérale? Force de la tendance?
2. STRUCTURES VISIBLES: supports, résistances, canaux, triangles, drapeaux, tête-épaules, double top/bottom, etc.
3. BOUGIES NOTABLES: marteaux, doji, englobantes, étoiles, etc.
4. INDICATEURS SI VISIBLES: moyennes mobiles, RSI, MACD, volumes
5. NIVEAUX CLÉS: prix importants à surveiller
6. PATTERN PRINCIPAL détecté

Sois très précis et technique. Utilise le vocabulaire du trading professionnel.
Réponds en JSON avec cette structure:
{
  "description": "description détaillée de ce que tu vois",
  "trend": "haussier|baissier|lateral|indecis",
  "patterns_detected": ["liste des patterns"],
  "support_levels": ["niveaux support"],
  "resistance_levels": ["niveaux résistance"],
  "indicators": ["indicateurs visibles"],
  "confidence": 0.0-1.0,
  "key_observations": "observations clés"
}
"""

def build_vision_prompt(style_addition: str = "") -> str:
    if style_addition:
        return VISION_PROMPT_BASE + "\n\n" + style_addition
    return VISION_PROMPT_BASE

# Keep for backward compat
VISION_PROMPT = VISION_PROMPT_BASE

class VisionService:
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.google_key = os.getenv("GOOGLE_API_KEY")
        
        self.available_providers = []
        if self.openai_key:
            self.available_providers.append("openai")
        if self.anthropic_key:
            self.available_providers.append("anthropic")
        if self.google_key:
            self.available_providers.append("google")
        
        logger.info(f"Vision providers available: {self.available_providers}")

    def _encode_image(self, image_path: Path) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def _analyze_with_openai(self, image_path: Path, style_prompt: str = "") -> Optional[Dict[str, Any]]:
        if not self.openai_key:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            
            base64_image = self._encode_image(image_path)
            prompt = build_vision_prompt(style_prompt)
            
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1500,
                temperature=0.2
            )
            
            content = response.choices[0].message.content
            return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"OpenAI vision failed: {e}")
            return None

    def _analyze_with_anthropic(self, image_path: Path, style_prompt: str = "") -> Optional[Dict[str, Any]]:
        if not self.anthropic_key:
            return None
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.anthropic_key)
            
            # Detect media type
            ext = image_path.suffix.lower()
            media_type = "image/jpeg"
            if ext == ".png":
                media_type = "image/png"
            elif ext == ".webp":
                media_type = "image/webp"
            elif ext == ".gif":
                media_type = "image/gif"
            
            base64_image = self._encode_image(image_path)
            prompt = build_vision_prompt(style_prompt)
            
            response = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=1500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": base64_image
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            
            content = response.content[0].text
            return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"Anthropic vision failed: {e}")
            return None

    def _analyze_with_google(self, image_path: Path, style_prompt: str = "") -> Optional[Dict[str, Any]]:
        if not self.google_key:
            return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.google_key)
            model = genai.GenerativeModel(os.getenv("GOOGLE_MODEL", "gemini-1.5-flash"))
            
            img = Image.open(image_path)
            prompt = build_vision_prompt(style_prompt)
            
            response = model.generate_content([prompt, img])
            content = response.text
            return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"Google vision failed: {e}")
            return None

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        import json
        import re
        
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        
        # Try direct JSON parse
        try:
            parsed = json.loads(content)
            return parsed
        except:
            # Try to find JSON object
            try:
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end != -1:
                    json_str = content[start:end]
                    parsed = json.loads(json_str)
                    return parsed
            except:
                pass
        
        # Fallback: create structured response from text
        logger.warning("Failed to parse JSON, using text fallback")
        trend = "indecis"
        if "haussier" in content.lower() or "bullish" in content.lower() or "hausse" in content.lower():
            trend = "haussier"
        elif "baissier" in content.lower() or "bearish" in content.lower() or "baisse" in content.lower():
            trend = "baissier"
        elif "lateral" in content.lower() or "range" in content.lower():
            trend = "lateral"
        
        return {
            "description": content[:1000],
            "trend": trend,
            "patterns_detected": ["analyse textuelle"],
            "support_levels": [],
            "resistance_levels": [],
            "indicators": [],
            "confidence": 0.6,
            "key_observations": content[:500]
        }

    def _analyze_local_fallback(self, image_path: Path) -> Dict[str, Any]:
        """Analyse locale sans LLM - basique mais fonctionnelle"""
        try:
            img = Image.open(image_path)
            width, height = img.size
            
            # Analyse basique de l'image
            # Convert to grayscale and check brightness distribution as proxy
            gray = img.convert('L')
            # Simple heuristic: we can't do real TA without LLM
            
            return {
                "description": f"Image de graphique {width}x{height} analysée en mode local (sans API LLM). Pour une analyse approfondie, configurez OPENAI_API_KEY, ANTHROPIC_API_KEY ou GOOGLE_API_KEY. L'image semble être un graphique de trading nécessitant une analyse visuelle experte.",
                "trend": "indecis",
                "patterns_detected": ["analyse locale - API LLM requise pour détection précise"],
                "support_levels": ["Niveau support à identifier manuellement"],
                "resistance_levels": ["Niveau résistance à identifier manuellement"],
                "indicators": ["Analyse locale - pas d'indicateurs détectés automatiquement"],
                "confidence": 0.3,
                "key_observations": f"Image {width}x{height} - Mode local activé. Ajoutez une clé API pour débloquer l'analyse IA complète avec GPT-4 Vision, Claude Vision ou Gemini.",
                "mode": "local_fallback"
            }
        except Exception as e:
            logger.error(f"Local fallback failed: {e}")
            return {
                "description": "Impossible d'analyser l'image en mode local",
                "trend": "indecis",
                "patterns_detected": [],
                "support_levels": [],
                "resistance_levels": [],
                "indicators": [],
                "confidence": 0.1,
                "key_observations": f"Erreur: {str(e)}"
            }

    def analyze_image(self, image_path: Path, style_key: str = "general") -> Dict[str, Any]:
        """Point d'entrée principal"""
        # Get style prompt
        try:
            from app.config.styles import get_style
            style = get_style(style_key)
            style_prompt = style.get("vision_prompt_addition", "")
        except:
            style_prompt = ""
            style = {"name": style_key}
        
        # Try providers in order: OpenAI, Anthropic, Google, then fallback
        result = None
        provider_used = "local"
        
        if "openai" in self.available_providers:
            result = self._analyze_with_openai(image_path, style_prompt)
            if result:
                provider_used = "openai"
        
        if not result and "anthropic" in self.available_providers:
            result = self._analyze_with_anthropic(image_path, style_prompt)
            if result:
                provider_used = "anthropic"
        
        if not result and "google" in self.available_providers:
            result = self._analyze_with_google(image_path, style_prompt)
            if result:
                provider_used = "google"
        
        if not result:
            result = self._analyze_local_fallback(image_path)
            provider_used = "local"
        
        result["provider"] = provider_used
        result["style_used"] = style_key
        return result

    def get_available_providers(self) -> Dict[str, bool]:
        return {
            "openai": bool(self.openai_key),
            "anthropic": bool(self.anthropic_key),
            "google": bool(self.google_key),
            "local": True
        }
