"""
FastAPI application initialization and configuration
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logger_config import init_logging, get_logger
from database import (
    init_database,
    ExchangeRepository,
    AgentRepository,
    ActivityLogRepository
)
from exchange_manager import ExchangeManager
from agent_manager import AgentManager
from risk_manager import RiskManager
from order_manager import OrderManager
from position_manager import PositionManager
from shared_state import SharedState
from managers.connection_manager import ConnectionManager

# Import route modules
from routes import (
    agent_conversation_routes,
    auth_routes, 
    models_routes, 
    exchanges_routes, 
    agents_routes, 
    market_orders_routes, 
    health_routes, 
    websocket_routes
)   

# Initialize logging
init_logging()
logger = get_logger(__name__)


def create_app():
    """Create and configure FastAPI application"""
    
    # Initialize managers
    shared_state = SharedState()
    connection_manager = ConnectionManager()
    risk_manager = RiskManager()
    exchange_manager = ExchangeManager(shared_state=shared_state)
    position_manager = PositionManager(exchange_manager=exchange_manager, shared_state=shared_state)
    order_manager = OrderManager(exchange_manager=exchange_manager, risk_manager=risk_manager, position_manager=position_manager)
    agent_manager = None
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal agent_manager
        
        init_database()
        logger.info("Database initialized")
        
        # ============ Step 1: Load and initialize exchanges ============
        try:
            enabled_exchanges = ExchangeRepository.get_all()
            if enabled_exchanges:
                logger.info(f"Loaded {len(enabled_exchanges)} exchange configurations from database")
                for ex in enabled_exchanges:
                    success = await exchange_manager.add_exchange({
                        'id': ex['id'],
                        'exchange': ex['exchange'],
                        'api_keys': ex.get('api_keys', {}),
                        'testnet': ex.get('testnet', True)
                    })
                    
                    if success:
                        ExchangeRepository.update(ex['id'], {'status': 'connected'})
                        logger.info(f"✅ Connected exchange at startup: {ex['name']}")
                    else:
                        ExchangeRepository.update(ex['id'], {'status': 'error'})
                        logger.warning(f"❌ Failed to connect exchange at startup: {ex['name']}")
            else:
                logger.info("No exchanges configured")
        except Exception as e:
            logger.error(f"Failed to initialize exchanges: {e}")
        
        # ============ Step 2: Load and initialize models ============
        try:
            from database import AIModelRepository
            enabled_models = AIModelRepository.get_all()
            if enabled_models:
                logger.info(f"Loaded {len(enabled_models)} AI model configurations from database")
                active_models = [m for m in enabled_models if m.get('status') == 'active']
                logger.info(f"{len(active_models)} models are active")
            else:
                logger.info("No AI models configured")
        except Exception as e:
            logger.error(f"Failed to load AI models: {e}")
        
        # ============ Step 3: Initialize AgentManager ============
        try:
            agent_manager = AgentManager(exchange_manager=exchange_manager, order_manager=order_manager, position_manager=position_manager)
            exchange_manager.set_data_event_handler(agent_manager.handle_data_event)
            logger.info("✅ AgentManager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize AgentManager: {e}")
            agent_manager = None
        
        # ============ Step 4: Load and start Agents ============
        if agent_manager:
            try:
                enabled_agents = AgentRepository.get_all()
                stopped_agents = [a for a in enabled_agents if a.get('status') == 'stopped']
                running_agents = [a for a in enabled_agents if a.get('status') == 'running']
                
                if enabled_agents:
                    logger.info(f"Loaded {len(enabled_agents)} agents from database ({len(running_agents)} need to start)")
                else:
                    logger.info("No agents configured")
                    enabled_agents = []
                
                # Create all Agent instances
                created_agents = []
                for agent in enabled_agents:
                    try:
                        logger.info(f"Creating agent: {agent['name']} (ID: {agent['id']})")
                        
                        agent_config = {
                            'max_position_size': agent.get('max_position_size', 1000.0),
                            'risk_per_trade': agent.get('risk_per_trade', 0.02),
                            'default_leverage': agent.get('default_leverage', 1),
                            'decision_interval': 60
                        }
                        
                        symbols = agent.get('symbols') if agent.get('symbols') else ([agent.get('symbol')] if agent.get('symbol') else [])
                        await agent_manager.create_agent(
                            agent_id=agent['id'],
                            name=agent['name'],
                            model_id=agent['model_id'],
                            exchange_id=agent['exchange_id'],
                            symbols=symbols,
                            timeframe=agent['timeframe'],
                            indicators=agent['indicators'],
                            prompt=agent['prompt'],
                            config=agent_config
                        )
                        created_agents.append(agent['id'])
                        logger.info(f"✅ Successfully created agent: {agent['name']}")
                    except Exception as e:
                        logger.error(f"❌ Failed to create agent {agent['name']} (ID: {agent['id']}): {e}", exc_info=True)
                        AgentRepository.update(agent['id'], {'status': 'error'})
                
                logger.info(f"Successfully created {len(created_agents)} agents")
                
                # Start previously running agents
                started_agents = []
                for agent in running_agents:
                    try:
                        if agent['id'] not in created_agents:
                            logger.warning(f"Agent {agent['name']} creation failed, skipping startup")
                            continue
                        
                        logger.info(f"Starting agent: {agent['name']} (ID: {agent['id']})")
                        await agent_manager.start_agent(agent['id'])
                        started_agents.append(agent['id'])
                        logger.info(f"✅ Successfully started agent: {agent['name']}")
                    except Exception as e:
                        logger.error(f"❌ Failed to start agent {agent['name']} (ID: {agent['id']}): {e}", exc_info=True)
                        AgentRepository.update(agent['id'], {'status': 'error'})
                
                logger.info(f"Successfully started {len(started_agents)} agents")
            except Exception as e:
                logger.error(f"Failed to load agents: {e}", exc_info=True)
        
        ActivityLogRepository.log('info', 'Backend server started')
        logger.info("=" * 50)
        logger.info("✅ Backend server startup completed")
        logger.info("=" * 50)
        
        # Store managers in app.state for use in routes
        app.state.agent_manager = agent_manager
        app.state.exchange_manager = exchange_manager
        app.state.connection_manager = connection_manager
        
        # Inject managers into route modules (after agent_manager is fully initialized)
        agents_routes.set_managers(agent_manager, exchange_manager)
        market_orders_routes.set_exchange_manager(exchange_manager)
        health_routes.set_managers(agent_manager, connection_manager, exchange_manager)
        
        yield
        
        # Cleanup
        logger.info("Starting cleanup...")
        if agent_manager:
            await agent_manager.cleanup()
        
        await exchange_manager.close_all()
        ActivityLogRepository.log('info', 'Backend server stopped')
    
    # Create FastAPI app with lifespan
    app = FastAPI(title="CryptoAgent API", lifespan=lifespan)
    
    # CORS configuration — allow localhost dev, ngrok tunnels, and v0/Vercel preview origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://localhost:3000",
        ],
        # Also allow any origin so ngrok + v0 preview domains work without enumeration.
        # In production, replace allow_origins with your exact frontend domain and remove allow_origin_regex.
        allow_origin_regex=r"https?://.*\.(vusercontent\.net|ngrok\.io|ngrok-free\.app|ngrok-free\.dev|vercel\.app)$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routes
    app.include_router(agent_conversation_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(models_routes.router)
    app.include_router(exchanges_routes.router)
    app.include_router(agents_routes.router)
    app.include_router(market_orders_routes.router)
    app.include_router(health_routes.router)
    app.include_router(websocket_routes.router)
    
    # Inject managers into route modules
    exchanges_routes.set_exchange_manager(exchange_manager)
    # Note: agents_routes, market_orders_routes, and health_routes managers are now set in lifespan after initialization
    websocket_routes.set_connection_manager(connection_manager)
    
    return app
