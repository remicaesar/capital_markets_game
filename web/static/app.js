/**
 * Capital Markets Game - Frontend JavaScript
 * Handles API communication and UI updates
 */

// API Base URL
const API_BASE = '/api/game';

// Global State
let gameState = {
    gameId: null,
    selectedAction: 'buy',
    selectedCompany: null,
    companies: [],
    netWorthHistory: [],
    tradeHistory: [],
    achievements: {}
};

// Stock chart instance
let stockChart = null;

// Current option chain data
let currentOptionChain = null;

// Achievement Definitions
const ACHIEVEMENTS = {
    first_trade: {
        id: 'first_trade',
        title: 'First Steps',
        description: 'Execute your first trade',
        icon: '📈',
        check: (state) => state.tradeHistory.length >= 1
    },
    trader_10: {
        id: 'trader_10',
        title: 'Active Trader',
        description: 'Execute 10 trades',
        icon: '💹',
        check: (state) => state.tradeHistory.length >= 10
    },
    trader_50: {
        id: 'trader_50',
        title: 'Day Trader',
        description: 'Execute 50 trades',
        icon: '🔥',
        check: (state) => state.tradeHistory.length >= 50
    },
    profit_10: {
        id: 'profit_10',
        title: 'In the Green',
        description: 'Achieve 10% total return',
        icon: '💰',
        check: (state, apiState) => apiState && apiState.player.total_return_pct >= 10
    },
    profit_50: {
        id: 'profit_50',
        title: 'Big Winner',
        description: 'Achieve 50% total return',
        icon: '💎',
        check: (state, apiState) => apiState && apiState.player.total_return_pct >= 50
    },
    profit_100: {
        id: 'profit_100',
        title: 'Double Up',
        description: 'Double your money (100% return)',
        icon: '🚀',
        check: (state, apiState) => apiState && apiState.player.total_return_pct >= 100
    },
    diversified: {
        id: 'diversified',
        title: 'Diversified',
        description: 'Hold 5 different stocks at once',
        icon: '🎯',
        check: (state, apiState) => apiState && apiState.portfolio.length >= 5
    },
    short_seller: {
        id: 'short_seller',
        title: 'Bear Trader',
        description: 'Open a short position',
        icon: '🐻',
        check: (state) => state.tradeHistory.some(t => t.action === 'SHORT')
    },
    survivor: {
        id: 'survivor',
        title: 'Survivor',
        description: 'Complete a game without going negative',
        icon: '🛡️',
        check: (state, apiState) => apiState && apiState.game_over && apiState.player.total_return_pct >= 0
    },
    market_beater: {
        id: 'market_beater',
        title: 'Market Beater',
        description: 'Beat the market return',
        icon: '🏆',
        check: (state, apiState, finalStats) => finalStats && finalStats.alpha > 0
    },
    sharpe_master: {
        id: 'sharpe_master',
        title: 'Risk Manager',
        description: 'Achieve Sharpe ratio above 1.0',
        icon: '📊',
        check: (state, apiState) => apiState && apiState.player.sharpe_ratio >= 1.0
    },
    fear_buyer: {
        id: 'fear_buyer',
        title: 'Contrarian',
        description: 'Buy when Fear/Greed is below 25',
        icon: '🧠',
        check: (state) => state.achievements.fear_buyer_triggered
    }
};

// DOM Elements (cached after load)
let elements = {};

// ============================================================================
// API Functions
// ============================================================================

async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (body) {
        options.body = JSON.stringify(body);
    }
    
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'API error');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

async function startNewGame(seed = null) {
    const body = seed !== null ? { seed } : {};
    return await apiCall('/new', 'POST', body);
}

async function getGameState(gameId) {
    return await apiCall(`/state?game_id=${gameId}`);
}

async function executeAction(gameId, action, company, shares) {
    return await apiCall('/action', 'POST', {
        game_id: gameId,
        action,
        company,
        shares
    });
}

async function advanceTurn(gameId) {
    return await apiCall('/advance', 'POST', { game_id: gameId });
}

async function getSavesList() {
    return await apiCall('/saves');
}

async function saveGame(gameId, slot = 'websave') {
    return await apiCall('/save', 'POST', { game_id: gameId, slot });
}

async function loadGame(slot) {
    return await apiCall('/load', 'POST', { slot });
}

async function placeOrder(gameId, orderType, action, company, shares, limitPrice) {
    return await apiCall('/order', 'POST', {
        game_id: gameId,
        order_type: orderType,
        action,
        company,
        shares,
        limit_price: limitPrice
    });
}

async function cancelOrder(gameId, orderId) {
    return await apiCall('/order/cancel', 'POST', {
        game_id: gameId,
        order_id: orderId
    });
}

// Options API
async function getOptionChain(gameId, company) {
    return await apiCall(`/options/chain?game_id=${gameId}&company=${encodeURIComponent(company)}`);
}

async function buyOption(gameId, company, optionType, strikePrice, contracts) {
    return await apiCall('/options/buy', 'POST', {
        game_id: gameId,
        company,
        option_type: optionType,
        strike_price: strikePrice,
        contracts
    });
}

async function exerciseOption(gameId, optionId) {
    return await apiCall('/options/exercise', 'POST', {
        game_id: gameId,
        option_id: optionId
    });
}

async function sellOption(gameId, optionId) {
    return await apiCall('/options/sell', 'POST', {
        game_id: gameId,
        option_id: optionId
    });
}

// ============================================================================
// UI Update Functions
// ============================================================================

function updateHeader(state) {
    elements.currentTurn.textContent = state.turn;
    elements.maxTurns.textContent = state.max_turns;
    
    // Update progress bar
    const progress = (state.turn / state.max_turns) * 100;
    elements.turnProgress.style.width = `${progress}%`;
    
    // Update regime display
    const regime = state.regime.toLowerCase();
    let regimeText = state.regime.charAt(0).toUpperCase() + state.regime.slice(1);
    let regimeEmoji = '📊';
    
    if (regime === 'bull') {
        regimeText = 'Bull Market';
        regimeEmoji = '🐂';
    } else if (regime === 'bear') {
        regimeText = 'Bear Market';
        regimeEmoji = '🐻';
    } else if (regime === 'sideways') {
        regimeText = 'Sideways';
        regimeEmoji = '↔️';
    } else if (regime === 'volatile') {
        regimeText = 'Volatile';
        regimeEmoji = '⚡';
    }
    
    elements.regimeDisplay.textContent = regimeText;
    elements.regimeDisplay.className = `regime ${regime}`;
    elements.regimeEmoji.textContent = regimeEmoji;
}

