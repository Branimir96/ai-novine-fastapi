// Financial Widget JavaScript - app/static/js/financial-widget.js
// Only runs when financial widget is present on the page

console.log('📈 Financial widget script loaded');

// Initialize only if widget exists
if (document.querySelector('.financial-widget')) {
    
    console.log('📈 Financial widget detected, initializing...');
    
    function updateFinancialTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('hr-HR', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        const lastUpdateEl = document.getElementById('lastUpdate');
        if (lastUpdateEl) {
            lastUpdateEl.textContent = timeString;
        }
    }

    function updateFinancialDisplay(symbol, data) {
        const symbolLower = symbol.toLowerCase();
        const priceElement = document.getElementById(`${symbolLower}-price`);
        const changeElement = document.getElementById(`${symbolLower}-change`);
        const priceItem = document.querySelector(`[data-symbol="${symbol}"]`);
        
        if (priceElement && changeElement && data) {
            priceItem.classList.remove('loading');
            
            priceElement.textContent = data.formatted_price;
            changeElement.textContent = data.formatted_change;
            changeElement.className = `change ${data.change_percent >= 0 ? 'positive' : 'negative'}`;
            
            priceItem.classList.add('updated');
            setTimeout(() => {
                priceItem.classList.remove('updated');
            }, 800);
            
            console.log(`✅ Updated ${symbol}: ${data.formatted_price} (${data.formatted_change})`);
        }
    }

    function showFinancialError(symbol) {
        const symbolLower = symbol.toLowerCase();
        const priceElement = document.getElementById(`${symbolLower}-price`);
        const changeElement = document.getElementById(`${symbolLower}-change`);
        const priceItem = document.querySelector(`[data-symbol="${symbol}"]`);
        
        if (priceElement && changeElement) {
            priceItem.classList.remove('loading');
            priceElement.textContent = 'Error';
            changeElement.textContent = '-';
            changeElement.className = 'change';
            console.error(`❌ Error displaying ${symbol}`);
        }
    }

    async function fetchFinancialPrices() {
        console.log('🚀 Fetching financial prices...');
        
        // Show loading for all items
        document.querySelectorAll('.price-item').forEach(item => {
            item.classList.add('loading');
        });
        
        try {
            // Use the batch API endpoint for better performance
            const response = await fetch('/api/prices/all');
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('📊 API Response:', data);
            
            if (data.success) {
                // Update stock prices
                Object.entries(data.stocks || {}).forEach(([symbol, stockData]) => {
                    if (stockData.error) {
                        showFinancialError(symbol);
                        console.warn(`⚠️ Error for ${symbol}:`, stockData.error);
                    } else {
                        updateFinancialDisplay(symbol, stockData);
                    }
                });
                
                // Update crypto prices
                Object.entries(data.crypto || {}).forEach(([symbol, cryptoData]) => {
                    if (cryptoData.error) {
                        showFinancialError(symbol);
                        console.warn(`⚠️ Error for crypto ${symbol}:`, cryptoData.error);
                    } else {
                        updateFinancialDisplay(symbol, cryptoData);
                    }
                });
                
                // Mock commodities data (since Alpha Vantage doesn't have free commodities)
                const mockCommodities = {
                    'GOLD': { formatted_price: '$2,035', formatted_change: '-0.3%', change_percent: -0.3 },
                    'OIL': { formatted_price: '$78.50', formatted_change: '+1.5%', change_percent: 1.5 }
                };
                
                Object.entries(mockCommodities).forEach(([symbol, commodityData]) => {
                    updateFinancialDisplay(symbol, commodityData);
                });
                
                updateFinancialTime();
                console.log('✅ Financial prices updated successfully');
                
            } else {
                throw new Error('API returned unsuccessful response');
            }
            
        } catch (error) {
            console.error('❌ Failed to fetch financial prices:', error);
            
            // Show error for all items
            document.querySelectorAll('.price-item').forEach(item => {
                showFinancialError(item.dataset.symbol);
            });
        }
    }

    // The refresh function that was causing the error
    function refreshFinancialPrices() {
        const refreshBtn = document.querySelector('.refresh-btn');
        if (!refreshBtn) return;
        
        const originalText = refreshBtn.innerHTML;
        
        refreshBtn.innerHTML = '⏳ Učitavam...';
        refreshBtn.disabled = true;
        
        fetchFinancialPrices()
            .then(() => {
                refreshBtn.innerHTML = '✅ Osvježeno!';
                setTimeout(() => {
                    refreshBtn.innerHTML = originalText;
                    refreshBtn.disabled = false;
                }, 2000);
            })
            .catch((error) => {
                console.error('Refresh error:', error);
                refreshBtn.innerHTML = '❌ Greška';
                setTimeout(() => {
                    refreshBtn.innerHTML = originalText;
                    refreshBtn.disabled = false;
                }, 3000);
            });
    }

    // Make the function globally available
    window.refreshFinancialPrices = refreshFinancialPrices;

    // Initialize financial widget
    function initFinancialWidget() {
        console.log('📈 Initializing financial widget on Ekonomija page...');
        updateFinancialTime();
        fetchFinancialPrices();
        
        // Auto-refresh every 10 minutes
        setInterval(fetchFinancialPrices, 10 * 60 * 1000);
        
        console.log('✅ Financial widget initialized');
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFinancialWidget);
    } else {
        initFinancialWidget();
    }
    
    // Handle page visibility for financial widget
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible') {
            // Refresh financial data when page becomes visible
            setTimeout(fetchFinancialPrices, 1000);
        }
    });

} else {
    console.log('📈 No financial widget found on this page');
}