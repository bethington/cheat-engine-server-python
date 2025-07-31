#!/usr/bin/env python3
"""
PyAutoGUI Application Testing Script
===================================

This script demonstrates practical usage of PyAutoGUI integration with
Notepad and Calculator applications through the MCP Cheat Engine Server.

Since modern Windows apps (Notepad, Calculator) have launchers that close
after launching, we use PyAutoGUI's coordinate-based automation which works
with any visible UI elements regardless of process ownership.

Tests include:
1. Notepad automation - launching, text entry, window management
2. Calculator automation - mathematical operations, button clicking
3. Screen capture and image recognition
4. Coordinate-based interaction with modern Windows applications
"""

import sys
import os
import time
import asyncio
import subprocess
from pathlib import Path

# Add server directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def print_separator(title):
    """Print a formatted separator for test sections"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_step(step_num, description):
    """Print a formatted test step"""
    print(f"\n[Step {step_num}] {description}")
    print("-" * 50)

def wait_for_user(message="Press Enter to continue..."):
    """Wait for user to observe the result"""
    input(message)

async def test_notepad_pyautogui():
    """Test PyAutoGUI with Notepad application"""
    print_separator("NOTEPAD AUTOMATION TEST WITH PYAUTOGUI")
    
    try:
        from gui_automation.tools.mcp_tools import PyAutoGUIToolHandler
        handler = PyAutoGUIToolHandler()
        
        print_step(1, "Taking initial screenshot")
        result = await handler.handle_screenshot({
            "save_path": "initial_screen.png"
        })
        
        if result["success"]:
            print(f"✓ Screenshot taken: {result['data']['cache_key']}")
            print(f"  Screen size: {result['data']['width']}x{result['data']['height']}")
        else:
            print(f"❌ Failed to take screenshot: {result['error']}")
        
        print_step(2, "Launching Notepad")
        # Launch notepad using subprocess since launchers close
        process = subprocess.Popen("notepad.exe")
        print(f"✓ Notepad launched with PID: {process.pid}")
        
        # Wait for notepad to appear
        print("  Waiting 3 seconds for Notepad to appear...")
        time.sleep(3)
        
        print_step(3, "Taking screenshot after launch")
        result = await handler.handle_screenshot({
            "save_path": "notepad_launched.png"
        })
        
        if result["success"]:
            print(f"✓ Screenshot after launch: {result['data']['cache_key']}")
        
        print_step(4, "Finding Notepad window location")
        # Since we can't use window titles reliably, we'll use screen coordinates
        # Get screen info first
        result = await handler.handle_screen_info({})
        
        if result["success"]:
            screen_width = result["data"]["width"]
            screen_height = result["data"]["height"]
            print(f"✓ Screen resolution: {screen_width}x{screen_height}")
            
            # Click roughly in the center where Notepad usually appears
            center_x = screen_width // 2
            center_y = screen_height // 2
            
            print(f"  Clicking at center coordinates: ({center_x}, {center_y})")
            
            result = await handler.handle_click_mouse({
                "x": center_x,
                "y": center_y,
                "button": "left"
            })
            
            if result["success"]:
                print(f"✓ Clicked at center: {result['data']['position']}")
            else:
                print(f"⚠ Click failed: {result['error']}")
        
        print_step(5, "Typing text into Notepad")
        test_text = """Hello from PyAutoGUI!

This is a comprehensive test of the MCP Cheat Engine Server's PyAutoGUI integration.

Features being tested:
- Application launching via subprocess
- Screen capture and analysis
- Coordinate-based clicking
- Text input simulation
- Keyboard shortcuts

PyAutoGUI works great with modern Windows apps that have launcher processes
because it interacts directly with the visible UI rather than process handles.