function updateMarketTable(companies) {
    gameState.companies = companies;
    
    const tbody = elements.marketTbody;
    tbody.innerHTML = '';
    
    companies.forEach(company => {
        const row = document.createElement('tr');
        row.dataset.company = company.name;
        
        if (gameState.selectedCompany === company.name) {
            row.classList.add('selected');
        }
        
        const changeClass = company.change_pct >= 0 ? 'positive' : 'negative';
        const changeSign = company.change_pct >= 0 ? '+' : '';
        
        row.innerHTML = `
            <td class="company-name" data-company="${company.name}">
                <span class="company-name-text">${company.name}</span>
                <span class="chart-icon" title="View Chart">📊</span>
            </td>
            <td>${company.sector}</td>
            <td>$${company.price.toFixed(2)}</td>
            <td class="${changeClass}">${changeSign}${company.change_pct.toFixed(2)}%</td>
            <td>${company.rsi.toFixed(0)}</td>
            <td class="${company.momentum >= 0 ? 'positive' : 'negative'}">${company.momentum >= 0 ? '+' : ''}${company.momentum.toFixed(2)}%</td>
            <td>${company.volume.toFixed(2)}</td>
            <td>${company.beta.toFixed(2)}</td>
            <td>${company.trend}</td>
        `;

        // Click on row to select company
        row.addEventListener('click', (e) => {
            // Don't select if clicking on chart icon
            if (!e.target.classList.contains('chart-icon')) {
                selectCompany(company.name);
            }
        });

        // Click on company name or chart icon to show chart
        const companyCell = row.querySelector('.company-name');
        companyCell.addEventListener('click', (e) => {
            e.stopPropagation();
            showStockChart(company.name);
        });
        
        tbody.appendChild(row);
    });
    
    // Update company select dropdown
    updateCompanySelect(companies);
}

function updateCompanySelect(companies) {
    const select = elements.companySelect;
    const currentValue = select.value;
    
    select.innerHTML = '<option value="">Select company...</option>';
    
    companies.forEach(company => {
        const option = document.createElement('option');
        option.value = company.name;
        option.textContent = `${company.name} - $${company.price.toFixed(2)}`;
        select.appendChild(option);
    });
    
    // Restore selection if still valid
    if (currentValue && companies.find(c => c.name === currentValue)) {
        select.value = currentValue;
    } else if (gameState.selectedCompany) {
        select.value = gameState.selectedCompany;
    }
}

function selectCompany(companyName) {
    gameState.selectedCompany = companyName;
    elements.companySelect.value = companyName;
    
    // Update table selection highlight
    document.querySelectorAll('.market-table tr').forEach(row => {
        row.classList.toggle('selected', row.dataset.company === companyName);
    });
    
    updateOrderPreview();
}

function updatePortfolio(portfolio) {
    const container = elements.portfolioContent;
    
    if (!portfolio || portfolio.length === 0) {
        container.innerHTML = '<p class="empty-message">No positions</p>';
        return;
    }
    
    container.innerHTML = portfolio.map(pos => {
        const pnlClass = pos.pnl >= 0 ? 'positive' : 'negative';
        const pnlSign = pos.pnl >= 0 ? '+' : '';
        
        return `
            <div class="position-item">
                <div class="position-header">
                    <span class="position-name">${pos.company}</span>
                    <span class="position-shares">${pos.shares} @ $${pos.avg_price.toFixed(2)}</span>
                </div>
                <div class="position-pnl ${pnlClass}">
                    P/L: ${pnlSign}$${pos.pnl.toFixed(2)} (${pnlSign}${pos.pnl_pct.toFixed(2)}%)
                </div>
            </div>
        `;
    }).join('');
}

function updateShortPositions(shorts) {
    const container = elements.shortsContent;
    
    if (!shorts || shorts.length === 0) {
        container.innerHTML = '<p class="empty-message">No short positions</p>';
        return;
    }
    
    container.innerHTML = shorts.map(pos => {
        const pnlClass = pos.pnl >= 0 ? 'positive' : 'negative';
        const pnlSign = pos.pnl >= 0 ? '+' : '';
        
        return `
            <div class="position-item">
                <div class="position-header">
                    <span class="position-name">${pos.company}</span>
                    <span class="position-shares">-${pos.shares} @ $${pos.borrow_price.toFixed(2)}</span>
                </div>
                <div class="position-pnl ${pnlClass}">
                    P/L: ${pnlSign}$${pos.pnl.toFixed(2)} (${pnlSign}${pos.pnl_pct.toFixed(2)}%)
                </div>
            </div>
        `;
    }).join('');
}

function updatePsychology(psychology) {
    // Fear/Greed Index (0-100)
    elements.fearGreedBar.style.width = `${psychology.fear_greed_index}%`;
    elements.fearGreedValue.textContent = psychology.fear_greed_index.toFixed(0);
    
    // Herd Level
    elements.herdBar.style.width = `${psychology.herd_strength}%`;
    elements.herdValue.textContent = `${psychology.herd_strength.toFixed(0)}%`;
    
    // Complacency
    elements.complacencyBar.style.width = `${psychology.complacency}%`;
    elements.complacencyValue.textContent = `${psychology.complacency.toFixed(0)}%`;
    
    // Sentiment emoji
    elements.sentimentEmoji.textContent = psychology.sentiment;
}

function updateStats(player) {
    elements.statCash.textContent = formatCurrency(player.cash);
    elements.statPortfolio.textContent = formatCurrency(player.portfolio_value);
    elements.statNetworth.textContent = formatCurrency(player.net_worth);
    
    const returnClass = player.total_return_pct >= 0 ? 'positive' : 'negative';
    const returnSign = player.total_return_pct >= 0 ? '+' : '';
    elements.statReturn.textContent = `${returnSign}${player.total_return_pct.toFixed(2)}%`;
    elements.statReturn.className = `stat-value ${returnClass}`;
    
    elements.statSharpe.textContent = player.sharpe_ratio.toFixed(2);
    elements.statDrawdown.textContent = `${player.max_drawdown.toFixed(2)}%`;
    elements.statTrades.textContent = player.trade_count;
    elements.statFees.textContent = formatCurrency(player.total_fees_paid);
    elements.statMargin.textContent = formatCurrency(player.available_margin);
}

