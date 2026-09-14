import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

FINAL_SYNTHESIS_PROMPT_BASE = """Tu es un expert trading senior spécialisé en {style_name}. Tu dois produire une analyse finale structurée en t'appuyant sur:

1. L'ANALYSE VISUELLE du graphique:
{vision_analysis}

2. Le CONTEXTE DES COURS (méthodologie de l'utilisateur):
{rag_context}

3. STYLE DE TRADING: {style_name} - {style_description}
{style_addition}

Ta tâche: Fusionne ces deux sources pour produire une analyse professionnelle SELON LE STYLE {style_name}.

RÈGLES:
- Si les cours mentionnent une méthodologie spécifique (ex: "selon la méthode X, un double top se valide par..."), cite-la explicitement
- Sois honnête sur ton niveau de confiance
- Donne des niveaux de prix concrets si visibles
- Explique la logique derrière ta prédiction en utilisant le vocabulaire du style {style_name}
- Mentionne les risques et invalidations spécifiques au style
- Si style HLZ: utilise BOS, CHOCH, OB, FVG, Liquidité, Premium/Discount, OTE

Réponds en JSON avec cette structure exacte:
{{
  "pattern_principal": "nom du pattern principal détecté selon {style_name}",
  "confiance": 0.0-1.0,
  "explication_methodologie": "comment ta détection s'appuie sur les cours fournis et le style {style_name}",
  "analyse_technique": "analyse technique détaillée (3-5 phrases) en vocabulaire {style_name}",
  "prediction": "prédiction haussière/baissière/latérale avec justification et target selon {style_name}",
  "niveaux_cles": {{
    "supports": ["liste supports"],
    "resistances": ["liste résistances"],
    "entree": ["zones d'entrée potentielles selon {style_name}"],
    "stop_loss": ["niveaux stop loss"],
    "take_profit": ["objectifs"]
  }},
  "risques": "risques et conditions d'invalidation selon {style_name}",
  "recommandation": "recommandation actionnable selon {style_name}",
  "timeframe_suggere": "timeframe suggéré pour le trade"
}}
"""

def build_final_prompt(vision_analysis, rag_context, style):
    return FINAL_SYNTHESIS_PROMPT_BASE.format(
        vision_analysis=vision_analysis,
        rag_context=rag_context,
        style_name=style.get("name", "Général"),
        style_description=style.get("description", ""),
        style_addition=style.get("analysis_prompt_addition", "")
    )