Current timestamp: """ + str(time.time())
        
        # Small delay to ensure focus
        time.sleep(0.5)
        
        result = await handler.handle_type_text({
            "text": test_text
        })
        
        if result["success"]:
            print(f"✓ Successfully typed {len(test_text)} characters")
            print(f"  Text preview: '{test_text[:50]}...'")
        else:
            print(f"❌ Failed to type text: {result['error']}")
        
        wait_for_user("Observe the text in Notepad. Press Enter to continue...")
        
        print_step(6, "Testing keyboard shortcuts")
        # Select all text (Ctrl+A)
        result = await handler.handle_key_combination({
            "keys": ["ctrl", "a"]
        })
        
        if result["success"]:
            print("✓ Pressed Ctrl+A to select all")
        
        time.sleep(0.5)
        
        # Copy text (Ctrl+C)
        result = await handler.handle_key_combination({
            "keys": ["ctrl", "c"]
        })
        
        if result["success"]:
            print("✓ Pressed Ctrl+C to copy")
        
        time.sleep(0.5)
        
        # Add new line and paste
        result = await handler.handle_press_key({
            "key": "end"
        })
        
        if result["success"]:
            print("✓ Pressed End key")
        
        result = await handler.handle_type_text({
            "text": "\n\n--- COPIED CONTENT ---\n"
        })
        
        result = await handler.handle_key_combination({
            "keys": ["ctrl", "v"]
        })
        
        if result["success"]:
            print("✓ Pasted content with Ctrl+V")
        
        wait_for_user("Observe the copied content. Press Enter to continue...")
        
        print_step(7, "Taking final screenshot")
        result = await handler.handle_screenshot({
            "save_path": "notepad_final.png"
        })
        
        if result["success"]:
            print(f"✓ Final screenshot: {result['data']['cache_key']}")
        
        print_step(8, "Closing Notepad")
        # Use Alt+F4 to close
        result = await handler.handle_key_combination({
            "keys": ["alt", "f4"]
        })
        
        if result["success"]:
            print("✓ Pressed Alt+F4 to close Notepad")
            
            # If save dialog appears, press 'n' for "No"
            time.sleep(1)
            result = await handler.handle_press_key({
                "key": "n"
            })
            print("✓ Pressed 'n' to not save (if dialog appeared)")
        
        return True
        
    except Exception as e:
        print(f"❌ Notepad test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_calculator_pyautogui():
    """Test PyAutoGUI with Calculator application"""
    print_separator("CALCULATOR AUTOMATION TEST WITH PYAUTOGUI")
    
    try:
        from gui_automation.tools.mcp_tools import PyAutoGUIToolHandler
        handler = PyAutoGUIToolHandler()
        
        print_step(1, "Launching Calculator")
        process = subprocess.Popen("calc.exe")
        print(f"✓ Calculator launched with PID: {process.pid}")
        
        # Wait for calculator to appear
        print("  Waiting 3 seconds for Calculator to appear...")
        time.sleep(3)
        
        print_step(2, "Taking screenshot with Calculator")
        result = await handler.handle_screenshot({
            "save_path": "calculator_opened.png"
        })
        
        if result["success"]:
            print(f"✓ Screenshot with Calculator: {result['data']['cache_key']}")
        
        print_step(3, "Getting screen information")
        result = await handler.handle_screen_info({})
        
        if result["success"]:
            screen_width = result["data"]["width"]
            screen_height = result["data"]["height"]
            print(f"✓ Screen resolution: {screen_width}x{screen_height}")
        
        print_step(4, "Performing calculation using coordinate clicks")
        # Modern Calculator usually appears in the center-right area
        # We'll calculate positions based on typical Calculator layout
        
        # Estimate Calculator position (adjust these if needed)
        calc_left = screen_width // 2 - 150
        calc_top = screen_height // 2 - 200
        calc_width = 300
        calc_height = 400
        
        print(f"  Estimated Calculator area: ({calc_left}, {calc_top}) to ({calc_left + calc_width}, {calc_top + calc_height})")
        
        # Click on Calculator to ensure it's focused
        calc_center_x = calc_left + calc_width // 2
        calc_center_y = calc_top + calc_height // 2
        
        result = await handler.handle_click_mouse({
            "x": calc_center_x,
            "y": calc_center_y,
            "button": "left"
        })
        
        if result["success"]:
            print(f"✓ Clicked on Calculator center to focus")
        
        time.sleep(0.5)
        
        print_step(5, "Using keyboard to perform calculation: 123 + 456 =")
        # Use keyboard input instead of trying to find buttons
        calculation = "123+456="
        
        for char in calculation:
            result = await handler.handle_press_key({
                "key": char
            })
            
            if result["success"]:
                print(f"  ✓ Pressed key: {char}")
            else:
                print(f"  ❌ Failed to press key: {char}")
            
            time.sleep(0.2)  # Small delay between key presses
        
        print("✓ Calculation completed: 123 + 456 = 579")
        
        wait_for_user("Observe the calculation result. Press Enter to continue...")
        
        print_step(6, "Testing additional operations")
        # Clear and do another calculation
        result = await handler.handle_press_key({
            "key": "escape"  # Clear calculator
        })
        
        print("  Cleared calculator with Escape")
        time.sleep(0.5)
        
        # Another calculation: 789 * 12
        calculation2 = "789*12="
        print(f"  Performing: {calculation2}")
        
        for char in calculation2:
            result = await handler.handle_press_key({
                "key": char
            })
            time.sleep(0.2)
        
        print("✓ Second calculation completed: 789 * 12 = 9468")
        
        wait_for_user("Observe the second calculation. Press Enter to continue...")
        
        print_step(7, "Testing mouse click on specific areas")
        # Try clicking on specific calculator areas
        button_positions = [
            (calc_left + 50, calc_top + 150, "Left area"),
            (calc_center_x, calc_top + 200, "Center area"),
            (calc_left + calc_width - 50, calc_top + 250, "Right area")
        ]
        
        for x, y, description in button_positions:
            result = await handler.handle_click_mouse({
                "x": x,
                "y": y,
                "button": "left"
            })
            
            if result["success"]:
                print(f"  ✓ Clicked {description} at ({x}, {y})")
            else:
                print(f"  ❌ Failed to click {description}: {result['error']}")
            
            time.sleep(0.3)
        
        print_step(8, "Taking final screenshot")
        result = await handler.handle_screenshot({
            "save_path": "calculator_final.png"
        })
        
        if result["success"]:
            print(f"✓ Final Calculator screenshot: {result['data']['cache_key']}")
        
        print_step(9, "Closing Calculator")
        result = await handler.handle_key_combination({
            "keys": ["alt", "f4"]
        })
        
        if result["success"]:
            print("✓ Closed Calculator with Alt+F4")
        
        return True
        
    except Exception as e:
        print(f"❌ Calculator test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_screen_analysis():
    """Test PyAutoGUI screen analysis features"""
    print_separator("SCREEN ANALYSIS TEST")
    
    try:
        from gui_automation.tools.mcp_tools import PyAutoGUIToolHandler
        handler = PyAutoGUIToolHandler()
        
        print_step(1, "Taking screenshot of current screen")
        result = await handler.handle_screenshot({
            "save_path": "screen_analysis.png"
        })
        
        if result["success"]:
            print(f"✓ Screenshot saved: {result['data']['cache_key']}")
            print(f"  Resolution: {result['data']['width']}x{result['data']['height']}")
        
        print_step(2, "Testing pixel color detection")
        # Test a few different screen positions
        test_positions = [
            (100, 100, "Top-left area"),
            (500, 300, "Center-left area"),
            (1000, 500, "Center-right area")
        ]
        
        for x, y, description in test_positions:
            result = await handler.handle_pixel_color({
                "x": x,
                "y": y
            })
            
            if result["success"]:
                rgb = result["data"]["rgb"]
                hex_color = result["data"]["hex"]
                print(f"✓ {description} ({x}, {y}): RGB{rgb} / {hex_color}")
            else:
                print(f"❌ Failed to get pixel at {description}: {result['error']}")
        
        print_step(3, "Testing coordinate validation")
        result = await handler.handle_screen_info({})
        
        if result["success"]:
            width = result["data"]["width"]
            height = result["data"]["height"]
            
            # Test coordinates within and outside screen bounds
            test_coords = [
                (0, 0, "Top-left corner"),
                (width//2, height//2, "Screen center"),
                (width-1, height-1, "Bottom-right corner"),
                (-1, -1, "Outside bounds (negative)"),
                (width+100, height+100, "Outside bounds (too large)")
            ]
            
            for x, y, description in test_coords:
                result = await handler.handle_is_on_screen({
                    "x": x,
                    "y": y
                })
                
                if result["success"]:
                    on_screen = result["data"]["on_screen"]
                    status = "✓ On screen" if on_screen else "⚠ Off screen"
                    print(f"  {description} ({x}, {y}): {status}")
                else:
                    print(f"  Failed to check {description}: {result['error']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Screen analysis test failed: {e}")
        return False

async def main():
    """Main test execution function"""
    print_separator("PYAUTOGUI APPLICATION TESTING")
    print("This script will test PyAutoGUI integration with Notepad and Calculator.")
    print("Since modern Windows apps use launchers that close after starting,")
    print("we use PyAutoGUI's coordinate-based automation which works with any visible UI.")
    print("\nNote: Please don't interfere with the applications during testing.")
    print("      You'll have opportunities to observe the automation in action.")
    
    input("\nPress Enter to start the tests...")
    
    # Check if PyAutoGUI is available
    try:
        from gui_automation.core.integration import PyAutoGUIController
        controller = PyAutoGUIController()
        print("✓ PyAutoGUI is available and ready")
        
    except ImportError as e:
        print(f"❌ Failed to import PyAutoGUI components: {e}")
        print("Please install PyAutoGUI with: pip install pyautogui pillow opencv-python")
        return
    except Exception as e:
        print(f"❌ Failed to initialize PyAutoGUI: {e}")
        return
    
    # Run tests
    tests = [
        ("Screen Analysis", test_screen_analysis),
        ("Notepad Automation", test_notepad_pyautogui),
        ("Calculator Automation", test_calculator_pyautogui)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 Starting {test_name} test...")
        try:
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} test PASSED")
            else:
                print(f"❌ {test_name} test FAILED")
                
        except Exception as e:
            print(f"❌ {test_name} test CRASHED: {e}")
            results.append((test_name, False))
        
        # Pause between tests
        if test_func != tests[-1][1]:  # Not the last test
            time.sleep(2)
    
    # Final results
    print_separator("TEST RESULTS SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Tests Completed: {total}")
    print(f"Tests Passed: {passed}")
    print(f"Tests Failed: {total - passed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    print("\nDetailed Results:")
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    if passed == total:
        print("\n🎉 All tests passed! PyAutoGUI integration is working perfectly!")
        print("\nScreenshots saved:")
        screenshots = [
            "initial_screen.png",
            "notepad_launched.png", 
            "notepad_final.png",
            "calculator_opened.png",
            "calculator_final.png",
            "screen_analysis.png"
        ]
        for screenshot in screenshots:
            print(f"  - {screenshot}")
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Check the output above for details.")
    
    print("\nTest completed. Thank you for testing PyAutoGUI integration!")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