function updateNews(news) {
    const container = elements.newsContent;
    
    if (!news || news.length === 0) {
        container.innerHTML = '<p class="empty-message">No news yet</p>';
        return;
    }
    
    container.innerHTML = news.map(item => {
        // Try to determine sentiment from keywords
        let sentimentClass = '';
        const lower = item.toLowerCase();
        if (lower.includes('rally') || lower.includes('surge') || lower.includes('beat') || lower.includes('bull') || lower.includes('growth')) {
            sentimentClass = 'positive';
        } else if (lower.includes('crash') || lower.includes('fall') || lower.includes('bear') || lower.includes('crisis') || lower.includes('miss')) {
            sentimentClass = 'negative';
        }
        
        return `<div class="news-item ${sentimentClass}">📰 ${item}</div>`;
    }).join('');
    
    // Scroll to bottom to show latest news
    container.scrollTop = container.scrollHeight;
}

function updateOrderPreview() {
    const company = gameState.companies.find(c => c.name === elements.companySelect.value);
    const shares = parseInt(elements.sharesInput.value) || 0;

    if (company && shares > 0) {
        const cost = company.price * shares * 1.005; // Include ~0.5% fee estimate
        elements.orderCost.textContent = formatCurrency(cost);
    } else {
        elements.orderCost.textContent = '$0.00';
    }
}

// ============================================================================
// Performance Chart
// ============================================================================

