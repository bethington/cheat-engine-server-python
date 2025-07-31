"""
Symbol Manager Module
Handles debug symbols and PDB file integration
"""

import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import struct

logger = logging.getLogger(__name__)

@dataclass
class SymbolInfo:
    """Information about a debug symbol"""
    name: str
    address: int
    size: Optional[int]
    type: str
    module: str
    file: Optional[str] = None
    line: Optional[int] = None

@dataclass
class ModuleInfo:
    """Information about a loaded module"""
    name: str
    base_address: int
    size: int
    path: str
    has_symbols: bool = False
    symbol_file: Optional[str] = None

class SymbolManager:
    """Manages debug symbols and symbol resolution"""
    
    def __init__(self):
        self.modules: Dict[str, ModuleInfo] = {}
        self.symbols: Dict[int, SymbolInfo] = {}
        self.symbol_cache: Dict[str, List[SymbolInfo]] = {}
        
        # Try to import symbol libraries
        self.pefile_available = False
        self.pdbparse_available = False
        
        try:
            import pefile
            self.pefile_available = True
        except ImportError:
            logger.info("pefile not available - PE symbol parsing disabled")
        
        try:
            import pdbparse
            self.pdbparse_available = True
        except ImportError:
            logger.info("pdbparse not available - PDB symbol parsing disabled")
    
    def load_module_symbols(self, module_path: str, base_address: int) -> bool:
        """Load symbols for a specific module
        
        Args:
            module_path: Path to the module file
            base_address: Base address where module is loaded
            
        Returns:
            True if symbols were successfully loaded
        """
        try:
            if not os.path.exists(module_path):
                logger.warning(f"Module file not found: {module_path}")
                return False
            
            module_name = os.path.basename(module_path)
            
            # Create module info
            module_info = ModuleInfo(
                name=module_name,
                base_address=base_address,
                size=self._get_module_size(module_path),
                path=module_path
            )
            
            # Try to load PE exports first
            if self.pefile_available:
                pe_symbols = self._load_pe_exports(module_path, base_address)
                if pe_symbols:
                    for symbol in pe_symbols:
                        self.symbols[symbol.address] = symbol
                    module_info.has_symbols = True
                    logger.info(f"Loaded {len(pe_symbols)} PE exports for {module_name}")
            
            # Try to find and load PDB file
            pdb_path = self._find_pdb_file(module_path)
            if pdb_path and self.pdbparse_available:
                pdb_symbols = self._load_pdb_symbols(pdb_path, base_address)
                if pdb_symbols:
                    for symbol in pdb_symbols:
                        self.symbols[symbol.address] = symbol
                    module_info.has_symbols = True
                    module_info.symbol_file = pdb_path
                    logger.info(f"Loaded {len(pdb_symbols)} PDB symbols for {module_name}")
            
            self.modules[module_name] = module_info
            return module_info.has_symbols
            
        except Exception as e:
            logger.error(f"Error loading symbols for {module_path}: {e}")
            return False
    
    def _get_module_size(self, module_path: str) -> int:
        """Get the size of a module file"""
        try:
            if self.pefile_available:
                import pefile
                pe = pefile.PE(module_path)
                return pe.OPTIONAL_HEADER.SizeOfImage
            else:
                # Fallback to file size
                return os.path.getsize(module_path)
        except Exception:
            return os.path.getsize(module_path)
    
    def _load_pe_exports(self, module_path: str, base_address: int) -> List[SymbolInfo]:
        """Load exported symbols from PE file"""
        if not self.pefile_available:
            return []
        
        try:
            import pefile
            
            pe = pefile.PE(module_path)
            symbols = []
            
            if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
                for export in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                    if export.name:
                        symbol_name = export.name.decode('utf-8', errors='ignore')
                        symbol_address = base_address + export.address
                        
                        symbol = SymbolInfo(
                            name=symbol_name,
                            address=symbol_address,
                            size=None,
                            type='function',
                            module=os.path.basename(module_path)
                        )
                        symbols.append(symbol)
            
            return symbols
            
        except Exception as e:
            logger.debug(f"Error loading PE exports: {e}")
            return []
    
    def _find_pdb_file(self, module_path: str) -> Optional[str]:
        """Find the PDB file associated with a module"""
        try:
            # Try same directory with .pdb extension
            base_name = os.path.splitext(module_path)[0]
            pdb_path = base_name + '.pdb'
            
            if os.path.exists(pdb_path):
                return pdb_path
            
            # Try common symbol directories
            symbol_dirs = [
                os.path.dirname(module_path),
                os.path.join(os.path.dirname(module_path), 'symbols'),
                r'C:\Windows\Symbols',
                r'C:\Symbols'
            ]
            
            pdb_name = os.path.basename(base_name) + '.pdb'
            
            for symbol_dir in symbol_dirs:
                if os.path.exists(symbol_dir):
                    pdb_path = os.path.join(symbol_dir, pdb_name)
                    if os.path.exists(pdb_path):
                        return pdb_path
            
            return None
            
        except Exception as e:
            logger.debug(f"Error finding PDB file: {e}")
            return None
    
    def _load_pdb_symbols(self, pdb_path: str, base_address: int) -> List[SymbolInfo]:
        """Load symbols from PDB file"""
        if not self.pdbparse_available:
            return []
        
        try:
            import pdbparse
            
            pdb = pdbparse.parse(pdb_path)
            symbols = []
            
            # Load public symbols
            if hasattr(pdb, 'STREAM_PUBLICS') and pdb.STREAM_PUBLICS:
                for symbol in pdb.STREAM_PUBLICS:
                    if hasattr(symbol, 'name') and hasattr(symbol, 'offset'):
                        symbol_info = SymbolInfo(
                            name=symbol.name,
                            address=base_address + symbol.offset,
                            size=getattr(symbol, 'size', None),
                            type='public',
                            module=os.path.basename(pdb_path),
                            file=getattr(symbol, 'filename', None),
                            line=getattr(symbol, 'line', None)
                        )
                        symbols.append(symbol_info)
            
            # Load global symbols
            if hasattr(pdb, 'STREAM_GSYM') and pdb.STREAM_GSYM:
                for symbol in pdb.STREAM_GSYM:
                    if hasattr(symbol, 'name') and hasattr(symbol, 'offset'):
                        symbol_info = SymbolInfo(
                            name=symbol.name,
                            address=base_address + symbol.offset,
                            size=getattr(symbol, 'size', None),
                            type='global',
                            module=os.path.basename(pdb_path)
                        )
                        symbols.append(symbol_info)
            
            return symbols
            
        except Exception as e:
            logger.debug(f"Error loading PDB symbols: {e}")
            return []
    
    def resolve_address(self, address: int) -> Optional[SymbolInfo]:
        """Resolve an address to a symbol
        
        Args:
            address: Address to resolve
            
        Returns:
            SymbolInfo if found, None otherwise
        """
        # Exact match first
        if address in self.symbols:
            return self.symbols[address]
        
        # Find closest symbol before this address
        closest_symbol = None
        closest_distance = float('inf')
        
        for sym_addr, symbol in self.symbols.items():
            if sym_addr <= address:
                distance = address - sym_addr
                if distance < closest_distance:
                    # Check if address falls within symbol size if known
                    if symbol.size is None or distance < symbol.size:
                        closest_distance = distance
                        closest_symbol = symbol
        
        return closest_symbol
    
    def find_symbol_by_name(self, name: str, module: Optional[str] = None) -> List[SymbolInfo]:
        """Find symbols by name
        
        Args:
            name: Symbol name to search for (supports wildcards)
            module: Optional module name to filter by
            
        Returns:
            List of matching symbols
        """
        matching_symbols = []
        
        # Use cache if available
        cache_key = f"{name}:{module or '*'}"
        if cache_key in self.symbol_cache:
            return self.symbol_cache[cache_key]
        
        try:
            import fnmatch
            
            for symbol in self.symbols.values():
                # Check module filter
                if module and symbol.module.lower() != module.lower():
                    continue
                
                # Check name match (with wildcard support)
                if fnmatch.fnmatch(symbol.name.lower(), name.lower()):
                    matching_symbols.append(symbol)
            
            # Cache the result
            self.symbol_cache[cache_key] = matching_symbols
            
        except Exception as e:
            logger.error(f"Error searching symbols: {e}")
        
        return matching_symbols
    
    def get_symbol_info(self, address: int) -> Dict[str, Any]:
        """Get detailed symbol information for an address
        
        Args:
            address: Address to get info for
            
        Returns:
            Dictionary with symbol information
        """
        symbol = self.resolve_address(address)
        
        if symbol:
            return {
                'address': f"0x{address:08X}",
                'symbol_name': symbol.name,
                'symbol_address': f"0x{symbol.address:08X}",
                'offset': address - symbol.address,
                'module': symbol.module,
                'type': symbol.type,
                'file': symbol.file,
                'line': symbol.line,
                'size': symbol.size
            }
        else:
            # Try to determine which module contains this address
            containing_module = None
            for module in self.modules.values():
                if (module.base_address <= address < 
                    module.base_address + module.size):
                    containing_module = module
                    break
            
            return {
                'address': f"0x{address:08X}",
                'symbol_name': None,
                'module': containing_module.name if containing_module else None,
                'module_offset': (address - containing_module.base_address) if containing_module else None,
                'has_symbols': containing_module.has_symbols if containing_module else False
            }
    
    def get_function_boundaries(self, address: int) -> Optional[Tuple[int, int]]:
        """Get the start and end addresses of a function containing the given address
        
        Args:
            address: Address within the function
            
        Returns:
            Tuple of (start_address, end_address) or None if not found
        """
        symbol = self.resolve_address(address)
        
        if symbol and symbol.type == 'function' and symbol.size:
            return (symbol.address, symbol.address + symbol.size)
        
        # If no size information, try to estimate using nearby symbols
        if symbol:
            next_symbol_addr = None
            for sym_addr in sorted(self.symbols.keys()):
                if sym_addr > symbol.address:
                    next_symbol_addr = sym_addr
                    break
            
            if next_symbol_addr:
                return (symbol.address, next_symbol_addr)
            else:
                # Fallback to a reasonable function size estimate
                return (symbol.address, symbol.address + 0x1000)
        
        return None
    
    def export_symbols(self, format: str = 'text') -> str:
        """Export symbols to various formats
        
        Args:
            format: Export format ('text', 'csv', 'json')
            
        Returns:
            Formatted symbol data
        """
        if format == 'text':
            return self._export_text()
        elif format == 'csv':
            return self._export_csv()
        elif format == 'json':
            return self._export_json()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_text(self) -> str:
        """Export symbols as text"""
        output = []
        output.append("Symbol Table:")
        output.append("=" * 60)
        output.append(f"{'Address':<12} {'Name':<30} {'Module':<20} {'Type'}")
        output.append("-" * 60)
        
        for address in sorted(self.symbols.keys()):
            symbol = self.symbols[address]
            output.append(f"0x{address:08X}  {symbol.name:<30} {symbol.module:<20} {symbol.type}")
        
        return '\n'.join(output)
    
    def _export_csv(self) -> str:
        """Export symbols as CSV"""
        output = []
        output.append("Address,Name,Module,Type,Size,File,Line")
        
        for address in sorted(self.symbols.keys()):
            symbol = self.symbols[address]
            output.append(f"0x{address:08X},{symbol.name},{symbol.module},{symbol.type},"
                         f"{symbol.size or ''},{symbol.file or ''},{symbol.line or ''}")
        
        return '\n'.join(output)
    
    def _export_json(self) -> str:
        """Export symbols as JSON"""
        import json
        
        symbols_data = []
        for address, symbol in self.symbols.items():
            symbols_data.append({
                'address': f"0x{address:08X}",
                'name': symbol.name,
                'module': symbol.module,
                'type': symbol.type,
                'size': symbol.size,
                'file': symbol.file,
                'line': symbol.line
            })
        
        return json.dumps(symbols_data, indent=2)
    
    def clear_cache(self):
        """Clear the symbol cache"""
        self.symbol_cache.clear()
    
    def get_loaded_modules(self) -> List[Dict[str, Any]]:
        """Get information about loaded modules"""
        return [
            {
                'name': module.name,
                'base_address': f"0x{module.base_address:08X}",
                'size': module.size,
                'path': module.path,
                'has_symbols': module.has_symbols,
                'symbol_file': module.symbol_file,
                'symbol_count': len([s for s in self.symbols.values() if s.module == module.name])
            }
            for module in self.modules.values()
        ]
