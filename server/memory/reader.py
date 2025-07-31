"""
Memory Reader Module
Handles direct memory reading operations from attached processes
"""

import ctypes
import ctypes.wintypes
import struct
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Memory protection constants
PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
PAGE_GUARD = 0x100
PAGE_NOCACHE = 0x200
PAGE_WRITECOMBINE = 0x400

# Memory types
MEM_COMMIT = 0x1000
MEM_FREE = 0x10000
MEM_RESERVE = 0x2000
MEM_IMAGE = 0x1000000
MEM_MAPPED = 0x40000
MEM_PRIVATE = 0x20000

@dataclass
class MemoryRegion:
    """Memory region information"""
    base_address: int
    size: int
    protection: int
    state: int
    type: int
    allocation_base: int
    allocation_protect: int
    
    @property
    def protection_string(self) -> str:
        """Human-readable protection string"""
        protections = []
        
        if self.protection & PAGE_EXECUTE:
            protections.append("E")
        if self.protection & PAGE_READWRITE:
            protections.append("RW")
        elif self.protection & PAGE_READONLY:
            protections.append("R")
        elif self.protection & PAGE_WRITECOPY:
            protections.append("WC")
        
        if self.protection & PAGE_GUARD:
            protections.append("G")
        if self.protection & PAGE_NOCACHE:
            protections.append("NC")
        
        return "+".join(protections) if protections else "---"
    
    @property
    def type_string(self) -> str:
        """Human-readable type string"""
        if self.type & MEM_IMAGE:
            return "Image"
        elif self.type & MEM_MAPPED:
            return "Mapped"
        elif self.type & MEM_PRIVATE:
            return "Private"
        else:
            return "Unknown"