function drawPerformanceChart() {
    const canvas = document.getElementById('performance-chart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const data = gameState.netWorthHistory;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (data.length < 2) {
        // Draw baseline
        ctx.strokeStyle = '#333';
        ctx.beginPath();
        ctx.moveTo(0, canvas.height / 2);
        ctx.lineTo(canvas.width, canvas.height / 2);
        ctx.stroke();
        return;
    }

    const padding = 10;
    const chartWidth = canvas.width - padding * 2;
    const chartHeight = canvas.height - padding * 2;

    const minValue = Math.min(...data) * 0.95;
    const maxValue = Math.max(...data) * 1.05;
    const range = maxValue - minValue || 1;

    // Draw baseline (starting value)
    const baselineY = padding + chartHeight - ((10000 - minValue) / range) * chartHeight;
    ctx.strokeStyle = '#444';
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(padding, baselineY);
    ctx.lineTo(canvas.width - padding, baselineY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw performance line
    const lastValue = data[data.length - 1];
    const isPositive = lastValue >= 10000;

    ctx.strokeStyle = isPositive ? '#00ff00' : '#ff4444';
    ctx.lineWidth = 2;
    ctx.beginPath();

    data.forEach((value, index) => {
        const x = padding + (index / (data.length - 1)) * chartWidth;
        const y = padding + chartHeight - ((value - minValue) / range) * chartHeight;

        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });

    ctx.stroke();

    // Fill area under/over baseline
    ctx.globalAlpha = 0.1;
    ctx.fillStyle = isPositive ? '#00ff00' : '#ff4444';
    ctx.beginPath();

    data.forEach((value, index) => {
        const x = padding + (index / (data.length - 1)) * chartWidth;
        const y = padding + chartHeight - ((value - minValue) / range) * chartHeight;

        if (index === 0) {
            ctx.moveTo(x, baselineY);
            ctx.lineTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });

    ctx.lineTo(canvas.width - padding, baselineY);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = 1;

    // Update label
    document.getElementById('graph-label-end').textContent = `Turn ${data.length}`;
}

// ============================================================================
// Stock Price Chart
// ============================================================================

function showStockChart(companyName) {
    const company = gameState.companies.find(c => c.name === companyName);
    if (!company) return;

    // Update modal header info
    document.getElementById('chart-company-name').textContent = company.name;
    document.getElementById('chart-sector').textContent = company.sector;
    document.getElementById('chart-current-price').textContent = `$${company.price.toFixed(2)}`;

    const changeEl = document.getElementById('chart-change');
    const changeSign = company.change_pct >= 0 ? '+' : '';
    changeEl.textContent = `${changeSign}${company.change_pct.toFixed(2)}%`;
    changeEl.className = `chart-change ${company.change_pct >= 0 ? 'positive' : 'negative'}`;

    // Update stats
    document.getElementById('chart-rsi').textContent = company.rsi.toFixed(0);
    document.getElementById('chart-momentum').textContent = `${company.momentum >= 0 ? '+' : ''}${company.momentum.toFixed(2)}%`;
    document.getElementById('chart-beta').textContent = company.beta.toFixed(2);
    document.getElementById('chart-volume').textContent = company.volume.toFixed(2);

    // Store selected company for quick trade buttons
    gameState.chartCompany = companyName;

    // Render the chart
    renderStockChart(company);

    // Show modal
    document.getElementById('chart-modal').classList.remove('hidden');
}

function renderStockChart(company) {
    const ctx = document.getElementById('stock-price-chart').getContext('2d');

    // Destroy existing chart if it exists
    if (stockChart) {
        stockChart.destroy();
    }

    const priceHistory = company.price_history || [company.price];
    const volumeHistory = company.volume_history || [1];
    const labels = priceHistory.map((_, i) => `T${i + 1}`);

    // Calculate price change colors for each segment
    const priceColors = [];
    const borderColors = [];
    for (let i = 0; i < priceHistory.length; i++) {
        if (i === 0) {
            priceColors.push('rgba(0, 170, 255, 0.5)');
            borderColors.push('rgba(0, 170, 255, 1)');
        } else {
            const isUp = priceHistory[i] >= priceHistory[i - 1];
            priceColors.push(isUp ? 'rgba(0, 255, 0, 0.5)' : 'rgba(255, 68, 68, 0.5)');
            borderColors.push(isUp ? 'rgba(0, 255, 0, 1)' : 'rgba(255, 68, 68, 1)');
        }
    }

    // Determine if overall trend is positive
    const startPrice = priceHistory[0];
    const endPrice = priceHistory[priceHistory.length - 1];
    const isPositive = endPrice >= startPrice;
    const lineColor = isPositive ? 'rgba(0, 255, 0, 1)' : 'rgba(255, 68, 68, 1)';
    const fillColor = isPositive ? 'rgba(0, 255, 0, 0.1)' : 'rgba(255, 68, 68, 0.1)';

    stockChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Price',
                    data: priceHistory,
                    borderColor: lineColor,
                    backgroundColor: fillColor,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    pointRadius: priceHistory.length > 20 ? 0 : 3,
                    pointHoverRadius: 5,
                    pointBackgroundColor: lineColor,
                    yAxisID: 'y'
                },
                {
                    label: 'Volume',
                    data: volumeHistory,
                    type: 'bar',
                    backgroundColor: 'rgba(255, 153, 0, 0.3)',
                    borderColor: 'rgba(255, 153, 0, 0.8)',
                    borderWidth: 1,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#888',
                        font: {
                            family: "'Consolas', 'Monaco', monospace",
                            size: 11
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(10, 10, 10, 0.9)',
                    titleColor: '#ff9900',
                    bodyColor: '#fff',
                    borderColor: '#ff9900',
                    borderWidth: 1,
                    titleFont: {
                        family: "'Consolas', 'Monaco', monospace"
                    },
                    bodyFont: {
                        family: "'Consolas', 'Monaco', monospace"
                    },
                    callbacks: {
                        label: function(context) {
                            if (context.dataset.label === 'Price') {
                                return `Price: $${context.parsed.y.toFixed(2)}`;
                            } else {
                                return `Volume: ${context.parsed.y.toFixed(2)}x`;
                            }
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(51, 51, 51, 0.5)'
                    },
                    ticks: {
                        color: '#666',
                        font: {
                            family: "'Consolas', 'Monaco', monospace",
                            size: 10
                        },
                        maxTicksLimit: 10
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    grid: {
                        color: 'rgba(51, 51, 51, 0.5)'
                    },
                    ticks: {
                        color: '#888',
                        font: {
                            family: "'Consolas', 'Monaco', monospace",
                            size: 11
                        },
                        callback: function(value) {
                            return '$' + value.toFixed(0);
                        }
                    },
                    title: {
                        display: true,
                        text: 'Price ($)',
                        color: '#888'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: {
                        drawOnChartArea: false,
                    },
                    ticks: {
                        color: '#ff9900',
                        font: {
                            family: "'Consolas', 'Monaco', monospace",
                            size: 10
                        }
                    },
                    title: {
                        display: true,
                        text: 'Volume',
                        color: '#ff9900'
                    },
                    min: 0,
                    max: Math.max(...volumeHistory) * 3 // Make volume bars shorter
                }
            }
        }
    });
}

function closeStockChart() {
    document.getElementById('chart-modal').classList.add('hidden');
    if (stockChart) {
        stockChart.destroy();
        stockChart = null;
    }
}

// ============================================================================
// Options Trading
// ============================================================================

async function showOptionsModal(companyName) {
    if (!gameState.gameId) return;

    try {
        const chain = await getOptionChain(gameState.gameId, companyName);
        currentOptionChain = chain;

        // Update header
        document.getElementById('options-company-name').textContent = companyName;
        document.getElementById('options-current-price').textContent = `$${chain.current_price.toFixed(2)}`;

        // Populate strike select
        const strikeSelect = document.getElementById('option-strike-select');
        strikeSelect.innerHTML = '<option value="">Select strike...</option>';
        chain.calls.forEach(call => {
            const option = document.createElement('option');
            option.value = call.strike;
            option.textContent = `$${call.strike.toFixed(2)}`;
            if (Math.abs(call.strike - chain.current_price) < 1) {
                option.textContent += ' (ATM)';
            }
            strikeSelect.appendChild(option);
        });

        // Populate calls list
        const callsList = document.getElementById('calls-list');
        callsList.innerHTML = chain.calls.map(call => `
            <div class="option-row ${call.itm ? 'itm' : 'otm'}" data-strike="${call.strike}" data-type="call">
                <span class="option-premium">$${call.premium.toFixed(2)}</span>
                <span class="option-cost">($${call.total_cost.toFixed(0)}/contract)</span>
            </div>
        `).join('');

        // Populate strikes list
        const strikesList = document.getElementById('strikes-list');
        strikesList.innerHTML = chain.calls.map(call => {
            const isAtm = Math.abs(call.strike - chain.current_price) < chain.current_price * 0.03;
            return `<div class="strike-row ${isAtm ? 'atm' : ''}">${call.strike.toFixed(2)}</div>`;
        }).join('');

        // Populate puts list
        const putsList = document.getElementById('puts-list');
        putsList.innerHTML = chain.puts.map(put => `
            <div class="option-row ${put.itm ? 'itm' : 'otm'}" data-strike="${put.strike}" data-type="put">
                <span class="option-premium">$${put.premium.toFixed(2)}</span>
                <span class="option-cost">($${put.total_cost.toFixed(0)}/contract)</span>
            </div>
        `).join('');

        // Add click handlers to option rows
        document.querySelectorAll('.option-row').forEach(row => {
            row.addEventListener('click', () => {
                document.getElementById('option-type-select').value = row.dataset.type;
                document.getElementById('option-strike-select').value = row.dataset.strike;
                updateOptionCostPreview();
            });
        });

        // Show modal
        document.getElementById('options-modal').classList.remove('hidden');
        updateOptionCostPreview();

    } catch (error) {
        showTradeMessage(`Failed to load options: ${error.message}`, true);
    }
}

function closeOptionsModal() {
    document.getElementById('options-modal').classList.add('hidden');
    currentOptionChain = null;
}

function updateOptionCostPreview() {
    const strikeSelect = document.getElementById('option-strike-select');
    const typeSelect = document.getElementById('option-type-select');
    const contractsInput = document.getElementById('option-contracts-input');
    const costDisplay = document.getElementById('option-total-cost');

    if (!currentOptionChain || !strikeSelect.value) {
        costDisplay.textContent = '$0.00';
        return;
    }

    const strike = parseFloat(strikeSelect.value);
    const contracts = parseInt(contractsInput.value) || 1;
    const optionType = typeSelect.value;

    const optionList = optionType === 'call' ? currentOptionChain.calls : currentOptionChain.puts;
    const option = optionList.find(o => o.strike === strike);

    if (option) {
        const totalCost = option.total_cost * contracts;
        costDisplay.textContent = `$${totalCost.toFixed(2)}`;
    } else {
        costDisplay.textContent = '$0.00';
    }
}

async function handleBuyOption() {
    if (!gameState.gameId || !currentOptionChain) return;

    const company = currentOptionChain.company;
    const optionType = document.getElementById('option-type-select').value;
    const strikePrice = parseFloat(document.getElementById('option-strike-select').value);
    const contracts = parseInt(document.getElementById('option-contracts-input').value);

    if (!strikePrice) {
        showTradeMessage('Please select a strike price', true);
        return;
    }

    if (!contracts || contracts < 1) {
        showTradeMessage('Please enter valid number of contracts', true);
        return;
    }

    try {
        const response = await buyOption(gameState.gameId, company, optionType, strikePrice, contracts);

        updateFullUI(response.state);
        showTradeMessage(response.message, !response.success);

        if (response.success) {
            closeOptionsModal();
        }
    } catch (error) {
        showTradeMessage(`Failed to buy option: ${error.message}`, true);
    }
}

function updateOptionsPositions(options) {
    const container = document.getElementById('options-content');
    const section = document.getElementById('options-section');

    if (!options || options.length === 0) {
        container.innerHTML = '<p class="empty-message">No options positions</p>';
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');

    container.innerHTML = options.map(option => {
        const typeClass = option.type;
        const pnlClass = option.pnl >= 0 ? 'positive' : 'negative';
        const pnlSign = option.pnl >= 0 ? '+' : '';
        const itmClass = option.in_the_money ? 'itm' : 'otm';

        return `
            <div class="option-position-item ${typeClass}" data-option-id="${option.id}">
                <div class="option-position-header">
                    <span class="option-type-badge ${typeClass}">${option.type.toUpperCase()}</span>
                    <span class="option-company">${option.company}</span>
                    <span class="option-strike">@ $${option.strike_price.toFixed(2)}</span>
                    <span class="option-itm-badge ${itmClass}">${option.in_the_money ? 'ITM' : 'OTM'}</span>
                </div>
                <div class="option-position-details">
                    <span class="option-contracts">${option.contracts} contract${option.contracts > 1 ? 's' : ''}</span>
                    <span class="option-expiry">Expires: T${option.expiry_turn} (${option.turns_remaining} turns)</span>
                    <span class="option-value">Value: $${option.current_value.toFixed(2)}</span>
                    <span class="option-pnl ${pnlClass}">P/L: ${pnlSign}$${option.pnl.toFixed(2)}</span>
                </div>
                <div class="option-position-actions">
                    <button class="option-action-btn exercise-btn" data-option-id="${option.id}"
                            ${!option.in_the_money ? 'disabled title="Option is out of the money"' : ''}>
                        EXERCISE
                    </button>
                    <button class="option-action-btn sell-btn" data-option-id="${option.id}">
                        SELL
                    </button>
                </div>
            </div>
        `;
    }).join('');

    // Add event handlers
    container.querySelectorAll('.exercise-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const optionId = parseInt(btn.dataset.optionId);
            await handleExerciseOption(optionId);
        });
    });

    container.querySelectorAll('.sell-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const optionId = parseInt(btn.dataset.optionId);
            await handleSellOption(optionId);
        });
    });
}

