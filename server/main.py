#!/usr/bin/env python3

import os
import sys
import argparse
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import Tool

# Import our modules
from process.manager import ProcessManager
from memory.reader import MemoryReader
from memory.scanner import MemoryScanner
from memory.analyzer import StructureAnalyzer
from memory.symbols import SymbolManager
from utils.validators import validate_address, validate_size
from utils.formatters import format_memory_data, format_process_info
from config.settings import ServerConfig
from config.whitelist import ProcessWhitelist

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Parse command line arguments
parser = argparse.ArgumentParser(description="MCP Cheat Engine Server")
parser.add_argument(
    "--config", 
    default="config.json", 
    help="Configuration file path"
)
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
parser.add_argument("--read-only", action="store_true", help="Enable read-only mode")
args = parser.parse_args()

# Initialize server
mcp = FastMCP("cheat-engine-server")

# Global state
server_config = ServerConfig()
process_manager = ProcessManager()
memory_reader = MemoryReader()
memory_scanner = MemoryScanner()
structure_analyzer = StructureAnalyzer()
symbol_manager = SymbolManager()
process_whitelist = ProcessWhitelist()

# Current attached process
current_process = None


@mcp.tool()
def list_processes() -> str:
    """Enumerate running processes available for attachment"""
    try:
        logger.info("Listing available processes")
        processes = process_manager.list_processes()
        
        # Filter by whitelist if configured
        if process_whitelist.is_enabled():
            processes = [p for p in processes if process_whitelist.is_allowed(p['name'])]
        
        if not processes:
            return "No processes available or accessible"
        
        return format_process_info(processes)
    
    except Exception as e:
        logger.error(f"Error listing processes: {e}")
        return f"Error listing processes: {str(e)}"


@mcp.tool()
def attach_to_process(identifier: str, access_level: str = "read") -> str:
    """Attach debugger to specified process
    
    Args:
        identifier: Process name or PID
        access_level: "read" for read-only access, "debug" for full debug access
    """
    global current_process
    
    try:
        logger.info(f"Attempting to attach to process: {identifier}")
        
        # Validate access level
        if access_level not in ["read", "debug"]:
            return "Error: access_level must be 'read' or 'debug'"
        
        # Force read-only mode if server is configured for it
        if args.read_only and access_level == "debug":
            access_level = "read"
            logger.warning("Forced read-only mode, downgrading access level")
        
        # Check whitelist
        if process_whitelist.is_enabled():
            if isinstance(identifier, str) and not identifier.isdigit():
                if not process_whitelist.is_allowed(identifier):
                    return f"Error: Process '{identifier}' not in whitelist"
        
        # Attempt attachment
        process_info = process_manager.attach_process(identifier, access_level)
        current_process = process_info
        
        # Initialize memory reader with the process
        memory_reader.set_process(process_info)
        
        logger.info(f"Successfully attached to process {process_info['pid']} ({process_info['name']})")
        
        return f"Successfully attached to process:\n{format_process_info([process_info])}"
    
    except Exception as e:
        logger.error(f"Error attaching to process: {e}")
        return f"Error attaching to process: {str(e)}"


@mcp.tool()
def get_process_info() -> str:
    """Get detailed information about currently attached process"""
    try:
        if not current_process:
            return "No process currently attached"
        
        logger.info(f"Getting process info for PID {current_process['pid']}")
        
        # Get detailed process information
        detailed_info = process_manager.get_detailed_info(current_process['pid'])
        
        return format_process_info([detailed_info], detailed=True)
    
    except Exception as e:
        logger.error(f"Error getting process info: {e}")
        return f"Error getting process info: {str(e)}"


@mcp.tool()
def detach_process() -> str:
    """Safely detach from current process"""
    global current_process
    
    try:
        if not current_process:
            return "No process currently attached"
        
        logger.info(f"Detaching from process {current_process['pid']}")
        
        process_manager.detach_process()
        memory_reader.clear_process()
        current_process = None
        
        return "Successfully detached from process"
    
    except Exception as e:
        logger.error(f"Error detaching from process: {e}")
        return f"Error detaching from process: {str(e)}"


