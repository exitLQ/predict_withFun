const API_BASE = '/api';

let currentCategoryId = null;
let currentMarkets = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadCategories();
    
    document.getElementById('loadMarketsBtn').addEventListener('click', loadMarkets);
    document.getElementById('analyzeBtn').addEventListener('click', startAnalysis);
    document.getElementById('categorySelect').addEventListener('change', onCategoryChange);
});

async function loadCategories() {
    showLoading(true);
    hideError();
    
    try {
        const response = await fetch(`${API_BASE}/categories`);
        if (!response.ok) {
            throw new Error('Fehler beim Laden der Kategorien');
        }
        
        const categories = await response.json();
        const select = document.getElementById('categorySelect');
        
        select.innerHTML = '<option value="">Kategorie auswählen...</option>';
        categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category.id;
            option.textContent = category.name;
            select.appendChild(option);
        });
    } catch (error) {
        showError('Fehler beim Laden der Kategorien: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function onCategoryChange() {
    const select = document.getElementById('categorySelect');
    currentCategoryId = select.value;
    const loadBtn = document.getElementById('loadMarketsBtn');
    const analyzeBtn = document.getElementById('analyzeBtn');
    
    loadBtn.disabled = !currentCategoryId;
    analyzeBtn.disabled = true;
    
    // Hide markets and analysis sections
    document.getElementById('marketsSection').style.display = 'none';
    document.getElementById('analysisSection').style.display = 'none';
    currentMarkets = [];
}

async function loadMarkets() {
    if (!currentCategoryId) return;
    
    showLoading(true);
    hideError();
    hideSection('marketsSection');
    hideSection('analysisSection');
    
    try {
        const response = await fetch(`${API_BASE}/markets/${currentCategoryId}`);
        if (!response.ok) {
            throw new Error('Fehler beim Laden der Märkte');
        }
        
        currentMarkets = await response.json();
        displayMarkets(currentMarkets);
        document.getElementById('analyzeBtn').disabled = false;
    } catch (error) {
        showError('Fehler beim Laden der Märkte: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function displayMarkets(markets) {
    const container = document.getElementById('marketsTableContainer');
    
    if (markets.length === 0) {
        container.innerHTML = '<p>Keine Märkte in dieser Kategorie gefunden.</p>';
        document.getElementById('marketsSection').style.display = 'block';
        return;
    }
    
    let html = '<table><thead><tr>';
    html += '<th>Titel</th>';
    html += '<th>Volumen</th>';
    html += '<th>Outcomes & Wahrscheinlichkeiten</th>';
    html += '</tr></thead><tbody>';
    
    markets.forEach(market => {
        html += '<tr>';
        html += `<td><strong>${escapeHtml(market.title)}</strong></td>`;
        html += `<td class="volume">$${formatNumber(market.volume)}</td>`;
        html += '<td><div class="outcomes">';
        
        market.outcomes.forEach(outcome => {
            html += `<div class="outcome-item">`;
            html += `<span>${escapeHtml(outcome.title)}: </span>`;
            html += `<span class="probability">${(outcome.probability * 100).toFixed(2)}%</span>`;
            html += `</div>`;
        });
        
        html += '</div></td>';
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
    document.getElementById('marketsSection').style.display = 'block';
}

async function startAnalysis() {
    if (!currentCategoryId) return;
    
    showLoading(true);
    hideError();
    hideSection('analysisSection');
    
    try {
        const response = await fetch(`${API_BASE}/analyze?category_id=${currentCategoryId}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Fehler bei der Analyse');
        }
        
        const analysis = await response.json();
        displayAnalysis(analysis);
    } catch (error) {
        showError('Fehler bei der Analyse: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function displayAnalysis(analysis) {
    const container = document.getElementById('analysisContent');
    
    let html = '<div class="analysis-content">';
    
    // Summary
    html += `<div class="analysis-summary">${escapeHtml(analysis.summary)}</div>`;
    
    // Overall insights
    if (analysis.overall_insights) {
        html += '<div class="analysis-insights">';
        html += '<h3>Wichtige Erkenntnisse</h3>';
        html += `<p>${escapeHtml(analysis.overall_insights)}</p>`;
        html += '</div>';
    }
    
    // Per-market analysis
    if (analysis.markets && analysis.markets.length > 0) {
        analysis.markets.forEach(marketAnalysis => {
            html += '<div class="market-analysis">';
            html += `<h4>${escapeHtml(marketAnalysis.market_title)}</h4>`;
            
            // Metrics
            html += '<div class="analysis-metrics">';
            html += '<div class="metric">';
            html += '<div class="metric-label">Markt-Wahrscheinlichkeit</div>';
            html += `<div class="metric-value">${(marketAnalysis.market_probability * 100).toFixed(2)}%</div>`;
            html += '</div>';
            
            if (marketAnalysis.fair_probability !== null && marketAnalysis.fair_probability !== undefined) {
                html += '<div class="metric">';
                html += '<div class="metric-label">Faire Wahrscheinlichkeit</div>';
                html += `<div class="metric-value">${(marketAnalysis.fair_probability * 100).toFixed(2)}%</div>`;
                html += '</div>';
            }
            
            html += '<div class="metric">';
            html += '<div class="metric-label">Bewertung</div>';
            const assessmentClass = `assessment-${getAssessmentClass(marketAnalysis.assessment)}`;
            html += `<div class="metric-value"><span class="assessment-badge ${assessmentClass}">${escapeHtml(marketAnalysis.assessment)}</span></div>`;
            html += '</div>';
            html += '</div>';
            
            // Risks
            if (marketAnalysis.risks && marketAnalysis.risks.length > 0) {
                html += '<div class="risks-list">';
                html += '<strong>Risiken:</strong>';
                html += '<ul>';
                marketAnalysis.risks.forEach(risk => {
                    html += `<li>${escapeHtml(risk)}</li>`;
                });
                html += '</ul>';
                html += '</div>';
            }
            
            // Reasoning
            if (marketAnalysis.reasoning) {
                html += '<div class="reasoning">';
                html += '<strong>Begründung:</strong><br>';
                html += escapeHtml(marketAnalysis.reasoning);
                html += '</div>';
            }
            
            html += '</div>';
        });
    }
    
    html += '</div>';
    container.innerHTML = html;
    document.getElementById('analysisSection').style.display = 'block';
}

function getAssessmentClass(assessment) {
    const lower = assessment.toLowerCase();
    if (lower.includes('überbewertet') || lower.includes('overpriced')) {
        return 'overpriced';
    } else if (lower.includes('unterbewertet') || lower.includes('underpriced')) {
        return 'underpriced';
    }
    return 'fair';
}

function showLoading(show) {
    document.getElementById('loadingSection').style.display = show ? 'block' : 'none';
}

function showError(message) {
    const errorSection = document.getElementById('errorSection');
    document.getElementById('errorMessage').textContent = message;
    errorSection.style.display = 'block';
}

function hideError() {
    document.getElementById('errorSection').style.display = 'none';
}

function hideSection(sectionId) {
    document.getElementById(sectionId).style.display = 'none';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatNumber(num) {
    return new Intl.NumberFormat('de-DE', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(num);
}