async function handleExerciseOption(optionId) {
    if (!gameState.gameId) return;

    try {
        const response = await exerciseOption(gameState.gameId, optionId);
        updateFullUI(response.state);
        showTradeMessage(response.message, !response.success);
    } catch (error) {
        showTradeMessage(`Failed to exercise option: ${error.message}`, true);
    }
}

async function handleSellOption(optionId) {
    if (!gameState.gameId) return;

    try {
        const response = await sellOption(gameState.gameId, optionId);
        updateFullUI(response.state);
        showTradeMessage(response.message, !response.success);
    } catch (error) {
        showTradeMessage(`Failed to sell option: ${error.message}`, true);
    }
}

// ============================================================================
// Trade History
// ============================================================================

function addTradeToHistory(action, company, shares, price, turn) {
    const trade = {
        turn,
        action: action.toUpperCase(),
        company,
        shares,
        price,
        timestamp: new Date().toISOString()
    };

    gameState.tradeHistory.unshift(trade); // Add to beginning

    // Keep only last 50 trades
    if (gameState.tradeHistory.length > 50) {
        gameState.tradeHistory.pop();
    }

    updateTradeHistory();
}

function updateTradeHistory() {
    const container = document.getElementById('history-content');
    if (!container) return;

    if (gameState.tradeHistory.length === 0) {
        container.innerHTML = '<p class="empty-message">No trades yet</p>';
        return;
    }

    container.innerHTML = gameState.tradeHistory.slice(0, 10).map(trade => {
        const actionClass = trade.action.toLowerCase();
        return `
            <div class="trade-item">
                <div class="trade-info">
                    <span class="trade-action ${actionClass}">${trade.action}</span>
                    <span class="trade-details">T${trade.turn}: ${trade.shares} ${trade.company} @ $${trade.price.toFixed(2)}</span>
                </div>
            </div>
        `;
    }).join('');
}

// ============================================================================
// Achievements System
// ============================================================================

function checkAchievements(apiState = null, finalStats = null) {
    let newAchievements = [];

    for (const [id, achievement] of Object.entries(ACHIEVEMENTS)) {
        if (!gameState.achievements[id]) {
            try {
                if (achievement.check(gameState, apiState, finalStats)) {
                    gameState.achievements[id] = true;
                    newAchievements.push(achievement);
                }
            } catch (e) {
                // Achievement check failed, skip
            }
        }
    }

    // Show notifications for new achievements
    newAchievements.forEach((achievement, index) => {
        setTimeout(() => showAchievementNotification(achievement), index * 2000);
    });
}

function showAchievementNotification(achievement) {
    const notification = document.getElementById('achievement-notification');
    const nameElement = document.getElementById('achievement-name');

    if (!notification || !nameElement) return;

    nameElement.textContent = `${achievement.icon} ${achievement.title}`;
    notification.classList.remove('hidden');

    // Hide after 3 seconds
    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}

function updateAchievementsModal() {
    const container = document.getElementById('achievements-list');
    if (!container) return;

    container.innerHTML = Object.values(ACHIEVEMENTS).map(achievement => {
        const unlocked = gameState.achievements[achievement.id];
        return `
            <div class="achievement-item ${unlocked ? 'unlocked' : 'locked'}">
                <div class="achievement-icon">${unlocked ? achievement.icon : '🔒'}</div>
                <div class="achievement-title">${achievement.title}</div>
                <div class="achievement-desc">${achievement.description}</div>
            </div>
        `;
    }).join('');
}

function showTradeMessage(message, isError = false) {
    elements.tradeMessage.textContent = message;
    elements.tradeMessage.className = `trade-message ${isError ? 'error' : 'success'}`;
    
    // Clear after 5 seconds
    setTimeout(() => {
        elements.tradeMessage.textContent = '';
        elements.tradeMessage.className = 'trade-message';
    }, 5000);
}

