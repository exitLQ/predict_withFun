import os
import json
from typing import List
from openai import OpenAI
from models import Market, AnalysisResult, MarketAnalysis
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def build_analysis_prompt(markets: List[Market], category: str) -> str:
    """Build a prompt for OpenAI to analyze markets"""
    prompt = f"""Du bist ein Experte für Wahrscheinlichkeitsanalyse und Marktbewertung. 
Analysiere die folgenden Top-Märkte aus der Kategorie "{category}" von Polymarket.

Für jeden Markt sollst du:
1. Die aktuelle Marktwahrscheinlichkeit bewerten
2. Eine faire Einschätzung der tatsächlichen Wahrscheinlichkeit geben
3. Risiken und Verzerrungen identifizieren
4. Begründen, ob der Marktpreis fair, überbewertet oder unterbewertet ist

Marktdaten:
"""
    
    for i, market in enumerate(markets, 1):
        prompt += f"\n{i}. {market.title}\n"
        prompt += f"   Volumen: ${market.volume:,.2f}\n"
        if market.description:
            prompt += f"   Beschreibung: {market.description}\n"
        prompt += "   Outcomes:\n"
        for outcome in market.outcomes:
            prompt += f"     - {outcome.title}: {outcome.probability:.2%} (Preis: {outcome.price:.4f})\n"
    
    prompt += """
Antworte im folgenden JSON-Format:
{
  "summary": "Eine zusammenfassende Analyse aller Märkte in 2-3 Sätzen",
  "overall_insights": "Wichtige Erkenntnisse und Trends",
  "markets": [
    {
      "market_title": "Titel des Markts",
      "market_probability": 0.65,
      "fair_probability": 0.70,
      "assessment": "unterbewertet|fair|überbewertet",
      "risks": ["Risiko 1", "Risiko 2"],
      "reasoning": "Detaillierte Begründung der Einschätzung"
    }
  ]
}

Wichtig: Antworte NUR mit gültigem JSON, keine zusätzlichen Erklärungen außerhalb des JSON.
"""
    return prompt


def analyze_markets(markets: List[Market], category: str) -> AnalysisResult:
    """Analyze markets using OpenAI API"""
    if not markets:
        return AnalysisResult(
            category=category,
            summary="Keine Märkte zum Analysieren vorhanden.",
            markets=[],
            overall_insights="Keine Daten verfügbar."
        )
    
    prompt = build_analysis_prompt(markets, category)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "Du bist ein Experte für Wahrscheinlichkeitsanalyse und Marktbewertung. Antworte immer im angeforderten JSON-Format."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        analysis_data = json.loads(content)
        
        # Build structured analysis
        market_analyses = []
        for market in markets:
            # Find matching analysis from OpenAI response
            market_analysis_data = None
            for ma in analysis_data.get("markets", []):
                if ma.get("market_title") == market.title:
                    market_analysis_data = ma
                    break
            
            if market_analysis_data:
                # Get the main outcome probability (usually the first one or highest)
                main_probability = market.outcomes[0].probability if market.outcomes else 0.5
                
                market_analyses.append(MarketAnalysis(
                    market_slug=market.slug,
                    market_title=market.title,
                    market_probability=main_probability,
                    fair_probability=market_analysis_data.get("fair_probability"),
                    assessment=market_analysis_data.get("assessment", "fair"),
                    risks=market_analysis_data.get("risks", []),
                    reasoning=market_analysis_data.get("reasoning", "")
                ))
            else:
                # Fallback if no matching analysis found
                main_probability = market.outcomes[0].probability if market.outcomes else 0.5
                market_analyses.append(MarketAnalysis(
                    market_slug=market.slug,
                    market_title=market.title,
                    market_probability=main_probability,
                    assessment="fair",
                    risks=[],
                    reasoning="Keine detaillierte Analyse verfügbar."
                ))
        
        return AnalysisResult(
            category=category,
            summary=analysis_data.get("summary", "Analyse abgeschlossen."),
            markets=market_analyses,
            overall_insights=analysis_data.get("overall_insights")
        )
        
    except json.JSONDecodeError as e:
        print(f"Error parsing OpenAI JSON response: {e}")
        return AnalysisResult(
            category=category,
            summary="Fehler beim Parsen der Analyse-Ergebnisse.",
            markets=[],
            overall_insights="JSON-Parsing-Fehler."
        )
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return AnalysisResult(
            category=category,
            summary=f"Fehler bei der Analyse: {str(e)}",
            markets=[],
            overall_insights="API-Fehler aufgetreten."
        )
