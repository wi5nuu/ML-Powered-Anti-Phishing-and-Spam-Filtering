#!/usr/bin/env python3
"""
Live demonstration script for CogniMail real-time WebSocket functionality.

This script provides a comprehensive demo of the real-time capabilities
for admin and superadmin users, showing how WebSocket connections work
and how real-time updates are broadcasted.

Usage:
    python _live_demo.py
"""

import asyncio
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.infrastructure.websocket.manager import ws_manager

# Simulate WebSocket client for demonstration
class DemoWebSocketClient:
    def __init__(self, client_id: str, role: str):
        self.client_id = client_id
        self.role = role
        self.connected = False
        self.messages_received = 0
        
    def connect(self):
        self.connected = True
        print(f"  ✅ Client {self.client_id} ({self.role}) connected")
        
    def disconnect(self):
        self.connected = False
        print(f"  ❌ Client {self.client_id} ({self.role}) disconnected")
        
    async def send_message(self, message: Dict[str, Any]):
        if not self.connected:
            print(f"  ⚠️  Client {self.client_id} is not connected")
            return False
        
        self.messages_received += 1
        print(f"  📨 Client {self.client_id} ({self.role}): {json.dumps(message, indent=2)}")
        return True
        
    def simulate_ping_pong(self):
        """Simulate ping/pong keep-alive messages."""
        if self.connected:
            print(f"  💭 Client {self.client_id} Ping -> Pong")


async def demo_websocket_connection():
    """Demonstrate WebSocket client connection process."""
    print("\n🔌 WebSocket Connection Demo")
    print("-" * 40)
    
    # Create demo clients
    admin_client = DemoWebSocketClient("admin-001", "admin")
    superadmin_client = DemoWebSocketClient("superadmin-001", "superadmin")
    
    # Simulate connection process
    admin_client.connect()
    superadmin_client.connect()
    
    # Simulate some ping/pong messages
    for _ in range(3):
        admin_client.simulate_ping_pong()
        superadmin_client.simulate_ping_pong()
        await asyncio.sleep(0.5)
    
    # Send a welcome message
    welcome_msg = {
        "type": "connected",
        "data": {
            "message": "WebSocket connected successfully",
            "user": "demo_admin",
            "role": "admin",
            "timestamp": time.time()
        }
    }
    
    await admin_client.send_message(welcome_msg)
    
    # Simulate disconnect
    admin_client.disconnect()
    superadmin_client.disconnect()
    
    return [admin_client, superadmin_client]


async def demo_broadcast_functionality():
    """Demonstrate WebSocket broadcasting capabilities."""
    print("\n📢 WebSocket Broadcasting Demo")
    print("-" * 40)
    
    # Add some connections to the manager for demo
    admin_client = DemoWebSocketClient("broadcast-admin", "admin")
    superadmin_client = DemoWebSocketClient("broadcast-superadmin", "superadmin")
    
    admin_client.connect()
    superadmin_client.connect()
    
    # Create fake WebSocket objects for the manager
    class FakeWebSocket:
        def __init__(self, client, ws_id):
            self.client = client
            self.id = ws_id
            
        async def send_text(self, message):
            data = json.loads(message)
            await self.client.send_message(data)
    
    fake_admin_ws = FakeWebSocket(admin_client, "admin-ws-001")
    fake_superadmin_ws = FakeWebSocket(superadmin_client, "superadmin-ws-001")
    
    # Simulate connections via the manager
    await ws_manager.connect(fake_admin_ws, "admin")
    await ws_manager.connect(fake_superadmin_ws, "superadmin")
    
    print(f"\n📊 Current connections: {ws_manager.get_connection_count()}")
    print(f"   - Admin connections: {len(ws_manager.connections.get('admin', []))}")
    print(f"   - Superadmin connections: {len(ws_manager.connections.get('superadmin', []))}")
    
    # Demo different event types
    demo_events = [
        {
            "event_type": "user_created",
            "data": {
                "id": 1001,
                "username": "new_user",
                "role": "user",
                "email": "newuser@example.com"
            }
        },
        {
            "event_type": "email_quarantined",
            "data": {
                "id": 2001,
                "email_id": "threat-001",
                "subject": "Urgent: Account Verification Required",
                "sender": "unknown@phishing.com",
                "category": "phishing",
                "score": 0.95
            }
        },
        {
            "event_type": "system_health_update",
            "data": {
                "status": "healthy",
                "databases": {
                    "main": "connected",
                    "redis": "connected"
                },
                "active_connections": ws_manager.get_connection_count(),
                "uptime": "99.8%"
            }
        }
    ]
    
    print(f"\n🚀 Broadcasting demo events...")
    for event in demo_events:
        print(f"\n  Broadcasting: {event['event_type']}")
        await ws_manager.broadcast_event(event['event_type'], event['data'])
        await asyncio.sleep(1)
    
    # Demonstrate role-based broadcasting
    print(f"\n🎯 Demonstrating role-based broadcasting...")
    user_event = {
        "event_type": "mailbox_created",
        "data": {
            "id": 3001,
            "email": "new@company.com",
            "assigned_to": "admin_user"
        }
    }
    
    await ws_manager.broadcast_event(user_event['event_type'], user_event['data'], roles=["admin"])
    print(f"   • Event sent to admin role only")
    
    # Clean up
    ws_manager.disconnect(fake_admin_ws, "admin")
    ws_manager.disconnect(fake_superadmin_ws, "superadmin")
    
    print(f"\n📈 Final connection count: {ws_manager.get_connection_count()}")