function updatePendingOrders(orders) {
    const container = document.getElementById('pending-orders-content');
    const section = document.getElementById('pending-orders-section');

    if (!orders || orders.length === 0) {
        container.innerHTML = '<p class="empty-message">No pending orders</p>';
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');

    container.innerHTML = orders.map(order => {
        const orderTypeLabel = order.order_type.replace('_', ' ').toUpperCase();
        const actionClass = order.action.toLowerCase();
        const priceDirection = order.current_price > order.limit_price ? '↓' : '↑';
        const priceDiff = ((order.limit_price - order.current_price) / order.current_price * 100).toFixed(1);
        const priceDiffSign = priceDiff >= 0 ? '+' : '';

        return `
            <div class="order-item" data-order-id="${order.id}">
                <div class="order-header">
                    <span class="order-type ${order.order_type}">${orderTypeLabel}</span>
                    <span class="order-action ${actionClass}">${order.action.toUpperCase()}</span>
                    <span class="order-company">${order.company}</span>
                </div>
                <div class="order-details">
                    <span class="order-shares">${order.shares} shares</span>
                    <span class="order-prices">
                        Target: <span class="target-price">$${order.limit_price.toFixed(2)}</span>
                        ${priceDirection}
                        Current: <span class="current-price">$${order.current_price.toFixed(2)}</span>
                        <span class="price-diff">(${priceDiffSign}${priceDiff}%)</span>
                    </span>
                </div>
                <div class="order-meta">
                    <span class="order-created">Created T${order.created_turn} @ $${order.created_price.toFixed(2)}</span>
                    <button class="cancel-order-btn" data-order-id="${order.id}">✕ Cancel</button>
                </div>
            </div>
        `;
    }).join('');

    // Add cancel button handlers
    container.querySelectorAll('.cancel-order-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const orderId = parseInt(btn.dataset.orderId);
            await handleCancelOrder(orderId);
        });
    });
}

async function handleCancelOrder(orderId) {
    if (!gameState.gameId) return;

    try {
        const response = await cancelOrder(gameState.gameId, orderId);
        updateFullUI(response.state);
        showTradeMessage(response.message, !response.success);
    } catch (error) {
        showTradeMessage(`Failed to cancel order: ${error.message}`, true);
    }
}

function updateFullUI(state) {
    updateHeader(state);
    updateMarketTable(state.companies);
    updatePortfolio(state.portfolio);
    updateShortPositions(state.short_positions);
    updatePendingOrders(state.pending_orders || []);
    updateOptionsPositions(state.options_positions || []);
    updatePsychology(state.psychology);
    updateStats(state.player);
    updateNews(state.news);
}

// ============================================================================
// Game Actions
// ============================================================================

async function handleNewGame() {
    try {
        showLoading();
        const response = await startNewGame();

        gameState.gameId = response.game_id;
        gameState.netWorthHistory = [response.state.player.net_worth];
        gameState.tradeHistory = [];
        gameState.achievements = {};
        elements.gameIdDisplay.textContent = `Game ID: ${response.game_id}`;

        updateFullUI(response.state);
        drawPerformanceChart();
        updateTradeHistory();

        showGameScreen();
        showTradeMessage('New game started! Good luck!');
    } catch (error) {
        showError(`Failed to start new game: ${error.message}`);
    }
}

async function handleExecuteTrade() {
    if (!gameState.gameId) {
        showTradeMessage('No active game', true);
        return;
    }

    const company = elements.companySelect.value;
    const shares = parseInt(elements.sharesInput.value);
    const orderType = elements.orderTypeSelect.value;
    const limitPrice = parseFloat(elements.limitPriceInput.value);

    if (!company) {
        showTradeMessage('Please select a company', true);
        return;
    }

    if (!shares || shares <= 0) {
        showTradeMessage('Please enter a valid number of shares', true);
        return;
    }

    // For non-market orders, validate limit price
    if (orderType !== 'market') {
        if (!limitPrice || limitPrice <= 0) {
            showTradeMessage('Please enter a valid limit price', true);
            return;
        }

        // Place limit/stop/take-profit order
        try {
            const response = await placeOrder(
                gameState.gameId,
                orderType,
                gameState.selectedAction,
                company,
                shares,
                limitPrice
            );

            updateFullUI(response.state);
            showTradeMessage(response.message, !response.success);

            if (response.success) {
                // Reset inputs
                elements.sharesInput.value = '1';
                elements.limitPriceInput.value = '';
                elements.orderTypeSelect.value = 'market';
                document.querySelector('.limit-price-group').classList.add('hidden');
                updateOrderPreview();
            }
        } catch (error) {
            showTradeMessage(`Order failed: ${error.message}`, true);
        }
        return;
    }

    // Market order - execute immediately
    try {
        // Get current price before trade
        const companyData = gameState.companies.find(c => c.name === company);
        const price = companyData ? companyData.price : 0;

        const response = await executeAction(
            gameState.gameId,
            gameState.selectedAction,
            company,
            shares
        );

        if (response.success) {
            // Add to trade history
            addTradeToHistory(
                gameState.selectedAction,
                company,
                shares,
                price,
                response.state.turn
            );

            // Check for contrarian achievement (buying in fear)
            if (gameState.selectedAction === 'buy' && response.state.psychology.fear_greed_index < 25) {
                gameState.achievements.fear_buyer_triggered = true;
            }

            // Check achievements
            checkAchievements(response.state);
        }

        updateFullUI(response.state);
        showTradeMessage(response.message, !response.success);

        // Reset shares input
        elements.sharesInput.value = '1';
        updateOrderPreview();
    } catch (error) {
        showTradeMessage(`Trade failed: ${error.message}`, true);
    }
}

async function handleNextTurn() {
    if (!gameState.gameId) {
        showTradeMessage('No active game', true);
        return;
    }

    try {
        const response = await advanceTurn(gameState.gameId);

        // Track net worth history
        gameState.netWorthHistory.push(response.state.player.net_worth);

        updateFullUI(response.state);
        drawPerformanceChart();

        // Show news in trade message briefly
        if (response.news && response.news.length > 0) {
            showTradeMessage(`Turn ${response.state.turn}: ${response.news[0]}`);
        }

        // Check achievements
        checkAchievements(response.state, response.game_over ? response.final_stats : null);

        // Check for game over
        if (response.game_over) {
            showGameOver(response.final_stats);
        }
    } catch (error) {
        showTradeMessage(`Failed to advance turn: ${error.message}`, true);
    }
}

async function handleSaveGame() {
    if (!gameState.gameId) {
        showTradeMessage('No active game to save', true);
        return;
    }
    
    try {
        const response = await saveGame(gameState.gameId);
        showTradeMessage(response.message);
    } catch (error) {
        showTradeMessage(`Failed to save: ${error.message}`, true);
    }
}

