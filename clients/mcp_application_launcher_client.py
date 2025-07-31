#!/usr/bin/env python3
"""
MCP Application Launcher Client
Tests the application launcher functionality through MCP tools
"""

import logging
import time
import asyncio
import sys
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MCPApplicationLauncherClient:
    """MCP client for testing application launcher functionality through MCP tools"""
    
    def __init__(self):
        # Add server path for imports
        project_root = os.path.dirname(os.path.dirname(__file__))
        server_path = os.path.join(project_root, 'server')
        sys.path.insert(0, server_path)
        
        try:
            # Import MCP components
            from process.manager import ProcessManager
            self.process_manager = ProcessManager()
            logger.info("✅ MCP client initialized")
            
        except ImportError as e:
            logger.error(f"❌ Failed to import MCP components: {e}")
            raise
    
    async def test_mcp_application_launcher_workflow(self):
        """Test the complete MCP application launcher workflow"""
        try:
            logger.info("🤖 Starting MCP Application Launcher Workflow Test")
            logger.info("=" * 70)
            
            # Import main module to access MCP tools directly
            import main
            
            # Test 1: Get whitelisted applications
            logger.info("📋 Step 1: Getting whitelisted applications...")
            result = main.get_whitelisted_applications()
            logger.info(f"✅ Result:\\n{result}")
            await asyncio.sleep(1)
            
            # Test 2: Launch Notepad
            logger.info("🚀 Step 2: Launching Notepad...")
            result = main.launch_application("notepad.exe")
            logger.info(f"✅ Launch Result: {result}")
            
            # Extract PID if successful
            notepad_pid = None
            if "SUCCESS" in result and "PID:" in result:
                try:
                    # Extract PID from message like "SUCCESS: Successfully launched notepad.exe (PID: 12345)"
                    pid_part = result.split("PID: ")[1].split(")")[0]
                    notepad_pid = int(pid_part)
                    logger.info(f"📍 Extracted PID: {notepad_pid}")
                except:
                    logger.warning("⚠️ Could not extract PID from launch result")
            
            await asyncio.sleep(2)
            
            # Test 3: Get launched applications
            logger.info("📊 Step 3: Getting launched applications...")
            result = main.get_launched_applications()
            logger.info(f"✅ Result:\\n{result}")
            await asyncio.sleep(1)
            
            # Test 4: Get application info (if we have a PID)
            if notepad_pid:
                logger.info(f"🔍 Step 4: Getting application info for PID {notepad_pid}...")
                result = main.get_application_info(notepad_pid)
                logger.info(f"✅ Result:\\n{result}")
                await asyncio.sleep(1)
            
            # Test 5: Launch Calculator as well
            logger.info("🧮 Step 5: Launching Calculator...")
            result = main.launch_application("calc.exe")
            logger.info(f"✅ Launch Result: {result}")
            await asyncio.sleep(2)
            
            # Test 6: Get launched applications again
            logger.info("📊 Step 6: Getting all launched applications...")
            result = main.get_launched_applications()
            logger.info(f"✅ Result:\\n{result}")
            await asyncio.sleep(1)
            
            # Test 7: Terminate Notepad (if we have a PID)
            if notepad_pid:
                logger.info(f"🛑 Step 7: Terminating Notepad (PID {notepad_pid})...")
                result = main.terminate_application(notepad_pid, False)
                logger.info(f"✅ Terminate Result: {result}")
                await asyncio.sleep(2)
            
            # Test 8: Terminate all remaining applications
            logger.info("🧹 Step 8: Terminating all remaining applications...")
            result = main.terminate_all_launched_applications(False)
            logger.info(f"✅ Result:\\n{result}")
            await asyncio.sleep(2)
            
            # Test 9: Cleanup terminated applications
            logger.info("🗑️ Step 9: Cleaning up terminated applications...")
            result = main.cleanup_terminated_applications()
            logger.info(f"✅ Result: {result}")
            
            logger.info("=" * 70)
            logger.info("🎉 MCP Application Launcher Workflow TEST COMPLETE!")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ MCP workflow test failed: {e}")
            return False

async def main():
    """Main function"""
    try:
        logger.info("🧪 MCP Application Launcher Client Starting")
        logger.info("=" * 50)
        
        # Initialize client
        client = MCPApplicationLauncherClient()
        
        # Run MCP workflow test
        success = await client.test_mcp_application_launcher_workflow()
        
        if success:
            logger.info("🎉 MCP Application Launcher test completed successfully!")
        else:
            logger.error("❌ MCP Application Launcher test failed")
        
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
