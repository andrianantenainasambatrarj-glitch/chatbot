# HLZ Complet — Guide pour préparer ton IA

Tu veux que l'IA se base sur **HLZ complet** (High Low ZigZag / Smart Money HLZ). Voici comment faire pour que le RAG comprenne vraiment ta méthode et cite tes règles.

## ✅ Ce que fait l'app (ton intuition est juste)

1. Tu donnes **plusieurs PDFs** (1 PDF = 1 leçon)
2. L'IA découpe chaque PDF en chunks de ~400 mots
3. Elle convertit en vecteurs (embeddings) et stocke dans ChromaDB
4. Quand tu envoies une image de graphique, la Vision LLM décrit la structure
5. Cette description sert de requête RAG → elle retrouve les 5 chunks les plus pertinents de TES cours HLZ
6. Synthèse finale : Vision + RAG → analyse en vocabulaire HLZ (BOS, CHOCH, OB, FVG...)

**Donc oui : elle apprend toutes les leçons de tes PDFs et analyse l'image avec tes leçons.**

## 🔥 HLZ Complet — Structure recommandée de PDFs

Ne mets pas 1 seul gros PDF de 200 pages. Découpe en 6-10 PDFs thématiques, c'est CRITIQUE pour le RAG.

### PDFs à créer (nommage important) :

```
01_HLZ_Structure_Marche_HH_HL_LH_LL.pdf
02_HLZ_BOS_Break_of_Structure.pdf
03_HLZ_CHOCH_Change_of_Character.pdf
04_HLZ_Order_Blocks_OB_Validation.pdf
05_HLZ_FVG_Fair_Value_Gap_Imbalance.pdf
06_HLZ_Liquidites_Buy_Side_Sell_Side.pdf
07_HLZ_Premium_Discount_OTE_Fib.pdf
08_HLZ_Entry_Models_HLZ_Checklist.pdf
09_HLZ_Exemples_Trades_Gagnants.pdf
10_HLZ_Erreurs_Pieges_Inducement.pdf
```

### Contenu idéal pour chaque PDF :

**Page 1 : Définition claire**
```
HLZ - Order Block (OB) - Définition
Un Order Block est la dernière bougie baissière avant une impulsion haussière forte (ou inverse).
Caractéristiques d'un OB valide:
- Doit être avant un BOS
- Corps de bougie significatif
- Mitigation à 50% ou CE
...
```

**Page 2 : Règles de validation (l'IA va citer ça)**
```
Règles de validation OB selon HLZ complet:
1. OB doit être le dernier mouvement opposé avant BOS
2. Doit avoir causé un FVG
3. Invalidation si clôture corps au-delà de l'OB
4. ...
```

**Page 3 : Exemples textuels (pas juste images)**
```
Exemple 1: Sur EURUSD H1, le 12/03/2024, OB haussier à 1.0850-1.0860...
Après BOS à 1.0900, retour en discount sur OB + FVG = entrée long...
```

**Page 4 : Erreurs à éviter**

### 🎯 Astuce RAG pour HLZ

Le RAG cherche par similarité sémantique. Donc:

- Utilise les mêmes mots-clés que tu veux voir dans l'analyse : "BOS", "CHOCH", "Order Block", "FVG", "Liquidité", "Premium", "Discount", "Sweep", "Inducement"
- Mets ces mots dans les titres de sections
- Répète la définition au début de chaque PDF

Exemple de chunk parfait pour RAG :
> "Selon la méthode HLZ complet, un BOS (Break of Structure) se valide par une clôture de corps de bougie au-delà du dernier HH pour un BOS haussier. Il doit être accompagné d'un volume ou d'un FVG. Si le BOS échoue et qu'on a un CHOCH, on passe potentiellement baissier..."

Ce chunk sera retrouvé quand l'IA verra un BOS sur le graphique.

## 📸 Pour les graphiques

Quand tu uploades une image:

1. Sélectionne le style **HLZ Complet** dans le menu (nouveau)
2. L'IA va utiliser un prompt spécialisé HLZ :
   - Cherche HH/HL, LH/LL
   - Repère BOS/CHOCH
   - Localise OB, FVG, liquidités
   - Note Premium/Discount
3. Top-K = 5 ou 8 pour HLZ (plus de contexte)

## 🧠 Checklist HLZ à inclure en PDF (l'IA va l'utiliser)

Crée un PDF `HLZ_Checklist_Entree.pdf` :

```
CHECKLIST ENTREE HLZ COMPLET:

1. STRUCTURE: Sommes-nous en HH/HL haussier ou LH/LL baissier? Dernier BOS où?
2. LIQUIDITE: Y a-t-il eu sweep de liquidité? Buy Side au-dessus? Sell Side en dessous? Equal highs/lows?
3. CHOCH? Y a-t-il eu changement de caractère récent?
4. ZONE: Sommes-nous en Discount (<50% fib dernier swing) pour achat ou Premium (>50%) pour vente?
5. OB: Y a-t-il un Order Block valide non mitigé dans la zone?
6. FVG: Y a-t-il un Fair Value Gap aligné avec l'OB?
7. CONFLUENCE: Au moins 3 confluences HLZ? (ex: OB + FVG + Discount + Sweep)
8. ENTRY: Entrée sur mitigation OB ou 50% FVG, stop au-delà OB, TP sur prochaine liquidité

Si 3+ confluences = trade HLZ valide selon méthode.
```

L'IA va citer cette checklist dans sa recommandation.

## 🚀 Workflow complet HLZ

1. Prépare tes 8-10 PDFs HLZ comme ci-dessus
2. Va sur l'app → Upload tous les PDFs → "Indexer" → vérifie 100+ chunks créés
3. Sélectionne style "HLZ Complet 🔥"
4. Upload graphique TradingView (bien visible)
5. Analyse → Tu obtiens :
   - Pattern principal en vocabulaire HLZ
   - Analyse technique avec BOS/CHOCH/OB/FVG
   - Prédiction avec logique HLZ
   - Niveaux : OB, FVG, liquidités, entrée OTE, SL/TP
   - Méthodologie : citation de TES PDFs HLZ
   - Recommandation checklist HLZ

## ❓ Tu n'as pas de PDFs HLZ déjà faits ?

Tu peux:
- Exporter tes notes Notion/Google Docs en PDF
- Copier-coller tes cours Discord/Telegram dans Word → PDF
- Même des captures d'écran avec texte + OCR (mais texte sélectionnable mieux)
- Commencer avec 2-3 PDFs, ajouter au fur et à mesure, le RAG s'enrichit

Plus tu donnes de PDFs HLZ de qualité, plus l'IA parle comme toi.

## 📚 Exemple de prompt final que l'IA utilise pour HLZ

```
Tu analyses selon la méthode HLZ COMPLÈTE:
1. STRUCTURE: HH/HL ou LH/LL? Dernier BOS? CHOCH?
2. LIQUIDITÉS: Buy/Sell Side, Equal Highs/Lows
3. ZONES HLZ: OB valide, FVG, Breaker
4. PREMIUM/DISCOUNT: fib 50%
5. ENTRY: sweep + BOS + retour OB/FVG discount/premium
Ta prédiction DOIT utiliser vocabulaire HLZ: BOS, CHOCH, OB, FVG, Liquidity Sweep...
```

C'est pour ça que sélectionner "HLZ" change tout.

---

Besoin d'aide pour structurer tes PDFs HLZ ? Envoie-moi un exemple de ton cours et je te fais le découpage.