async def demo_redis_pubsub_integration():
    """Demonstrate Redis Pub/Sub integration concept."""
    print("\n🔄 Redis Pub/Sub Integration Demo")
    print("-" * 40)
    
    print("Redis Pub/Sub Bridge Configuration:")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    pubsub_channel = os.getenv("PUBSUB_CHANNEL", "email:processed")
    
    print(f"   • Redis URL: {redis_url}")
    print(f"   • Pub/Sub Channel: {pubsub_channel}")
    print(f"   • WebSocket Bridge: Enabled (production)")
    
    # Simulate Redis message processing
    print(f"\n📨 Simulating Redis message processing...")
    
    sample_redis_messages = [
        {
            "type": "message",
            "data": json.dumps({
                "type": "email_processed",
                "data": {
                    "id": "email-1001",
                    "status": "processed",
                    "threat_level": "low",
                    "timestamp": time.time()
                }
            })
        },
        {
            "type": "message", 
            "data": json.dumps({
                "type": "new_threat_detected",
                "data": {
                    "id": "threat-2001",
                    "severity": "high",
                    "detected_by": "isolation_forest",
                    "timestamp": time.time()
                }
            })
        }
    ]
    
    for i, message in enumerate(sample_redis_messages, 1):
        print(f"\n  Processing Redis message #{i}:")
        print(f"    Message type: {message['type']}")
        print(f"    Channel: {pubsub_channel}")
        
        try:
            message_data = json.loads(message['data'])
            print(f"    Parsed data: {message_data}")
            print(f"    Broadcasting to WebSocket clients via manager.broadcast()")
        except json.JSONDecodeError as e:
            print(f"    Error parsing message: {e}")
    
    print(f"\n✅ Redis Pub/Sub integration concept demonstrated!")


async def demo_api_endpoints():
    """Demonstrate the API endpoints for real-time updates."""
    print("\n🌐 API Endpoints Demo")
    print("-" * 40)
    
    print("Available real-time API endpoints:")
    print("\n   • GET /api/admin/health - Admin health checks")
    print("     ── Health: http://localhost:8000/api/admin/health")
    print("     ── Returns server status and WebSocket connection count")
    print("\n   • GET /api/health - Public health check")
    print("     ── Health: http://localhost:8000/api/health")
    print("     ── Returns system health with connection metrics")
    print("\n   • WebSocket: ws://localhost:8000/ws/admin?token=<jwt_token>")
    print("     ── Admin/Superadmin real-time updates")
    print("     ── Events: user_created, email_quarantined, system_health_update")
    
    print(f"\n📋 Supported event types:")
    supported_events = [
        ("user_created", "New user registration"),
        ("user_updated", "User profile update"),
        ("user_deleted", "User account deletion"),
        ("mailbox_created", "New mailbox setup"),
        ("email_quarantined", "Email threat detected and quarantined"),
        ("email_released", "Quarantined email released as safe"),
        ("system_health_update", "System health and metrics"),
    ]
    
    for event_type, description in supported_events:
        print(f"   • {event_type:<25} - {description}")


async def demo_connection_management():
    """Demonstrate connection management features."""
    print("\n🔗 Connection Management Demo")
    print("-" * 40)
    
    print("Connection Manager Features:")
    print("   • Centralized WebSocket connection pooling")
    print("   • Role-based connection tracking (admin, superadmin, user)")
    print("   • Automatic dead connection cleanup")
    print("   • Keep-alive ping/pong support")
    print("   • Connection count monitoring")
    
    # Show current manager status
    print(f"\n📊 Current WebSocket Manager Status:")
    print(f"   • Total connections: {ws_manager.get_connection_count()}")
    
    print(f"   • Connections by role:")
    for role, connections in ws_manager.connections.items():
        print(f"     - {role}: {len(connections)} connection(s)")
    
    print(f"\n🧹 Maintenance Features:")
    print("   • Automatic cleanup of dead connections")
    print("   • Connection timeout handling")
    print("   • Error recovery and reconnection logic")
    print("   • Connection metrics and monitoring")


async def main():
    """Main demo function orchestrating all demonstrations."""
    print("🎭 CogniMail Real-time WebSocket Live Demo")
    print("=" * 60)
    
    try:
        # Run all demonstrations
        await demo_websocket_connection()
        await demo_broadcast_functionality()
        await demo_redis_pubsub_integration()
        await demo_api_endpoints()
        await demo_connection_management()
        
        print("\n" + "=" * 60)
        print("✨ Live Demo completed successfully!")
        print("\n🎯 Summary:")
        print("   • Demonstrated WebSocket client connections")
        print("   • Showed broadcasting capabilities")
        print("   • Illustrated Redis Pub/Sub integration")
        print("   • Explored available API endpoints")
        print("   • Covered connection management features")
        
        print(f"\n🚀 Next Steps:")
        print("   1. Start the CogniMail system with: python src/main.py")
        print("   2. Connect WebSocket clients using: ws://localhost:8000/ws/admin")
        print("   3. Monitor connections via: GET /api/health")
        print("   4. Set up Redis for enhanced real-time updates")
        
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)