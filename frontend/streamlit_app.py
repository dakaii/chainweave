"""ChainWeave Streamlit Dashboard.

Real-time NFT analytics dashboard with:
- Global market overview
- Collection performance tracking
- Whale activity monitoring
- Interactive visualizations
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import asyncio
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json

# Add backend to path
sys.path.append('../backend/src')

from services.dashboard_data_service import DashboardDataService
from services.cache_manager import CacheManager

# Page configuration
st.set_page_config(
    page_title="ChainWeave - NFT Analytics",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    .whale-alert {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 4px;
        padding: 0.75rem;
        margin: 0.5rem 0;
    }
    .whale-alert.high {
        background: #f8d7da;
        border-color: #f5c6cb;
    }
    .whale-alert.critical {
        background: #d1ecf1;
        border-color: #bee5eb;
    }
    .collection-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: white;
    }
</style>
""", unsafe_allow_html=True)


class ChainWeaveDashboard:
    """Main dashboard application."""
    
    def __init__(self):
        """Initialize dashboard."""
        self.project_id = st.secrets.get("project_id", "chainweave-analytics")
        self.dataset_id = st.secrets.get("dataset_id", "chainweave")
        
        # Initialize services
        self.dashboard_service = DashboardDataService(self.project_id, self.dataset_id)
        self.cache_manager = CacheManager()
        
        # Session state initialization
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        if 'selected_collection' not in st.session_state:
            st.session_state.selected_collection = None
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = True
    
    def run(self):
        """Run the dashboard application."""
        # Header
        st.markdown('<h1 class="main-header">🔗 ChainWeave NFT Analytics</h1>', unsafe_allow_html=True)
        
        # Sidebar
        self.render_sidebar()
        
        # Main content
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Market Overview", "🏆 Collections", "🐋 Whale Activity", "📈 Analytics"])
        
        with tab1:
            self.render_market_overview()
        
        with tab2:
            self.render_collections_view()
        
        with tab3:
            self.render_whale_activity()
        
        with tab4:
            self.render_analytics_view()
    
    def render_sidebar(self):
        """Render sidebar with controls and status."""
        st.sidebar.title("🔧 Controls")
        
        # Auto-refresh toggle
        st.session_state.auto_refresh = st.sidebar.checkbox(
            "Auto-refresh (30s)",
            value=st.session_state.auto_refresh
        )
        
        # Manual refresh button
        if st.sidebar.button("🔄 Refresh Now"):
            st.session_state.last_refresh = datetime.now()
            st.experimental_rerun()
        
        # Last refresh time
        st.sidebar.write(f"Last refresh: {st.session_state.last_refresh.strftime('%H:%M:%S')}")
        
        # Auto-refresh logic
        if st.session_state.auto_refresh:
            time_since_refresh = (datetime.now() - st.session_state.last_refresh).total_seconds()
            if time_since_refresh > 30:
                st.session_state.last_refresh = datetime.now()
                st.experimental_rerun()
        
        st.sidebar.markdown("---")
        
        # Filters
        st.sidebar.subheader("📊 Filters")
        
        days_filter = st.sidebar.selectbox(
            "Time Range",
            options=[1, 7, 30, 90],
            index=1,
            format_func=lambda x: f"{x} day{'s' if x > 1 else ''}"
        )
        
        min_volume = st.sidebar.slider(
            "Min Volume (SOL)",
            min_value=0.0,
            max_value=1000.0,
            value=10.0,
            step=10.0
        )
        
        st.sidebar.markdown("---")
        
        # System status
        st.sidebar.subheader("🟢 System Status")
        
        try:
            # Mock status for demo
            st.sidebar.success("✅ BigQuery: Healthy")
            st.sidebar.success("✅ Cache: Active")
            st.sidebar.info("📊 Last Data: 2 minutes ago")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {str(e)}")
    
    def render_market_overview(self):
        """Render global market overview."""
        st.header("🌍 Global Market Overview")
        
        try:
            # Load global summary (with caching simulation)
            global_summary = self.get_cached_data("global_summary", self.load_global_summary)
            
            if global_summary:
                # Key metrics row
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    self.render_metric_card(
                        "Total Volume 24h",
                        f"{global_summary.get('total_volume_24h', 0):.1f} SOL",
                        f"{global_summary.get('volume_change_24h_pct', 0):+.1f}%"
                    )
                
                with col2:
                    self.render_metric_card(
                        "Total Collections",
                        f"{global_summary.get('total_collections', 0):,}",
                        f"+{global_summary.get('active_collections_24h', 0)} active"
                    )
                
                with col3:
                    self.render_metric_card(
                        "Active Wallets 24h",
                        f"{global_summary.get('unique_wallets_24h', 0):,}",
                        f"{global_summary.get('avg_transaction_size', 0):.3f} SOL avg"
                    )
                
                with col4:
                    market_trend = global_summary.get('market_trend', 'neutral')
                    trend_emoji = {'bullish': '🐂', 'bearish': '🐻', 'neutral': '😐'}.get(market_trend, '❓')
                    self.render_metric_card(
                        "Market Sentiment",
                        f"{market_trend.title()} {trend_emoji}",
                        f"{global_summary.get('whale_alerts_24h', 0)} whale alerts"
                    )
                
                st.markdown("---")
                
                # Charts row
                col1, col2 = st.columns(2)
                
                with col1:
                    self.render_volume_trend_chart()
                
                with col2:
                    self.render_market_activity_chart()
                
            else:
                st.warning("Unable to load global market data")
                
        except Exception as e:
            st.error(f"Error loading market overview: {str(e)}")
    
    def render_collections_view(self):
        """Render collections performance view."""
        st.header("🏆 Top Collections")
        
        try:
            # Load top collections
            top_collections = self.get_cached_data("top_collections", self.load_top_collections)
            
            if top_collections:
                # Collection selector
                collection_names = [f"{c['name']} ({c['collection_id'][:8]}...)" for c in top_collections]
                selected_idx = st.selectbox(
                    "Select Collection for Details",
                    range(len(collection_names)),
                    format_func=lambda x: collection_names[x]
                )
                
                if selected_idx is not None:
                    selected_collection = top_collections[selected_idx]
                    st.session_state.selected_collection = selected_collection['collection_id']
                
                st.markdown("---")
                
                # Top collections table
                st.subheader("📊 Rankings by Volume")
                
                # Convert to DataFrame for display
                df = pd.DataFrame(top_collections)
                df['rank'] = range(1, len(df) + 1)
                
                # Format columns
                display_df = pd.DataFrame({
                    'Rank': df['rank'],
                    'Collection': df['name'].str[:30],
                    'Volume (SOL)': df['volume'].round(1),
                    'Floor (SOL)': df['floor_price'].round(4),
                    'Transactions': df['transaction_count'],
                    'Traders': df['unique_traders'],
                    'Change %': df['volume_change_pct'].round(1)
                })
                
                # Color code based on volume change
                def color_change(val):
                    if val > 10:
                        return 'background-color: #d4edda'
                    elif val < -10:
                        return 'background-color: #f8d7da'
                    return ''
                
                styled_df = display_df.style.applymap(color_change, subset=['Change %'])
                st.dataframe(styled_df, use_container_width=True)
                
                # Detailed collection view
                if st.session_state.selected_collection:
                    self.render_collection_details(st.session_state.selected_collection)
                
            else:
                st.warning("No collection data available")
                
        except Exception as e:
            st.error(f"Error loading collections: {str(e)}")
    
    def render_collection_details(self, collection_id: str):
        """Render detailed view for selected collection."""
        st.markdown("---")
        st.subheader(f"📋 Collection Details: {collection_id[:8]}...")
        
        try:
            # Load collection summary
            collection_summary = self.get_cached_data(
                f"collection_{collection_id}",
                lambda: self.load_collection_summary(collection_id)
            )
            
            if collection_summary:
                # Collection metrics
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "Floor Price",
                        f"{collection_summary.get('floor_price', 0):.4f} SOL",
                        f"{collection_summary.get('price_stats_24h', {}).get('change_pct', 0):+.1f}%"
                    )
                
                with col2:
                    st.metric(
                        "Market Cap",
                        f"{collection_summary.get('market_cap', 0):.1f} SOL",
                        f"{collection_summary.get('holders_count', 0):,} holders"
                    )
                
                with col3:
                    st.metric(
                        "24h Volume",
                        f"{collection_summary.get('volume_24h', 0):.1f} SOL",
                        f"{collection_summary.get('transactions_24h', 0)} txns"
                    )
                
                # Charts
                col1, col2 = st.columns(2)
                
                with col1:
                    self.render_collection_price_chart(collection_id)
                
                with col2:
                    self.render_collection_holders_chart(collection_id)
                
                # Recent transactions
                st.subheader("🔄 Recent Transactions")
                recent_txns = self.get_cached_data(
                    f"recent_txns_{collection_id}",
                    lambda: self.load_recent_transactions(collection_id)
                )
                
                if recent_txns:
                    txn_df = pd.DataFrame(recent_txns[:10])  # Top 10
                    st.dataframe(
                        txn_df[['nft_name', 'event_type', 'price_sol', 'marketplace', 'timestamp']],
                        use_container_width=True
                    )
                
        except Exception as e:
            st.error(f"Error loading collection details: {str(e)}")
    
    def render_whale_activity(self):
        """Render whale activity monitoring."""
        st.header("🐋 Whale Activity Monitor")
        
        try:
            # Load whale alerts
            whale_alerts = self.get_cached_data("whale_alerts", self.load_whale_alerts)
            
            if whale_alerts:
                # Whale activity summary
                col1, col2, col3 = st.columns(3)
                
                severity_counts = {}
                total_volume = 0
                
                for alert in whale_alerts:
                    severity = alert.get('severity', 'unknown')
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                    total_volume += alert.get('amount_sol', 0)
                
                with col1:
                    st.metric("Total Alerts (7d)", len(whale_alerts), f"{severity_counts.get('high', 0)} high priority")
                
                with col2:
                    st.metric("Whale Volume", f"{total_volume:.1f} SOL", f"{len(set(a['wallet_address'] for a in whale_alerts))} unique wallets")
                
                with col3:
                    critical_alerts = severity_counts.get('critical', 0)
                    st.metric("Critical Alerts", critical_alerts, f"{(critical_alerts/len(whale_alerts)*100):.1f}% of total" if whale_alerts else "0%")
                
                # Whale alerts feed
                st.subheader("🚨 Recent Whale Alerts")
                
                for alert in whale_alerts[:15]:  # Show top 15
                    self.render_whale_alert_card(alert)
                
                # Whale activity chart
                st.subheader("📊 Whale Activity Trends")
                self.render_whale_activity_chart(whale_alerts)
                
            else:
                st.info("No recent whale activity detected")
                
        except Exception as e:
            st.error(f"Error loading whale activity: {str(e)}")
    
    def render_whale_alert_card(self, alert: Dict[str, Any]):
        """Render individual whale alert card."""
        severity = alert.get('severity', 'low')
        alert_type = alert.get('alert_type', 'unknown')
        amount = alert.get('amount_sol', 0)
        collection_name = alert.get('collection_name', 'Unknown')
        wallet = alert.get('wallet_address', '')
        
        # Severity styling
        severity_colors = {
            'low': '#d1ecf1',
            'medium': '#fff3cd',
            'high': '#f8d7da',
            'critical': '#d4edda'
        }
        
        severity_emojis = {
            'low': '🟢',
            'medium': '🟡',
            'high': '🔴',
            'critical': '🚨'
        }
        
        bg_color = severity_colors.get(severity, '#f8f9fa')
        emoji = severity_emojis.get(severity, '⚪')
        
        st.markdown(f"""
        <div style="background: {bg_color}; padding: 12px; border-radius: 8px; margin: 8px 0; border-left: 4px solid #007bff;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>{emoji} {alert_type.replace('_', ' ').title()}</strong> - {amount:.1f} SOL
                    <br>
                    <small>📁 {collection_name} | 👤 {wallet[:8]}...{wallet[-4:]}</small>
                </div>
                <div style="text-align: right;">
                    <small>{severity.upper()}</small>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    def render_analytics_view(self):
        """Render advanced analytics and insights."""
        st.header("📈 Advanced Analytics")
        
        try:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🎯 Market Insights")
                
                # Generate insights
                insights = self.generate_market_insights()
                for insight in insights:
                    st.info(f"💡 {insight}")
            
            with col2:
                st.subheader("🔮 Trending Collections")
                
                # Load trending data
                trending = self.get_cached_data("trending", self.load_trending_data)
                if trending:
                    for i, collection in enumerate(trending[:5], 1):
                        change = collection.get('volume_change_pct', 0)
                        trend_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                        st.write(f"{i}. {collection['name']} {trend_emoji} {change:+.1f}%")
            
            # Advanced charts
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                self.render_market_heatmap()
            
            with col2:
                self.render_price_distribution_chart()
                
        except Exception as e:
            st.error(f"Error loading analytics: {str(e)}")
    
    def render_metric_card(self, title: str, value: str, subtitle: str):
        """Render metric card component."""
        st.markdown(f"""
        <div class="metric-card">
            <h4 style="margin: 0; color: #666;">{title}</h4>
            <h2 style="margin: 0.5rem 0; color: #333;">{value}</h2>
            <p style="margin: 0; color: #888; font-size: 0.9rem;">{subtitle}</p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_volume_trend_chart(self):
        """Render volume trend chart."""
        st.subheader("📊 Volume Trend (7 days)")
        
        # Generate sample data
        dates = pd.date_range(start=datetime.now() - timedelta(days=7), end=datetime.now(), freq='D')
        volumes = [1200 + i*50 + (i%3)*100 for i in range(len(dates))]
        
        df = pd.DataFrame({'Date': dates, 'Volume': volumes})
        
        fig = px.line(df, x='Date', y='Volume', title='Daily Trading Volume')
        fig.update_traces(line=dict(color='#667eea', width=3))
        fig.update_layout(height=400)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_market_activity_chart(self):
        """Render market activity chart."""
        st.subheader("🎯 Market Activity")
        
        # Generate sample data
        categories = ['Sales', 'Transfers', 'Listings', 'Mints']
        values = [450, 230, 180, 90]
        
        fig = px.pie(values=values, names=categories, title='Transaction Types (24h)')
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(height=400)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_collection_price_chart(self, collection_id: str):
        """Render collection price history chart."""
        st.subheader("💰 Price History")
        
        # Generate sample data
        dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
        prices = [5.5 + i*0.1 + (i%5)*0.3 for i in range(len(dates))]
        
        df = pd.DataFrame({'Date': dates, 'Floor Price': prices})
        
        fig = px.line(df, x='Date', y='Floor Price', title='Floor Price (30 days)')
        fig.update_traces(line=dict(color='#764ba2', width=2))
        fig.update_layout(height=300)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_collection_holders_chart(self, collection_id: str):
        """Render collection holders distribution chart."""
        st.subheader("👥 Holders Distribution")
        
        # Generate sample data
        holder_ranges = ['1 NFT', '2-5 NFTs', '6-10 NFTs', '11-50 NFTs', '50+ NFTs']
        holder_counts = [1250, 480, 120, 45, 8]
        
        fig = px.bar(x=holder_ranges, y=holder_counts, title='NFTs per Holder')
        fig.update_traces(marker_color='#667eea')
        fig.update_layout(height=300)
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_whale_activity_chart(self, whale_alerts: List[Dict]):
        """Render whale activity timeline chart."""
        if not whale_alerts:
            return
        
        # Process alerts for chart
        df = pd.DataFrame(whale_alerts)
        df['triggered_at'] = pd.to_datetime(df['triggered_at'])
        df['date'] = df['triggered_at'].dt.date
        
        # Group by date and severity
        daily_alerts = df.groupby(['date', 'severity']).size().reset_index(name='count')
        
        fig = px.bar(daily_alerts, x='date', y='count', color='severity',
                    title='Whale Alerts Over Time',
                    color_discrete_map={
                        'low': '#28a745',
                        'medium': '#ffc107',
                        'high': '#dc3545',
                        'critical': '#6f42c1'
                    })
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    def render_market_heatmap(self):
        """Render market performance heatmap."""
        st.subheader("🌡️ Collection Performance Heatmap")
        
        # Generate sample data
        collections = [f"Collection {i}" for i in range(1, 21)]
        metrics = ['Volume', 'Floor Price', 'Holders', 'Activity']
        
        # Create sample performance matrix
        import numpy as np
        np.random.seed(42)
        data = np.random.rand(len(collections), len(metrics)) * 100
        
        fig = px.imshow(data, 
                       x=metrics, 
                       y=collections,
                       title="Collection Performance Matrix",
                       color_continuous_scale='RdYlBu_r')
        
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    
    def render_price_distribution_chart(self):
        """Render price distribution chart."""
        st.subheader("💹 Price Distribution")
        
        # Generate sample data
        import numpy as np
        np.random.seed(42)
        prices = np.random.lognormal(mean=1.5, sigma=0.8, size=1000)
        
        fig = px.histogram(x=prices, nbins=50, title='NFT Price Distribution (SOL)')
        fig.update_traces(marker_color='#764ba2')
        fig.update_layout(height=400)
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Data loading methods (with caching simulation)
    def get_cached_data(self, key: str, loader_func, ttl_minutes: int = 5):
        """Get data with caching simulation."""
        cache_key = f"dashboard_{key}"
        
        # Check session state cache
        if cache_key in st.session_state:
            cached_data, timestamp = st.session_state[cache_key]
            if (datetime.now() - timestamp).total_seconds() < ttl_minutes * 60:
                return cached_data
        
        # Load fresh data
        try:
            data = loader_func()
            st.session_state[cache_key] = (data, datetime.now())
            return data
        except Exception as e:
            st.error(f"Failed to load data for {key}: {str(e)}")
            return None
    
    def load_global_summary(self):
        """Load global market summary (mock data)."""
        return {
            'total_volume_24h': 15420.5,
            'volume_change_24h_pct': 12.3,
            'total_collections': 847,
            'active_collections_24h': 234,
            'unique_wallets_24h': 8934,
            'avg_transaction_size': 2.341,
            'market_trend': 'bullish',
            'whale_alerts_24h': 23
        }
    
    def load_top_collections(self):
        """Load top collections (mock data)."""
        collections = []
        for i in range(20):
            collections.append({
                'collection_id': f"collection_{i+1}",
                'name': f"NFT Collection {i+1}",
                'volume': 1000 - i*45,
                'floor_price': 5.5 - i*0.2,
                'transaction_count': 150 - i*5,
                'unique_traders': 80 - i*3,
                'volume_change_pct': 25 - i*2.5
            })
        return collections
    
    def load_collection_summary(self, collection_id: str):
        """Load collection summary (mock data)."""
        return {
            'collection_id': collection_id,
            'name': f"Collection {collection_id[:8]}",
            'floor_price': 5.67,
            'market_cap': 15420.5,
            'volume_24h': 892.3,
            'transactions_24h': 45,
            'holders_count': 1234,
            'price_stats_24h': {'change_pct': 8.2}
        }
    
    def load_recent_transactions(self, collection_id: str):
        """Load recent transactions (mock data)."""
        transactions = []
        for i in range(15):
            transactions.append({
                'nft_name': f"NFT #{1000+i}",
                'event_type': 'sale',
                'price_sol': 5.5 + i*0.3,
                'marketplace': 'Magic Eden',
                'timestamp': datetime.now() - timedelta(minutes=i*15)
            })
        return transactions
    
    def load_whale_alerts(self):
        """Load whale alerts (mock data)."""
        alerts = []
        severities = ['low', 'medium', 'high', 'critical']
        alert_types = ['large_purchase', 'large_sale', 'rapid_accumulation', 'bulk_listing']
        
        for i in range(25):
            alerts.append({
                'alert_id': f"alert_{i+1}",
                'wallet_address': f"{''.join(['a' for _ in range(40)])}",
                'alert_type': alert_types[i % len(alert_types)],
                'amount_sol': 50 + i*10,
                'severity': severities[i % len(severities)],
                'collection_name': f"Collection {i%5 + 1}",
                'triggered_at': datetime.now() - timedelta(hours=i)
            })
        return alerts
    
    def load_trending_data(self):
        """Load trending collections (mock data)."""
        trending = []
        for i in range(10):
            trending.append({
                'name': f"Trending Collection {i+1}",
                'volume_change_pct': 150 - i*15
            })
        return trending
    
    def generate_market_insights(self):
        """Generate market insights."""
        return [
            "NFT trading volume increased 23% in the last 24 hours",
            "Whale activity is up 45% compared to last week",
            "3 collections show unusual accumulation patterns",
            "Floor prices are stabilizing across major collections",
            "New wallet participation increased by 18%"
        ]


# Main application
def main():
    """Main application entry point."""
    dashboard = ChainWeaveDashboard()
    dashboard.run()


if __name__ == "__main__":
    main()