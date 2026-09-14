"""
Styles de trading prédéfinis - dont HLZ complet
Tu peux ajouter tes propres styles ici
"""
TRADING_STYLES = {
    "hlz": {
        "name": "HLZ Complet (High Low ZigZag)",
        "description": "Méthode HLZ - structure de marché, BOS, CHOCH, Order Blocks, FVG, Liquidités",
        "icon": "fa-wave-square",
        "color": "from-orange-600 to-red-600",
        "vision_prompt_addition": """
FOCUS HLZ:
- Identifie la structure: HH/HL (haussier) ou LH/LL (baissier)
- Repère les BOS (Break of Structure) et CHOCH (Change of Character)
- Localise les Order Blocks (OB), Fair Value Gaps (FVG), zones de liquidité (Equal Highs/Lows, Buy/Sell Side)
- Détecte les inducements, sweep de liquidité, et retours dans discount/premium
- Note les zones Premium (>50% fib) vs Discount (<50%)
- Cherche les points d'intérêt HLZ: OB + FVG + Liquidité alignés
""",
        "analysis_prompt_addition": """
Tu analyses selon la méthode HLZ COMPLÈTE:

1. STRUCTURE: Détermine si on est en HH/HL haussier ou LH/LL baissier. Où est le dernier BOS? Y a-t-il eu CHOCH récent?
2. LIQUIDITÉS: Où sont les liquidités? Buy Side au-dessus des highs, Sell Side sous les lows, equal highs/lows, trendline liquidity?
3. ZONES HLZ: Identifie les Order Blocks valides (dernier bougie avant impulsion), FVG (imbalance), Breaker Blocks, Mitigation Blocks
4. PREMIUM/DISCOUNT: Utilise fib du dernier swing HLZ pour déterminer si on est en premium (vente) ou discount (achat)
5. ENTRY MODEL HLZ: Attends sweep de liquidité + BOS + retour OB/FVG en discount/premium pour entrée
6. CONFLUENCES: Score HLZ = Structure + Liquidité + OB + FVG + Premium/Discount

Ta prédiction DOIT utiliser le vocabulaire HLZ: BOS, CHOCH, OB, FVG, Liquidity Sweep, Inducement, Premium, Discount, OTE, etc.
"""
    },
    "smc": {
        "name": "SMC (Smart Money Concepts)",
        "description": "SMC classique - OB, FVG, BOS, CHOCH, Liquidités",
        "icon": "fa-brain",
        "color": "from-violet-600 to-indigo-600",
        "vision_prompt_addition": "Focus SMC: BOS, CHOCH, Order Blocks, FVG, Liquidités, Premium/Discount, Killzones",
        "analysis_prompt_addition": "Analyse en SMC: Structure, Liquidités, OB, FVG, Entry après sweep + mitigation"
    },
    "ict": {
        "name": "ICT (Inner Circle Trader)",
        "description": "ICT - Market Structure, OTE, Killzones, PD Arrays",
        "icon": "fa-clock",
        "color": "from-emerald-600 to-teal-600",
        "vision_prompt_addition": "Focus ICT: Market Structure, OTE (Optimal Trade Entry), Killzones (London/NY), PD Arrays, Reaper",
        "analysis_prompt_addition": "Analyse ICT: Time & Price, OTE 62-79%, Killzones, Daily bias, PD Arrays"
    },
    "price_action": {
        "name": "Price Action Pur",
        "description": "Price action classique - supports, résistances, patterns bougies",
        "icon": "fa-chart-line",
        "color": "from-blue-600 to-cyan-600",
        "vision_prompt_addition": "Focus Price Action: S/R, tendances, patterns chandeliers (marteau, englobante, doji), figures chartistes",
        "analysis_prompt_addition": "Analyse Price Action pure: S/R, trendlines, patterns, volumes, sans indicateurs"
    },
    "elliott": {
        "name": "Elliott Waves",
        "description": "Vagues d'Elliott - 5 vagues impulsives + 3 correctives",
        "icon": "fa-water",
        "color": "from-pink-600 to-rose-600",
        "vision_prompt_addition": "Focus Elliott: Compte les vagues 1-5 impulsives et A-B-C correctives, fib, extensions",
        "analysis_prompt_addition": "Analyse Elliott: Où en sommes-nous dans le cycle 5-3? Extension? Retracement fib?"
    },
    "general": {
        "name": "Général / Tous styles",
        "description": "Analyse généraliste - utilise tous les concepts de tes PDFs",
        "icon": "fa-layer-group",
        "color": "from-gray-600 to-slate-600",
        "vision_prompt_addition": "",
        "analysis_prompt_addition": "Utilise tous les concepts trouvés dans les PDFs de l'utilisateur sans te limiter à un style."
    }
}

def get_style(style_key: str):
    return TRADING_STYLES.get(style_key, TRADING_STYLES["general"])

def list_styles():
    return [{"key": k, **v} for k, v in TRADING_STYLES.items()]