@mcp.tool()
def read_memory_region(address: str, size: int, data_type: str = "raw") -> str:
    """Read and analyze a memory region from attached process
    
    Args:
        address: Memory address in hex format (e.g., "0x12345678")
        size: Number of bytes to read
        data_type: Type of data to interpret ("raw", "int32", "float", "string", "auto")
    """
    try:
        if not current_process:
            return "Error: No process currently attached"
        
        # Validate inputs
        addr = validate_address(address)
        if addr is None:
            return f"Error: Invalid address format: {address}"
        
        if not validate_size(size):
            return f"Error: Invalid size: {size}"
        
        logger.info(f"Reading memory at {address}, size {size}, type {data_type}")
        
        # Read memory
        data = memory_reader.read_memory(addr, size)
        if data is None:
            return f"Error: Could not read memory at address {address}"
        
        # Format the data according to requested type
        formatted_data = format_memory_data(data, data_type, addr)
        
        return formatted_data
    
    except Exception as e:
        logger.error(f"Error reading memory: {e}")
        return f"Error reading memory: {str(e)}"


@mcp.tool()
def scan_memory(pattern: str, region_start: str = None, region_size: int = None) -> str:
    """Pattern scanning within memory regions
    
    Args:
        pattern: Byte pattern to search for (hex format, e.g., "48 8B 05 ?? ?? ?? ??")
        region_start: Starting address for scan (optional, scans all accessible memory if not specified)
        region_size: Size of region to scan (optional)
    """
    try:
        if not current_process:
            return "Error: No process currently attached"
        
        logger.info(f"Scanning memory for pattern: {pattern}")
        
        # Parse region parameters
        start_addr = None
        if region_start:
            start_addr = validate_address(region_start)
            if start_addr is None:
                return f"Error: Invalid region start address: {region_start}"
        
        if region_size and not validate_size(region_size):
            return f"Error: Invalid region size: {region_size}"
        
        # Perform scan
        results = memory_scanner.scan_pattern(pattern, start_addr, region_size)
        
        if not results:
            return f"No matches found for pattern: {pattern}"
        
        # Format results
        result_text = f"Found {len(results)} matches for pattern '{pattern}':\n"
        for i, addr in enumerate(results[:20]):  # Limit to first 20 results
            result_text += f"{i+1:3d}: 0x{addr:08X}\n"
        
        if len(results) > 20:
            result_text += f"... and {len(results) - 20} more matches"
        
        return result_text
    
    except Exception as e:
        logger.error(f"Error scanning memory: {e}")
        return f"Error scanning memory: {str(e)}"


@mcp.tool()
def get_memory_regions() -> str:
    """Get virtual memory layout of attached process"""
    try:
        if not current_process:
            return "Error: No process currently attached"
        
        logger.info("Getting memory regions")
        
        regions = memory_reader.get_memory_regions()
        if not regions:
            return "No memory regions found"
        
        result = "Memory Regions:\n"
        result += "Base Address    Size        Protection  Type\n"
        result += "-" * 50 + "\n"
        
        for region in regions:
            result += f"0x{region['base']:08X}  {region['size']:>10}  {region['protection']:<10} {region['type']}\n"
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting memory regions: {e}")
        return f"Error getting memory regions: {str(e)}"


@mcp.tool()
def analyze_data_structure(address: str, max_size: int = 256, hint_type: str = None) -> str:
    """Analyze memory region and identify probable data structures
    
    Args:
        address: Starting address to analyze
        max_size: Maximum structure size to analyze
        hint_type: Expected structure type hint (optional)
    """
    try:
        if not current_process:
            return "Error: No process currently attached"
        
        addr = validate_address(address)
        if addr is None:
            return f"Error: Invalid address format: {address}"
        
        if not validate_size(max_size):
            return f"Error: Invalid max_size: {max_size}"
        
        logger.info(f"Analyzing data structure at {address}")
        
        # Read the memory for analysis
        data = memory_reader.read_memory(addr, max_size)
        if data is None:
            return f"Error: Could not read memory at address {address}"
        
        # Analyze the structure
        analysis = structure_analyzer.analyze_structure(data, addr, hint_type)
        
        return format_memory_data(data, "structure", addr, analysis)
    
    except Exception as e:
        logger.error(f"Error analyzing data structure: {e}")
        return f"Error analyzing data structure: {str(e)}"


