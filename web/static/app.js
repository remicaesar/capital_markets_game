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
            <td class="company-name">${company.name}</td>
            <td>${company.sector}</td>
            <td>$${company.price.toFixed(2)}</td>
            <td class="${changeClass}">${changeSign}${company.change_pct.toFixed(2)}%</td>
            <td>${company.rsi.toFixed(0)}</td>
            <td class="${company.momentum >= 0 ? 'positive' : 'negative'}">${company.momentum >= 0 ? '+' : ''}${company.momentum.toFixed(2)}%</td>
            <td>${company.volume.toFixed(2)}</td>
            <td>${company.beta.toFixed(2)}</td>
            <td>${company.trend}</td>
        `;
        
        // Click to select company
        row.addEventListener('click', () => selectCompany(company.name));
        
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

function updateFullUI(state) {
    updateHeader(state);
    updateMarketTable(state.companies);
    updatePortfolio(state.portfolio);
    updateShortPositions(state.short_positions);
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

    if (!company) {
        showTradeMessage('Please select a company', true);
        return;
    }

    if (!shares || shares <= 0) {
        showTradeMessage('Please enter a valid number of shares', true);
        return;
    }

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