class AnalysisService:
    def __init__(self, rag_service, vision_service):
        self.rag_service = rag_service
        self.vision_service = vision_service
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.google_key = os.getenv("GOOGLE_API_KEY")

    def _format_rag_context(self, rag_results: List[Dict[str, Any]]) -> str:
        if not rag_results:
            return "Aucun contexte de cours disponible. Utilise tes connaissances générales en analyse technique."
        
        context_parts = []
        for i, chunk in enumerate(rag_results, 1):
            source = chunk.get("source", "cours")
            page = chunk.get("page", "")
            content = chunk.get("content", "")[:800]
            score = chunk.get("score", 0)
            context_parts.append(f"[Source {i} - {source} p.{page} - pertinence {score:.2f}]\n{content}\n")
        
        return "\n".join(context_parts)

    def _format_vision_analysis(self, vision: Dict[str, Any]) -> str:
        return f"""
Description: {vision.get('description','')}
Tendance détectée: {vision.get('trend','')}
Patterns: {', '.join(vision.get('patterns_detected', []))}
Supports: {', '.join(vision.get('support_levels', []))}
Résistances: {', '.join(vision.get('resistance_levels', []))}
Indicateurs: {', '.join(vision.get('indicators', []))}
Observations clés: {vision.get('key_observations','')}
Confiance vision: {vision.get('confidence',0)}
Provider: {vision.get('provider','')}
Style: {vision.get('style_used','general')}
"""

    def _synthesize_with_openai(self, vision_str: str, rag_str: str, style: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.openai_key:
            return None
        try:
            from openai import OpenAI
            import json, re
            client = OpenAI(api_key=self.openai_key)
            
            prompt = build_final_prompt(vision_str, rag_str, style)
            
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": f"Tu es un expert trading {style.get('name','')} qui répond uniquement en JSON valide."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            content = response.choices[0].message.content
            
            # Extract JSON
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            try:
                return json.loads(content)
            except:
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end != -1:
                    return json.loads(content[start:end])
            return None
        except Exception as e:
            logger.error(f"OpenAI synthesis failed: {e}")
            return None

    def _synthesize_with_anthropic(self, vision_str: str, rag_str: str, style: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.anthropic_key:
            return None
        try:
            import anthropic, json, re
            client = anthropic.Anthropic(api_key=self.anthropic_key)
            
            prompt = build_final_prompt(vision_str, rag_str, style)
            
            response = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            try:
                return json.loads(content)
            except:
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end != -1:
                    return json.loads(content[start:end])
            return None
        except Exception as e:
            logger.error(f"Anthropic synthesis failed: {e}")
            return None

    def _synthesize_with_google(self, vision_str: str, rag_str: str, style: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.google_key:
            return None
        try:
            import google.generativeai as genai
            import json, re
            genai.configure(api_key=self.google_key)
            model = genai.GenerativeModel(os.getenv("GOOGLE_MODEL", "gemini-1.5-flash"))
            
            prompt = build_final_prompt(vision_str, rag_str, style)
            
            response = model.generate_content(prompt)
            content = response.text
            
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            try:
                return json.loads(content)
            except:
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end != -1:
                    return json.loads(content[start:end])
            return None
        except Exception as e:
            logger.error(f"Google synthesis failed: {e}")
            return None

    def _synthesize_local(self, vision: Dict[str, Any], rag_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback local sans LLM"""
        trend = vision.get("trend", "indecis")
        patterns = vision.get("patterns_detected", [])
        pattern_principal = patterns[0] if patterns else "aucun pattern clair"
        
        # Build methodology explanation from RAG
        if rag_results:
            sources = [f"{r.get('source','')} p.{r.get('page','')}" for r in rag_results[:3]]
            methodo = f"Analyse basée sur {len(rag_results)} extraits de vos cours ({', '.join(sources)}). Le pattern '{pattern_principal}' a été comparé avec votre méthodologie. Consultez les chunks RAG ci-dessous pour la validation selon votre méthode."
        else:
            methodo = "Aucun cours fourni - analyse basée sur l'analyse visuelle seule et les connaissances générales. Pour une analyse enrichie de votre méthode, uploadez vos PDFs de cours."
        
        # Prediction based on trend
        if trend == "haussier":
            prediction = "Biais haussier probable - continuation attendue si les supports tiennent. Cible: prochaine résistance visible. Invalidation sous le dernier support."
            recommandation = "Chercher des achats sur repli, stop sous support"
        elif trend == "baissier":
            prediction = "Biais baissier probable - pression vendeuse. Cible: prochain support. Invalidation au-dessus de la dernière résistance."
            recommandation = "Chercher des ventes sur rebond, stop au-dessus résistance"
        elif trend == "lateral":
            prediction = "Marché en range - pas de direction claire. Attendre cassure de range pour directionnel, ou trader les bornes en mean-reversion."
            recommandation = "Range trading ou attente de breakout avec volume"
        else:
            prediction = "Tendance indécise - manque de clarté. Éviter ou réduire la taille. Attendre signal plus clair."
            recommandation = "Stand aside ou très petite taille, attendre confirmation"
        
        return {
            "pattern_principal": pattern_principal,
            "confiance": vision.get("confidence", 0.4) * 0.8,  # slightly lower for local
            "explication_methodologie": methodo,
            "analyse_technique": vision.get("description", "")[:500] + f" Tendance {trend} détectée. Patterns: {', '.join(patterns) if patterns else 'aucun pattern majeur clairement identifié'}.",
            "prediction": prediction,
            "niveaux_cles": {
                "supports": vision.get("support_levels", ["Support à identifier"])[:5],
                "resistances": vision.get("resistance_levels", ["Résistance à identifier"])[:5],
                "entree": ["Entrée sur confirmation"],
                "stop_loss": ["Sous support / Au-dessus résistance"],
                "take_profit": ["Prochaine zone S/R, ratio R:R 1:2 minimum"]
            },
            "risques": "Risque de faux signal, volatilité, news. Toujours confirmer avec volume et timeframe supérieur. Invalidation si cassure inverse avec volume. Mode local = confiance réduite, utilisez une clé API LLM pour précision maximale.",
            "recommandation": recommandation,
            "timeframe_suggere": "Confirmer en H4/Daily, entrée en M15/H1"
        }

    def analyze(self, image_path: Path, top_k: int = 5, style_key: str = "general") -> Dict[str, Any]:
        # Get style
        try:
            from app.config.styles import get_style
            style = get_style(style_key)
        except:
            style = {"name": style_key, "description": "", "analysis_prompt_addition": ""}
        
        # Step 1: Vision
        logger.info(f"Starting vision analysis for {image_path} with style {style_key}")
        vision_result = self.vision_service.analyze_image(image_path, style_key=style_key)
        
        # Step 2: RAG search from vision
        logger.info("Searching RAG from vision analysis")
        rag_results = self.rag_service.search_from_vision(vision_result, top_k=top_k)
        
        # Step 3: Final synthesis
        vision_str = self._format_vision_analysis(vision_result)
        rag_str = self._format_rag_context(rag_results)
        
        synthesis = None
        model_used = "local"
        
        # Try LLM synthesis in order
        if self.openai_key:
            synthesis = self._synthesize_with_openai(vision_str, rag_str, style)
            if synthesis:
                model_used = f"openai:{os.getenv('OPENAI_TEXT_MODEL','gpt-4o-mini')}"
        
        if not synthesis and self.anthropic_key:
            synthesis = self._synthesize_with_anthropic(vision_str, rag_str, style)
            if synthesis:
                model_used = f"anthropic:{os.getenv('ANTHROPIC_MODEL','claude-3-5-sonnet')}"
        
        if not synthesis and self.google_key:
            synthesis = self._synthesize_with_google(vision_str, rag_str, style)
            if synthesis:
                model_used = f"google:{os.getenv('GOOGLE_MODEL','gemini-1.5-flash')}"
        
        if not synthesis:
            synthesis = self._synthesize_local(vision_result, rag_results)
            # Enhance local with style
            if style_key == "hlz":
                synthesis["recommandation"] = f"[HLZ] {synthesis['recommandation']} | Cherche OB+FVG+Liquidité en Discount/Premium"
                synthesis["analyse_technique"] = f"[HLZ - {style['name']}] {synthesis['analyse_technique']}"
            model_used = f"local-heuristic-{style_key}"
        
        # Ensure all required fields
        default_levels = {
            "supports": ["Non détecté"],
            "resistances": ["Non détecté"],
            "entree": ["À confirmer"],
            "stop_loss": ["À définir"],
            "take_profit": ["À définir"]
        }
        
        # Build final response
        return {
            "vision": vision_result,
            "rag_chunks": rag_results,
            "pattern_principal": synthesis.get("pattern_principal", "indéterminé"),
            "confiance": float(synthesis.get("confiance", vision_result.get("confidence", 0.5))),
            "explication_methodologie": synthesis.get("explication_methodologie", ""),
            "analyse_technique": synthesis.get("analyse_technique", ""),
            "prediction": synthesis.get("prediction", ""),
            "niveaux_cles": synthesis.get("niveaux_cles", default_levels),
            "risques": synthesis.get("risques", ""),
            "recommandation": synthesis.get("recommandation", ""),
            "timeframe_suggere": synthesis.get("timeframe_suggere", ""),
            "sources_utilisees": [r.get("source","") for r in rag_results],
            "model_utilise": model_used
        }