@mcp.tool()
def find_pointers(target_address: str, search_regions: List[str] = None) -> str:
    """Find pointer chains targeting specific addresses
    
    Args:
        target_address: Address to find pointers to
        search_regions: List of memory region addresses to search in (optional)
    """
    try:
        if not current_process:
            return "Error: No process currently attached"
        
        target_addr = validate_address(target_address)
        if target_addr is None:
            return f"Error: Invalid target address format: {target_address}"
        
        logger.info(f"Finding pointers to {target_address}")
        
        # Find pointers
        pointers = memory_scanner.find_pointers(target_addr, search_regions)
        
        if not pointers:
            return f"No pointers found targeting address {target_address}"
        
        result = f"Found {len(pointers)} pointers to {target_address}:\n"
        for i, pointer_info in enumerate(pointers[:20]):  # Limit to first 20
            result += f"{i+1:3d}: 0x{pointer_info['address']:08X} -> 0x{pointer_info['value']:08X}\n"
        
        if len(pointers) > 20:
            result += f"... and {len(pointers) - 20} more pointers"
        
        return result
    
    except Exception as e:
        logger.error(f"Error finding pointers: {e}")
        return f"Error finding pointers: {str(e)}"


@mcp.tool()
def disassemble_region(address: str, size: int = 64) -> str:
    """Disassemble assembly code from memory region
    
    Args:
        address: Starting address for disassembly
        size: Number of bytes to disassemble
    """
    try:
        if not current_process:
            return "Error: No process currently attached"
        
        addr = validate_address(address)
        if addr is None:
            return f"Error: Invalid address format: {address}"
        
        if not validate_size(size):
            return f"Error: Invalid size: {size}"
        
        logger.info(f"Disassembling at {address}, size {size}")
        
        # Read memory
        data = memory_reader.read_memory(addr, size)
        if data is None:
            return f"Error: Could not read memory at address {address}"
        
        # Disassemble
        disasm = structure_analyzer.disassemble_code(data, addr)
        
        if not disasm:
            return f"Could not disassemble code at {address}"
        
        result = f"Disassembly at {address}:\n"
        result += "-" * 40 + "\n"
        for instruction in disasm:
            result += f"0x{instruction['address']:08X}: {instruction['mnemonic']:<8} {instruction['op_str']}\n"
        
        return result
    
    except Exception as e:
        logger.error(f"Error disassembling: {e}")
        return f"Error disassembling: {str(e)}"


def main():
    """Main server entry point"""
    try:
        # Initialize server configuration
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug mode enabled")
        
        if args.read_only:
            logger.info("Read-only mode enabled")
        
        # Load configuration
        server_config.load_config(args.config)
        
        # Initialize whitelist
        process_whitelist.load_whitelist(server_config.get_whitelist_path())
        
        logger.info("MCP Cheat Engine Server starting...")
        
        # Run the MCP server
        mcp.run()
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if current_process:
            try:
                process_manager.detach_process()
                logger.info("Cleaned up process attachment")
            except:
                pass


if __name__ == "__main__":
    main()
def read_file(path: str) -> str:
    """Read file contents"""
    path_obj = Path(path)

    if not path_obj.exists():
        return f"File not found: {path}"

    if not path_obj.is_file():
        return f"Path is not a file: {path}"

    try:
        with path_obj.open("r", encoding="utf-8") as f:
            content = f.read()

        return f"Contents of {path}:\n{content}"

    except UnicodeDecodeError:
        return f"File is not text or uses unsupported encoding: {path}"
    except PermissionError:
        return f"Permission denied reading: {path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@mcp.tool()
def get_file_info(path: str) -> str:
    """Get information about a file"""
    path_obj = Path(path)

    if not path_obj.exists():
        return f"Path not found: {path}"

    try:
        stat_info = path_obj.stat()
        file_type = "directory" if path_obj.is_dir() else "file"

        info = [
            f"Path: {path}",
            f"Type: {file_type}",
            f"Size: {stat_info.st_size} bytes",
            f"Modified: {stat_info.st_mtime}",
            f"Created: {stat_info.st_ctime}",
        ]

        info_text = "\n".join(info)
        return f"File Info:\n{info_text}"

    except PermissionError:
        return f"Permission denied accessing: {path}"
    except Exception as e:
        return f"Error getting file info: {str(e)}"


# Main execution
if __name__ == "__main__":
    # Debug output if enabled
    if args.debug:
        print("Starting File Manager MCP Server...", file=sys.stderr)
        print(f"Workspace: {args.workspace}", file=sys.stderr)

    # Run the server
    mcp.run()