class MemoryReader:
    """Handles memory reading operations"""
    
    def __init__(self):
        self.kernel32 = ctypes.windll.kernel32
        self.process_handle = None
        self.process_info = None
        self.cached_regions = None
    
    def set_process(self, process_info: Dict[str, Any]):
        """Set the target process for memory operations"""
        self.process_info = process_info
        self.process_handle = process_info.get('handle')
        self.cached_regions = None  # Clear cache
        
        if not self.process_handle:
            raise Exception("Invalid process handle")
    
    def clear_process(self):
        """Clear current process"""
        self.process_handle = None
        self.process_info = None
        self.cached_regions = None
    
    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        """Read raw memory from the attached process"""
        if not self.process_handle:
            raise Exception("No process attached")
        
        try:
            # Allocate buffer for the data
            buffer = ctypes.create_string_buffer(size)
            bytes_read = ctypes.wintypes.SIZE_T()
            
            # Read the memory
            success = self.kernel32.ReadProcessMemory(
                self.process_handle,
                ctypes.c_void_p(address),
                buffer,
                size,
                ctypes.byref(bytes_read)
            )
            
            if not success:
                error_code = ctypes.get_last_error()
                logger.warning(f"Failed to read memory at 0x{address:08X}: Error {error_code}")
                return None
            
            if bytes_read.value != size:
                logger.warning(f"Partial read at 0x{address:08X}: {bytes_read.value}/{size} bytes")
                return buffer.raw[:bytes_read.value]
            
            return buffer.raw
            
        except Exception as e:
            logger.error(f"Exception reading memory at 0x{address:08X}: {e}")
            return None
    
    def read_memory_safe(self, address: int, size: int) -> Optional[bytes]:
        """Safely read memory, handling access violations gracefully"""
        try:
            # Check if the memory region is accessible
            if not self.is_memory_accessible(address, size):
                return None
            
            return self.read_memory(address, size)
            
        except Exception as e:
            logger.debug(f"Safe read failed at 0x{address:08X}: {e}")
            return None
    
    def read_int32(self, address: int) -> Optional[int]:
        """Read a 32-bit integer from memory"""
        data = self.read_memory(address, 4)
        if data and len(data) >= 4:
            return struct.unpack('<I', data[:4])[0]
        return None
    
    def read_int64(self, address: int) -> Optional[int]:
        """Read a 64-bit integer from memory"""
        data = self.read_memory(address, 8)
        if data and len(data) >= 8:
            return struct.unpack('<Q', data[:8])[0]
        return None
    
    def read_float(self, address: int) -> Optional[float]:
        """Read a float from memory"""
        data = self.read_memory(address, 4)
        if data and len(data) >= 4:
            return struct.unpack('<f', data[:4])[0]
        return None
    
    def read_double(self, address: int) -> Optional[float]:
        """Read a double from memory"""
        data = self.read_memory(address, 8)
        if data and len(data) >= 8:
            return struct.unpack('<d', data[:8])[0]
        return None
    
    def read_string(self, address: int, max_length: int = 256, encoding: str = 'utf-8') -> Optional[str]:
        """Read a null-terminated string from memory"""
        data = self.read_memory(address, max_length)
        if not data:
            return None
        
        try:
            # Find null terminator
            null_pos = data.find(b'\x00')
            if null_pos != -1:
                data = data[:null_pos]
            
            # Try to decode
            if encoding == 'utf-8':
                return data.decode('utf-8', errors='ignore')
            elif encoding == 'utf-16':
                return data.decode('utf-16le', errors='ignore')
            elif encoding == 'ascii':
                return data.decode('ascii', errors='ignore')
            else:
                return data.decode('utf-8', errors='ignore')
                
        except Exception as e:
            logger.debug(f"String decode error at 0x{address:08X}: {e}")
            return None
    
    def read_pointer(self, address: int) -> Optional[int]:
        """Read a pointer value (size depends on process architecture)"""
        if not self.process_info:
            return None
        
        if self.process_info.get('architecture') == 'x64':
            return self.read_int64(address)
        else:
            return self.read_int32(address)
    
    def get_memory_regions(self, refresh: bool = False) -> List[Dict[str, Any]]:
        """Get all memory regions of the process"""
        if not self.process_handle:
            raise Exception("No process attached")
        
        if self.cached_regions and not refresh:
            return self.cached_regions
        
        regions = []
        address = 0
        
        class MEMORY_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BaseAddress", ctypes.c_void_p),
                ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", ctypes.wintypes.DWORD),
                ("RegionSize", ctypes.c_size_t),
                ("State", ctypes.wintypes.DWORD),
                ("Protect", ctypes.wintypes.DWORD),
                ("Type", ctypes.wintypes.DWORD),
            ]
        
        mbi = MEMORY_BASIC_INFORMATION()
        
        while True:
            result = self.kernel32.VirtualQueryEx(
                self.process_handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi)
            )
            
            if result == 0:
                break
            
            # Only include committed memory regions
            if mbi.State == MEM_COMMIT:
                region_info = {
                    'base': mbi.BaseAddress,
                    'size': mbi.RegionSize,
                    'protection': self._protection_to_string(mbi.Protect),
                    'type': self._type_to_string(mbi.Type),
                    'raw_protection': mbi.Protect,
                    'raw_type': mbi.Type
                }
                regions.append(region_info)
            
            address = mbi.BaseAddress + mbi.RegionSize
            
            # Prevent infinite loop on 32-bit systems
            if address >= 0x7FFFFFFF and self.process_info.get('architecture') != 'x64':
                break
        
        self.cached_regions = regions
        return regions
    
    def _protection_to_string(self, protection: int) -> str:
        """Convert protection flags to string"""
        if protection & PAGE_EXECUTE_READWRITE:
            return "ERW"
        elif protection & PAGE_EXECUTE_READ:
            return "ER"
        elif protection & PAGE_EXECUTE:
            return "E"
        elif protection & PAGE_READWRITE:
            return "RW"
        elif protection & PAGE_READONLY:
            return "R"
        elif protection & PAGE_WRITECOPY:
            return "WC"
        elif protection & PAGE_NOACCESS:
            return "---"
        else:
            return "UNK"
    
    def _type_to_string(self, mem_type: int) -> str:
        """Convert memory type to string"""
        if mem_type & MEM_IMAGE:
            return "Image"
        elif mem_type & MEM_MAPPED:
            return "Mapped"
        elif mem_type & MEM_PRIVATE:
            return "Private"
        else:
            return "Unknown"
    
    def is_memory_accessible(self, address: int, size: int) -> bool:
        """Check if a memory region is accessible for reading"""
        try:
            regions = self.get_memory_regions()
            
            for region in regions:
                region_start = region['base']
                region_end = region_start + region['size']
                
                # Check if address range falls within this region
                if (address >= region_start and 
                    address + size <= region_end and
                    region['raw_protection'] & (PAGE_READONLY | PAGE_READWRITE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE)):
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking memory accessibility: {e}")
            return False
    
    def find_memory_region(self, address: int) -> Optional[Dict[str, Any]]:
        """Find the memory region containing the given address"""
        try:
            regions = self.get_memory_regions()
            
            for region in regions:
                if region['base'] <= address < region['base'] + region['size']:
                    return region
            
            return None
            
        except Exception:
            return None
