#!/usr/bin/env python3
"""
Calculator-specific investigation
Tests why Calculator is showing as terminated
"""

import logging
import time
import asyncio
import sys
import os
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CalculatorInvestigation:
    """Investigate Calculator launch behavior"""
    
    def __init__(self):
        # Add server path for imports
        project_root = os.path.dirname(os.path.dirname(__file__))
        server_path = os.path.join(project_root, 'server')
        sys.path.insert(0, server_path)
        
        try:
            # Import required modules
            from config.whitelist import ProcessWhitelist
            from process.launcher import ApplicationLauncher
            
            # Initialize components
            self.whitelist = ProcessWhitelist()
            self.whitelist.load_whitelist(os.path.join(server_path, 'process_whitelist.json'))
            
            self.launcher = ApplicationLauncher(self.whitelist)
            
            logger.info("✅ Calculator investigation initialized")
            
        except ImportError as e:
            logger.error(f"❌ Failed to import components: {e}")
            raise
    
    def find_calculator_processes(self):
        """Find all calculator-related processes"""
        calculator_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'create_time']):
            try:
                info = proc.info
                name = info['name'].lower()
                if 'calc' in name or 'calculator' in name:
                    calculator_processes.append({
                        'pid': info['pid'],
                        'name': info['name'],
                        'exe': info['exe'],
                        'create_time': info['create_time']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return calculator_processes
    
    async def test_calculator_launch_behavior(self):
        """Test Calculator launch and monitor what happens"""
        try:
            logger.info("🧮 Calculator Launch Investigation")
            logger.info("=" * 50)
            
            # Check what calculator processes are already running
            logger.info("📊 Step 1: Checking existing calculator processes...")
            existing_calcs = self.find_calculator_processes()
            logger.info(f"Found {len(existing_calcs)} existing calculator processes:")
            for calc in existing_calcs:
                logger.info(f"  • PID {calc['pid']}: {calc['name']} ({calc['exe']})")
            
            # Launch Calculator
            logger.info("\\n🚀 Step 2: Launching Calculator...")
            success, message, pid = self.launcher.launch_application('calc.exe')
            
            if success:
                logger.info(f"✅ Launch result: {message}")
                logger.info(f"📍 Returned PID: {pid}")
                
                # Check if this PID actually exists
                try:
                    process = psutil.Process(pid)
                    logger.info(f"📋 PID {pid} details: {process.name()} ({process.exe()})")
                    logger.info(f"🕐 Process created: {time.ctime(process.create_time())}")
                except psutil.NoSuchProcess:
                    logger.warning(f"⚠️ PID {pid} does not exist!")
                
                # Wait and monitor
                for i in range(5):
                    await asyncio.sleep(1)
                    logger.info(f"\\n⏳ Status check {i+1}:")
                    
                    # Check if original PID still exists
                    try:
                        process = psutil.Process(pid)
                        logger.info(f"  📋 Original PID {pid}: {process.name()} (still running)")
                    except psutil.NoSuchProcess:
                        logger.warning(f"  ⚠️ Original PID {pid} no longer exists")
                    
                    # Check all calculator processes
                    current_calcs = self.find_calculator_processes()
                    logger.info(f"  📊 Current calculator processes ({len(current_calcs)}):")
                    for calc in current_calcs:
                        age = time.time() - calc['create_time']
                        logger.info(f"    • PID {calc['pid']}: {calc['name']} (age: {age:.1f}s)")
                    
                    # Check launcher status
                    app_info = self.launcher.get_application_by_pid(pid)
                    if app_info:
                        logger.info(f"  📊 Launcher status: {app_info['status']}")
                
                # Final status
                logger.info("\\n📋 Final Status:")
                final_calcs = self.find_calculator_processes()
                logger.info(f"Calculator processes found: {len(final_calcs)}")
                for calc in final_calcs:
                    logger.info(f"  • PID {calc['pid']}: {calc['name']}")
                
                launched_apps = self.launcher.get_launched_applications()
                calc_apps = [app for app in launched_apps if 'calc' in app['process_name']]
                logger.info(f"\\nLauncher tracking: {len(calc_apps)} calculator apps")
                for app in calc_apps:
                    logger.info(f"  • PID {app['pid']}: {app['process_name']} ({app['status']})")
                
                return True
                
            else:
                logger.error(f"❌ Launch failed: {message}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Investigation failed: {e}")
            return False

async def main():
    """Main function"""
    try:
        logger.info("🔬 Calculator Investigation Starting")
        logger.info("=" * 40)
        
        # Initialize investigation
        investigation = CalculatorInvestigation()
        
        # Run investigation
        success = await investigation.test_calculator_launch_behavior()
        
        if success:
            logger.info("🎉 Investigation completed successfully!")
        else:
            logger.error("❌ Investigation failed")
        
    except KeyboardInterrupt:
        logger.info("🛑 Investigation interrupted by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