async function handleLoadGame(slot) {
    try {
        showLoading();
        const response = await loadGame(slot);

        if (!response.success) {
            showError(response.message);
            return;
        }

        gameState.gameId = response.game_id;
        gameState.netWorthHistory = [response.state.player.net_worth];
        gameState.tradeHistory = [];
        gameState.achievements = {};
        elements.gameIdDisplay.textContent = `Game ID: ${response.game_id}`;

        updateFullUI(response.state);
        drawPerformanceChart();
        updateTradeHistory();
        showGameScreen();
        showTradeMessage(`Game loaded from '${slot}'`);
    } catch (error) {
        showError(`Failed to load game: ${error.message}`);
    }
}

async function handleShowSaves() {
    try {
        const response = await getSavesList();
        const container = document.getElementById('saves-container');
        
        if (!response.saves || response.saves.length === 0) {
            container.innerHTML = '<p class="empty-message">No saved games found</p>';
        } else {
            container.innerHTML = response.saves.map(save => `
                <div class="save-item" data-slot="${save.slot}">
                    <span class="save-name">${save.slot}</span>
                    <span class="save-info">Turn ${save.turn} | ${save.timestamp || 'Unknown time'}</span>
                </div>
            `).join('');
            
            // Add click handlers
            container.querySelectorAll('.save-item').forEach(item => {
                item.addEventListener('click', () => handleLoadGame(item.dataset.slot));
            });
        }
        
        document.getElementById('saves-list').classList.remove('hidden');
    } catch (error) {
        showError(`Failed to load saves: ${error.message}`);
    }
}

// ============================================================================
// Screen Management
// ============================================================================

function showLoading() {
    document.getElementById('loading-screen').classList.remove('hidden');
    document.getElementById('start-screen').classList.add('hidden');
    document.getElementById('game-container').classList.add('hidden');
}

function showStartScreen() {
    document.getElementById('loading-screen').classList.add('hidden');
    document.getElementById('start-screen').classList.remove('hidden');
    document.getElementById('game-container').classList.add('hidden');
    document.getElementById('saves-list').classList.add('hidden');
}

function showGameScreen() {
    document.getElementById('loading-screen').classList.add('hidden');
    document.getElementById('start-screen').classList.add('hidden');
    document.getElementById('game-container').classList.remove('hidden');
}

function showGameOver(stats) {
    const modal = document.getElementById('game-over-modal');
    const container = document.getElementById('final-stats');
    
    container.innerHTML = `
        <div class="final-stat-row">
            <span class="label">Final Net Worth:</span>
            <span class="value ${stats.total_return_pct >= 0 ? 'positive' : 'negative'}">${formatCurrency(stats.final_net_worth)}</span>
        </div>
        <div class="final-stat-row">
            <span class="label">Total Return:</span>
            <span class="value ${stats.total_return_pct >= 0 ? 'positive' : 'negative'}">${stats.total_return_pct >= 0 ? '+' : ''}${stats.total_return_pct.toFixed(2)}%</span>
        </div>
        <div class="final-stat-row">
            <span class="label">Market Return:</span>
            <span class="value">${stats.market_return_pct >= 0 ? '+' : ''}${stats.market_return_pct.toFixed(2)}%</span>
        </div>
        <div class="final-stat-row">
            <span class="label">Alpha (vs Market):</span>
            <span class="value ${stats.alpha >= 0 ? 'positive' : 'negative'}">${stats.alpha >= 0 ? '+' : ''}${stats.alpha.toFixed(2)}%</span>
        </div>
        <div class="final-stat-row">
            <span class="label">Sharpe Ratio:</span>
            <span class="value">${stats.sharpe_ratio.toFixed(2)}</span>
        </div>
        <div class="final-stat-row">
            <span class="label">Max Drawdown:</span>
            <span class="value negative">${stats.max_drawdown.toFixed(2)}%</span>
        </div>
        <div class="final-stat-row">
            <span class="label">Total Trades:</span>
            <span class="value">${stats.trade_count}</span>
        </div>
        <div class="final-stat-row">
            <span class="label">Total Fees:</span>
            <span class="value">${formatCurrency(stats.total_fees_paid)}</span>
        </div>
        <div class="rating-display">
            <div class="rating">${stats.rating}</div>
            <div class="message">${stats.message}</div>
        </div>
    `;
    
    modal.classList.remove('hidden');
}

function showError(message) {
    document.getElementById('modal-message').textContent = message;
    document.getElementById('message-modal').classList.remove('hidden');
}

// ============================================================================
// Utility Functions
// ============================================================================

function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2
    }).format(value);
}

// ============================================================================
// Event Handlers Setup
// ============================================================================

