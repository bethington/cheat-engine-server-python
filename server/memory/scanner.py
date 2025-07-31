"""
Memory Scanner Module
Handles pattern scanning and memory searching operations
"""

import re
import logging
from typing import List, Optional, Dict, Any, Tuple, Iterator
from .reader import MemoryReader

logger = logging.getLogger(__name__)

class MemoryScanner:
    """Handles memory pattern scanning and searching"""
    
    def __init__(self):
        self.memory_reader: Optional[MemoryReader] = None
    
    def set_memory_reader(self, reader: MemoryReader):
        """Set the memory reader instance"""
        self.memory_reader = reader
    
    def scan_pattern(self, pattern: str, start_address: Optional[int] = None, 
                    region_size: Optional[int] = None) -> List[int]:
        """Scan memory for a byte pattern
        
        Args:
            pattern: Byte pattern in format "48 8B 05 ?? ?? ?? ??" where ?? are wildcards
            start_address: Starting address (optional, scans all memory if not specified)
            region_size: Size of region to scan (optional)
        
        Returns:
            List of addresses where pattern was found
        """
        if not self.memory_reader:
            raise Exception("Memory reader not set")
        
        try:
            # Parse the pattern
            pattern_bytes = self._parse_pattern(pattern)
            if not pattern_bytes:
                return []
            
            results = []
            
            if start_address is not None and region_size is not None:
                # Scan specific region
                results.extend(self._scan_region(pattern_bytes, start_address, region_size))
            else:
                # Scan all accessible memory regions
                regions = self.memory_reader.get_memory_regions()
                for region in regions:
                    # Skip regions that are too small or not readable
                    if (region['size'] < len(pattern_bytes) or 
                        'R' not in region['protection']):
                        continue
                    
                    try:
                        matches = self._scan_region(
                            pattern_bytes, 
                            region['base'], 
                            region['size']
                        )
                        results.extend(matches)
                    except Exception as e:
                        logger.debug(f"Error scanning region 0x{region['base']:08X}: {e}")
                        continue
            
            return sorted(results)
            
        except Exception as e:
            logger.error(f"Error in pattern scan: {e}")
            return []
    
    def _parse_pattern(self, pattern: str) -> Optional[Tuple[bytes, bytes]]:
        """Parse a pattern string into bytes and mask
        
        Args:
            pattern: Pattern string like "48 8B 05 ?? ?? ?? ??"
            
        Returns:
            Tuple of (pattern_bytes, mask_bytes) or None if invalid
        """
        try:
            # Remove extra whitespace and convert to uppercase
            pattern = re.sub(r'\s+', ' ', pattern.strip().upper())
            
            # Split into individual byte strings
            byte_strings = pattern.split(' ')
            
            pattern_bytes = bytearray()
            mask_bytes = bytearray()
            
            for byte_str in byte_strings:
                if byte_str == '??' or byte_str == '?':
                    # Wildcard byte
                    pattern_bytes.append(0x00)
                    mask_bytes.append(0x00)
                else:
                    # Literal byte
                    try:
                        byte_val = int(byte_str, 16)
                        pattern_bytes.append(byte_val)
                        mask_bytes.append(0xFF)
                    except ValueError:
                        logger.error(f"Invalid byte in pattern: {byte_str}")
                        return None
            
            if len(pattern_bytes) == 0:
                return None
                
            return (bytes(pattern_bytes), bytes(mask_bytes))
            
        except Exception as e:
            logger.error(f"Error parsing pattern: {e}")
            return None
    
    def _scan_region(self, pattern_data: Tuple[bytes, bytes], address: int, size: int) -> List[int]:
        """Scan a specific memory region for a pattern
        
        Args:
            pattern_data: Tuple of (pattern_bytes, mask_bytes)
            address: Starting address of region
            size: Size of region to scan
            
        Returns:
            List of addresses where pattern was found
        """
        pattern_bytes, mask_bytes = pattern_data
        pattern_len = len(pattern_bytes)
        
        if size < pattern_len:
            return []
        
        results = []
        chunk_size = min(1024 * 1024, size)  # 1MB chunks
        
        try:
            for offset in range(0, size, chunk_size - pattern_len + 1):
                chunk_address = address + offset
                read_size = min(chunk_size, size - offset)
                
                if read_size < pattern_len:
                    break
                
                # Read chunk
                data = self.memory_reader.read_memory_safe(chunk_address, read_size)
                if not data:
                    continue
                
                # Search for pattern in chunk
                matches = self._find_pattern_in_data(data, pattern_bytes, mask_bytes)
                
                # Convert relative offsets to absolute addresses
                for match_offset in matches:
                    absolute_address = chunk_address + match_offset
                    results.append(absolute_address)
            
            return results
            
        except Exception as e:
            logger.debug(f"Error scanning region 0x{address:08X}: {e}")
            return []
    
    def _find_pattern_in_data(self, data: bytes, pattern: bytes, mask: bytes) -> List[int]:
        """Find pattern matches within data
        
        Args:
            data: Data to search in
            pattern: Pattern bytes to find
            mask: Mask bytes (0xFF = must match, 0x00 = wildcard)
            
        Returns:
            List of offsets where pattern was found
        """
        matches = []
        pattern_len = len(pattern)
        data_len = len(data)
        
        if data_len < pattern_len:
            return matches
        
        for i in range(data_len - pattern_len + 1):
            match = True
            
            for j in range(pattern_len):
                if mask[j] == 0xFF:  # Must match exactly
                    if data[i + j] != pattern[j]:
                        match = False
                        break
                # If mask[j] == 0x00, it's a wildcard (always matches)
            
            if match:
                matches.append(i)
        
        return matches
    
    def find_pointers(self, target_address: int, search_regions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Find pointers that point to a specific address
        
        Args:
            target_address: Address to find pointers to
            search_regions: Optional list of region addresses to search in
            
        Returns:
            List of pointer information dictionaries
        """
        if not self.memory_reader:
            raise Exception("Memory reader not set")
        
        try:
            pointers = []
            
            # Determine pointer size based on process architecture
            if self.memory_reader.process_info.get('architecture') == 'x64':
                pointer_size = 8
                target_bytes = target_address.to_bytes(8, 'little')
            else:
                pointer_size = 4
                target_bytes = target_address.to_bytes(4, 'little')
            
            # Get regions to search
            if search_regions:
                regions = []
                all_regions = self.memory_reader.get_memory_regions()
                for region_addr_str in search_regions:
                    try:
                        region_addr = int(region_addr_str, 16) if isinstance(region_addr_str, str) else region_addr_str
                        region = next((r for r in all_regions if r['base'] == region_addr), None)
                        if region:
                            regions.append(region)
                    except ValueError:
                        continue
            else:
                regions = self.memory_reader.get_memory_regions()
            
            # Search each region
            for region in regions:
                # Skip non-readable regions
                if 'R' not in region['protection']:
                    continue
                
                try:
                    # Use pattern scanning to find the target address bytes
                    pattern = ' '.join(f'{b:02X}' for b in target_bytes)
                    matches = self._scan_region(
                        (target_bytes, b'\xFF' * len(target_bytes)),
                        region['base'],
                        region['size']
                    )
                    
                    for match_addr in matches:
                        # Verify it's actually a valid pointer location
                        # (aligned to pointer size boundary)
                        if match_addr % pointer_size == 0:
                            pointers.append({
                                'address': match_addr,
                                'value': target_address,
                                'region': region,
                                'type': 'direct'
                            })
                
                except Exception as e:
                    logger.debug(f"Error searching region 0x{region['base']:08X} for pointers: {e}")
                    continue
            
            return pointers
            
        except Exception as e:
            logger.error(f"Error finding pointers: {e}")
            return []
    
    def scan_for_value(self, value: Any, data_type: str, regions: Optional[List[Dict]] = None) -> List[int]:
        """Scan memory for a specific value
        
        Args:
            value: Value to search for
            data_type: Type of value ('int32', 'int64', 'float', 'double', 'string')
            regions: Optional list of regions to search in
            
        Returns:
            List of addresses where value was found
        """
        if not self.memory_reader:
            raise Exception("Memory reader not set")
        
        try:
            # Convert value to bytes based on type
            if data_type == 'int32':
                search_bytes = int(value).to_bytes(4, 'little', signed=True)
            elif data_type == 'uint32':
                search_bytes = int(value).to_bytes(4, 'little', signed=False)
            elif data_type == 'int64':
                search_bytes = int(value).to_bytes(8, 'little', signed=True)
            elif data_type == 'uint64':
                search_bytes = int(value).to_bytes(8, 'little', signed=False)
            elif data_type == 'float':
                import struct
                search_bytes = struct.pack('<f', float(value))
            elif data_type == 'double':
                import struct
                search_bytes = struct.pack('<d', float(value))
            elif data_type == 'string':
                search_bytes = str(value).encode('utf-8')
            else:
                raise Exception(f"Unsupported data type: {data_type}")
            
            # Create pattern from search bytes
            pattern = ' '.join(f'{b:02X}' for b in search_bytes)
            
            # Search in specified regions or all regions
            if regions:
                results = []
                for region in regions:
                    matches = self._scan_region(
                        (search_bytes, b'\xFF' * len(search_bytes)),
                        region['base'],
                        region['size']
                    )
                    results.extend(matches)
                return results
            else:
                return self.scan_pattern(pattern)
                
        except Exception as e:
            logger.error(f"Error scanning for value: {e}")
            return []
    
    def scan_changed_memory(self, old_scan: Dict[int, bytes], new_scan: Dict[int, bytes]) -> List[int]:
        """Compare two memory scans and find changed addresses
        
        Args:
            old_scan: Dictionary of address -> data from previous scan
            new_scan: Dictionary of address -> data from current scan
            
        Returns:
            List of addresses where memory has changed
        """
        changed_addresses = []
        
        for address in old_scan:
            if address in new_scan:
                if old_scan[address] != new_scan[address]:
                    changed_addresses.append(address)
        
        return sorted(changed_addresses)
    
    def create_memory_snapshot(self, regions: Optional[List[Dict]] = None) -> Dict[int, bytes]:
        """Create a snapshot of memory regions for later comparison
        
        Args:
            regions: Optional list of specific regions to snapshot
            
        Returns:
            Dictionary mapping addresses to memory data
        """
        if not self.memory_reader:
            raise Exception("Memory reader not set")
        
        snapshot = {}
        
        try:
            if not regions:
                regions = self.memory_reader.get_memory_regions()
            
            for region in regions:
                if 'R' not in region['protection'] or region['size'] > 50 * 1024 * 1024:
                    continue  # Skip non-readable or very large regions
                
                try:
                    data = self.memory_reader.read_memory_safe(region['base'], region['size'])
                    if data:
                        # Store in chunks to avoid memory issues
                        chunk_size = 1024 * 1024  # 1MB chunks
                        for offset in range(0, len(data), chunk_size):
                            chunk_addr = region['base'] + offset
                            chunk_data = data[offset:offset + chunk_size]
                            snapshot[chunk_addr] = chunk_data
                            
                except Exception as e:
                    logger.debug(f"Error snapshotting region 0x{region['base']:08X}: {e}")
                    continue
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error creating memory snapshot: {e}")
            return {}
