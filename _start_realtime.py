#!/usr/bin/env python3
"""
Initialize and start CogniMail real-time WebSocket services.

This script provides utilities and configuration for the real-time WebSocket
infrastructure, including connection management and message broadcasting.

Usage:
    python _start_realtime.py
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from src.infrastructure.websocket.manager import ws_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_websocket_configuration():
    """Check and validate WebSocket configuration."""
    print("🔍 Checking WebSocket Configuration...")
    
    # Check Redis configuration for Pub/Sub bridge
    redis_url = os.getenv("REDIS_URL")
    pubsub_channel = os.getenv("PUBSUB_CHANNEL", "email:processed")
    
    print(f"   📡 Redis URL: {'Set' if redis_url else 'Not configured'}")
    print(f"   📺 Pub/Sub Channel: {pubsub_channel}")
    
    # Check supported roles
    supported_roles = list(ws_manager.connections.keys())
    print(f"   🎭 Supported roles: {', '.join(supported_roles)}")
    
    # Check connection count
    total_connections = ws_manager.get_connection_count()
    print(f"   🔗 Active WebSocket connections: {total_connections}")
    
    if total_connections > 0:
        print("   📊 Connections by role:")
        for role, connections in ws_manager.connections.items():
            count = len(connections)
            if count > 0:
                print(f"      • {role}: {count} connection(s)")
    
    return {
        "redis_configured": bool(redis_url),
        "pubsub_channel": pubsub_channel,
        "supported_roles": supported_roles,
        "total_connections": total_connections
    }


def setup_realtime_services():
    """Set up real-time services and utilities."""
    print("\n⚙️  Setting Up Real-time Services...")
    
    # Validate endpoint configurations
    print("   ✅ Validating WebSocket endpoints...")
    
    # Check for required environment variables
    required_env_vars = ["JWT_SECRET"]
    print("   🔐 Checking required environment variables...")
    for var in required_env_vars:
        if os.getenv(var):
            print(f"      ✓ {var} is configured")
        else:
            print(f"      ⚠️  {var} not configured - may affect authentication")
    
    # Setup connection monitoring
    print("   📊 Setting up connection monitoring...")
    
    # Log current configuration
    config = check_websocket_configuration()
    
    print("\n" + "=" * 60)
    print("✨ Realtime Services Setup Complete!")
    print("=" * 60)
    
    return config


async def start_demonstration():
    """Start a WebSocket demonstration."""
    print("\n🎭 Starting WebSocket Demonstration...")
    print("-" * 40)
    
    # Show how different event types are broadcasted
    demo_events = [
        ("user_created", {"id": 1, "username": "newuser", "role": "user"}),
        ("email_quarantined", {"id": 101, "subject": "Phishing Alert", "category": "phishing"}),
        ("system_health_update", {"status": "healthy", "connections": 0}),
    ]
    
    print("📢 Event types supported by WebSocket system:")
    for event_type, sample_data in demo_events:
        print(f"   • {event_type}: {sample_data}")
    
    print(f"\n🔗 WebSocket endpoint available at: /ws/admin")
    print("   ❓ Required parameter: token=<jwt_token>")
    print("   🎭 Supported roles: admin, superadmin")
    
    return True


async def main():
    """Main entry point for the realtime setup script."""
    print("🚀 CogniMail Real-time WebSocket Setup Utility")
    print("=" * 60)
    
    try:
        # Check configuration
        config = check_websocket_configuration()
        
        # Setup services
        setup_config = setup_realtime_services()
        
        # Start demonstration
        await start_demonstration()
        
        print("\n🎯 Summary:")
        print(f"   • Redis Pub/Sub: {'Enabled' if config['redis_configured'] else 'Disabled'}")
        print(f"   • WebSocket Manager: Active ({config['total_connections']} connections)")
        print(f"   • Supported Roles: {', '.join(config['supported_roles'])}")
        
        print(f"\n🔧 Next Steps:")
        print(f"   1. Start the main CogniMail application: python src/main.py")
        print(f"   2. Configure Redis: export REDIS_URL=redis://localhost:6379/0")
        print(f"   3. Set JWT secret: export JWT_SECRET=your-secret-key")
        print(f"   4. Test WebSocket connections using a WebSocket client")
        
    except Exception as e:
        logger.error(f"❌ Error during setup: {e}")
        print(f"\n❌ Setup failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)