function setupEventHandlers() {
    // Start screen buttons
    document.getElementById('btn-start-new').addEventListener('click', handleNewGame);
    document.getElementById('btn-start-load').addEventListener('click', handleShowSaves);

    // Trade action buttons
    document.querySelectorAll('.trade-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.trade-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            gameState.selectedAction = btn.dataset.action;
        });
    });

    // Trade inputs
    elements.companySelect.addEventListener('change', (e) => {
        selectCompany(e.target.value);
    });

    elements.sharesInput.addEventListener('input', updateOrderPreview);

    // Order type select - show/hide limit price input
    elements.orderTypeSelect.addEventListener('change', (e) => {
        const orderType = e.target.value;
        const limitPriceGroup = document.querySelector('.limit-price-group');
        const executeBtn = document.getElementById('btn-execute');

        if (orderType === 'market') {
            limitPriceGroup.classList.add('hidden');
            executeBtn.textContent = 'EXECUTE TRADE';
        } else {
            limitPriceGroup.classList.remove('hidden');
            executeBtn.textContent = 'PLACE ORDER';

            // Pre-fill with suggested price based on order type and action
            const company = gameState.companies.find(c => c.name === elements.companySelect.value);
            if (company) {
                let suggestedPrice = company.price;
                const action = gameState.selectedAction;

                if (orderType === 'limit') {
                    // Limit buy: below current, Limit sell/short: above current
                    if (action === 'buy' || action === 'cover') {
                        suggestedPrice = company.price * 0.95; // 5% below
                    } else {
                        suggestedPrice = company.price * 1.05; // 5% above
                    }
                } else if (orderType === 'stop_loss') {
                    // Stop loss sell: below current, Stop loss cover: above current
                    if (action === 'sell') {
                        suggestedPrice = company.price * 0.90; // 10% below
                    } else if (action === 'cover') {
                        suggestedPrice = company.price * 1.10; // 10% above
                    }
                } else if (orderType === 'take_profit') {
                    // Take profit sell: above current, Take profit cover: below current
                    if (action === 'sell') {
                        suggestedPrice = company.price * 1.15; // 15% above
                    } else if (action === 'cover') {
                        suggestedPrice = company.price * 0.85; // 15% below
                    }
                }

                elements.limitPriceInput.value = suggestedPrice.toFixed(2);
            }
        }
        updateOrderPreview();
    });

    elements.limitPriceInput.addEventListener('input', updateOrderPreview);

    // Trade execution buttons
    document.getElementById('btn-execute').addEventListener('click', handleExecuteTrade);
    document.getElementById('btn-next-turn').addEventListener('click', handleNextTurn);

    // Footer buttons
    document.getElementById('btn-new-game').addEventListener('click', () => {
        if (confirm('Start a new game? Current progress will be lost unless saved.')) {
            handleNewGame();
        }
    });
    document.getElementById('btn-save').addEventListener('click', handleSaveGame);
    document.getElementById('btn-load').addEventListener('click', () => {
        handleShowSaves();
        showStartScreen();
    });

    // Help modal
    document.getElementById('btn-help').addEventListener('click', () => {
        document.getElementById('help-modal').classList.remove('hidden');
    });
    document.getElementById('btn-help-close').addEventListener('click', () => {
        document.getElementById('help-modal').classList.add('hidden');
    });

    // Achievements modal
    document.getElementById('btn-achievements').addEventListener('click', () => {
        updateAchievementsModal();
        document.getElementById('achievements-modal').classList.remove('hidden');
    });
    document.getElementById('btn-achievements-close').addEventListener('click', () => {
        document.getElementById('achievements-modal').classList.add('hidden');
    });

    // Stock chart modal
    document.getElementById('btn-chart-close').addEventListener('click', closeStockChart);
    document.getElementById('btn-chart-buy').addEventListener('click', () => {
        if (gameState.chartCompany) {
            selectCompany(gameState.chartCompany);
            document.getElementById('btn-buy').click();
            closeStockChart();
        }
    });
    document.getElementById('btn-chart-short').addEventListener('click', () => {
        if (gameState.chartCompany) {
            selectCompany(gameState.chartCompany);
            document.getElementById('btn-short').click();
            closeStockChart();
        }
    });
    document.getElementById('btn-chart-options').addEventListener('click', () => {
        if (gameState.chartCompany) {
            closeStockChart();
            showOptionsModal(gameState.chartCompany);
        }
    });

    // Options modal
    document.getElementById('btn-options-close').addEventListener('click', closeOptionsModal);
    document.getElementById('btn-buy-option').addEventListener('click', handleBuyOption);
    document.getElementById('option-type-select').addEventListener('change', updateOptionCostPreview);
    document.getElementById('option-strike-select').addEventListener('change', updateOptionCostPreview);
    document.getElementById('option-contracts-input').addEventListener('input', updateOptionCostPreview);

    // Game over modal
    document.getElementById('btn-play-again').addEventListener('click', () => {
        document.getElementById('game-over-modal').classList.add('hidden');
        handleNewGame();
    });

    // Message modal
    document.getElementById('btn-modal-close').addEventListener('click', () => {
        document.getElementById('message-modal').classList.add('hidden');
        showStartScreen();
    });

    // Close modals on backdrop click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
            }
        });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Close modals on Escape
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal:not(.hidden)').forEach(modal => {
                modal.classList.add('hidden');
            });
            return;
        }

        // Only handle other shortcuts when game is active and no modal is open
        if (!gameState.gameId) return;
        if (document.querySelector('.modal:not(.hidden)')) return;

        switch (e.key.toLowerCase()) {
            case 'enter':
                if (e.ctrlKey || e.metaKey) {
                    handleNextTurn();
                } else if (elements.companySelect.value && elements.sharesInput.value) {
                    handleExecuteTrade();
                }
                break;
            case 'b':
                if (!e.ctrlKey && !e.metaKey) {
                    document.getElementById('btn-buy').click();
                }
                break;
            case 's':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    handleSaveGame();
                } else {
                    document.getElementById('btn-sell').click();
                }
                break;
            case 'h':
                if (!e.ctrlKey && !e.metaKey) {
                    document.getElementById('btn-short').click();
                }
                break;
            case 'c':
                if (!e.ctrlKey && !e.metaKey) {
                    document.getElementById('btn-cover').click();
                }
                break;
            case '?':
                document.getElementById('help-modal').classList.remove('hidden');
                break;
        }
    });
}

// ============================================================================
// Initialization
// ============================================================================

function cacheElements() {
    elements = {
        currentTurn: document.getElementById('current-turn'),
        maxTurns: document.getElementById('max-turns'),
        turnProgress: document.getElementById('turn-progress'),
        regimeDisplay: document.getElementById('regime-display'),
        regimeEmoji: document.getElementById('regime-emoji'),
        marketTbody: document.getElementById('market-tbody'),
        portfolioContent: document.getElementById('portfolio-content'),
        shortsContent: document.getElementById('shorts-content'),
        fearGreedBar: document.getElementById('fear-greed-bar'),
        fearGreedValue: document.getElementById('fear-greed-value'),
        herdBar: document.getElementById('herd-bar'),
        herdValue: document.getElementById('herd-value'),
        complacencyBar: document.getElementById('complacency-bar'),
        complacencyValue: document.getElementById('complacency-value'),
        sentimentEmoji: document.getElementById('sentiment-emoji'),
        statCash: document.getElementById('stat-cash'),
        statPortfolio: document.getElementById('stat-portfolio'),
        statNetworth: document.getElementById('stat-networth'),
        statReturn: document.getElementById('stat-return'),
        statSharpe: document.getElementById('stat-sharpe'),
        statDrawdown: document.getElementById('stat-drawdown'),
        statTrades: document.getElementById('stat-trades'),
        statFees: document.getElementById('stat-fees'),
        statMargin: document.getElementById('stat-margin'),
        newsContent: document.getElementById('news-content'),
        companySelect: document.getElementById('company-select'),
        sharesInput: document.getElementById('shares-input'),
        orderTypeSelect: document.getElementById('order-type-select'),
        limitPriceInput: document.getElementById('limit-price-input'),
        orderCost: document.getElementById('order-cost'),
        tradeMessage: document.getElementById('trade-message'),
        gameIdDisplay: document.getElementById('game-id-display')
    };
}

function init() {
    cacheElements();
    setupEventHandlers();
    
    // Show start screen after a brief delay
    setTimeout(() => {
        showStartScreen();
    }, 500);
}

// Start the application when DOM is ready
document.addEventListener('DOMContentLoaded', init);
