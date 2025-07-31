"""
Cheat Engine Bridge Module
Provides direct interface to Cheat Engine API and processes
"""

import logging
import ctypes
import ctypes.wintypes
import struct
import winreg
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class CEInstallation:
    """Information about Cheat Engine installation"""
    path: str
    version: str
    executable: str
    available: bool

@dataclass
class CEProcess:
    """Cheat Engine process information"""
    pid: int
    name: str
    handle: int
    base_address: int
    modules: List[Dict[str, Any]]

class CheatEngineBridge:
    """Bridge interface to Cheat Engine functionality"""
    
    def __init__(self):
        self.ce_installation = self._detect_cheat_engine()
        self.kernel32 = ctypes.windll.kernel32
        self.user32 = ctypes.windll.user32
        self.psapi = ctypes.windll.psapi
        self._setup_windows_api()
    
    def _detect_cheat_engine(self) -> CEInstallation:
        """Detect Cheat Engine installation"""
        
        # Common installation paths
        common_paths = [
            r"C:\dbengine",
            r"C:\Program Files\Cheat Engine",
            r"C:\Program Files (x86)\Cheat Engine",
            r"C:\Cheat Engine"
        ]
        
        # Check registry for installation path
        registry_path = None
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                              r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Cheat Engine") as key:
                registry_path, _ = winreg.QueryValueEx(key, "InstallLocation")
        except FileNotFoundError:
            try:
                # Try 32-bit registry on 64-bit system
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                  r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Cheat Engine") as key:
                    registry_path, _ = winreg.QueryValueEx(key, "InstallLocation")
            except FileNotFoundError:
                pass
        
        if registry_path:
            common_paths.insert(0, registry_path)
        
        # Check each path
        for path in common_paths:
            ce_path = Path(path)
            if ce_path.exists():
                # Try different executable names in order of preference
                exe_candidates = [
                    "dbengine-x86_64.exe",
                    "cheatengine-x86_64.exe",
                    "cheatengine.exe"
                ]
                
                exe_path = None
                for exe_name in exe_candidates:
                    candidate_path = ce_path / exe_name
                    if candidate_path.exists():
                        exe_path = candidate_path
                        break
                
                if exe_path:
                    version = self._get_ce_version(exe_path)
                    return CEInstallation(
                        path=str(ce_path),
                        version=version,
                        executable=str(exe_path),
                        available=True
                    )
        
        return CEInstallation(
            path="",
            version="",
            executable="",
            available=False
        )
    
    def _get_ce_version(self, exe_path: Path) -> str:
        """Get Cheat Engine version from executable"""
        try:
            # Try to get version from file properties
            import win32api
            try:
                info = win32api.GetFileVersionInfo(str(exe_path), "\\")
                ms = info['FileVersionMS']
                ls = info['FileVersionLS']
                version = f"{win32api.HIWORD(ms)}.{win32api.LOWORD(ms)}.{win32api.HIWORD(ls)}.{win32api.LOWORD(ls)}"
                return version
            except ImportError:
                # Fallback if win32api not available
                return "Unknown"
        except Exception as e:
            logger.warning(f"Could not determine CE version: {e}")
            return "Unknown"
    
    def _setup_windows_api(self):
        """Setup Windows API function signatures"""
        
        # OpenProcess
        self.kernel32.OpenProcess.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD]
        self.kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
        
        # ReadProcessMemory
        self.kernel32.ReadProcessMemory.argtypes = [
            ctypes.wintypes.HANDLE,  # hProcess
            ctypes.wintypes.LPCVOID,  # lpBaseAddress
            ctypes.wintypes.LPVOID,   # lpBuffer
            ctypes.c_size_t,          # nSize
            ctypes.POINTER(ctypes.c_size_t)  # lpNumberOfBytesRead
        ]
        self.kernel32.ReadProcessMemory.restype = ctypes.wintypes.BOOL
        
        # WriteProcessMemory
        self.kernel32.WriteProcessMemory.argtypes = [
            ctypes.wintypes.HANDLE,   # hProcess
            ctypes.wintypes.LPVOID,   # lpBaseAddress
            ctypes.wintypes.LPCVOID,  # lpBuffer
            ctypes.c_size_t,          # nSize
            ctypes.POINTER(ctypes.c_size_t)  # lpNumberOfBytesWritten
        ]
        self.kernel32.WriteProcessMemory.restype = ctypes.wintypes.BOOL
        
        # VirtualQueryEx
        self.kernel32.VirtualQueryEx.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.wintypes.LPCVOID,
            ctypes.wintypes.LPVOID,
            ctypes.c_size_t
        ]
        self.kernel32.VirtualQueryEx.restype = ctypes.c_size_t
        
        # CloseHandle
        self.kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
        
        # EnumProcessModules
        self.psapi.EnumProcessModules.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.POINTER(ctypes.wintypes.HMODULE),
            ctypes.wintypes.DWORD,
            ctypes.POINTER(ctypes.wintypes.DWORD)
        ]
        self.psapi.EnumProcessModules.restype = ctypes.wintypes.BOOL
        
        # GetModuleInformation
        self.psapi.GetModuleInformation.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.wintypes.HMODULE,
            ctypes.wintypes.LPVOID,
            ctypes.wintypes.DWORD
        ]
        self.psapi.GetModuleInformation.restype = ctypes.wintypes.BOOL
    
    def get_ce_installation_info(self) -> Dict[str, Any]:
        """Get Cheat Engine installation information"""
        return {
            'available': self.ce_installation.available,
            'path': self.ce_installation.path,
            'version': self.ce_installation.version,
            'executable': self.ce_installation.executable
        }
    
    def open_process_handle(self, pid: int, access_rights: int = 0x1F0FFF) -> Optional[int]:
        """Open a handle to a process
        
        Args:
            pid: Process ID
            access_rights: Access rights (default: PROCESS_ALL_ACCESS)
            
        Returns:
            Process handle or None if failed
        """
        try:
            handle = self.kernel32.OpenProcess(access_rights, False, pid)
            if handle:
                return handle
            else:
                error = ctypes.get_last_error()
                logger.error(f"Failed to open process {pid}: Error {error}")
                return None
        except Exception as e:
            logger.error(f"Exception opening process {pid}: {e}")
            return None
    
    def close_process_handle(self, handle: int) -> bool:
        """Close a process handle"""
        try:
            return bool(self.kernel32.CloseHandle(handle))
        except Exception as e:
            logger.error(f"Error closing handle {handle}: {e}")
            return False
    
    def read_process_memory(self, handle: int, address: int, size: int) -> Optional[bytes]:
        """Read memory from process
        
        Args:
            handle: Process handle
            address: Memory address
            size: Number of bytes to read
            
        Returns:
            Bytes read or None if failed
        """
        try:
            buffer = ctypes.create_string_buffer(size)
            bytes_read = ctypes.c_size_t()
            
            success = self.kernel32.ReadProcessMemory(
                handle,
                ctypes.c_void_p(address),
                buffer,
                size,
                ctypes.byref(bytes_read)
            )
            
            if success:
                return buffer.raw[:bytes_read.value]
            else:
                error = ctypes.get_last_error()
                logger.error(f"ReadProcessMemory failed: Error {error}")
                return None
                
        except Exception as e:
            logger.error(f"Exception reading memory at 0x{address:X}: {e}")
            return None
    
    def write_process_memory(self, handle: int, address: int, data: bytes) -> bool:
        """Write memory to process (READ-ONLY MODE - NOT IMPLEMENTED)
        
        This method is intentionally not implemented for safety.
        The server operates in read-only mode.
        """
        logger.warning("Write operations are disabled in read-only mode")
        return False
    
    def query_memory_info(self, handle: int, address: int) -> Optional[Dict[str, Any]]:
        """Query memory information at address"""
        
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
        
        try:
            mbi = MEMORY_BASIC_INFORMATION()
            size = self.kernel32.VirtualQueryEx(
                handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi)
            )
            
            if size:
                return {
                    'base_address': mbi.BaseAddress,
                    'allocation_base': mbi.AllocationBase,
                    'allocation_protect': mbi.AllocationProtect,
                    'region_size': mbi.RegionSize,
                    'state': mbi.State,
                    'protect': mbi.Protect,
                    'type': mbi.Type
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error querying memory at 0x{address:X}: {e}")
            return None
    
    def enum_process_modules(self, handle: int) -> List[Dict[str, Any]]:
        """Enumerate modules in a process"""
        modules = []
        
        try:
            # Get module count
            module_handles = (ctypes.wintypes.HMODULE * 1024)()
            bytes_needed = ctypes.wintypes.DWORD()
            
            success = self.psapi.EnumProcessModules(
                handle,
                module_handles,
                ctypes.sizeof(module_handles),
                ctypes.byref(bytes_needed)
            )
            
            if not success:
                return modules
            
            module_count = bytes_needed.value // ctypes.sizeof(ctypes.wintypes.HMODULE)
            
            # Get module information
            class MODULEINFO(ctypes.Structure):
                _fields_ = [
                    ("lpBaseOfDll", ctypes.c_void_p),
                    ("SizeOfImage", ctypes.wintypes.DWORD),
                    ("EntryPoint", ctypes.c_void_p),
                ]
            
            for i in range(min(module_count, 1024)):
                if module_handles[i]:
                    module_info = MODULEINFO()
                    success = self.psapi.GetModuleInformation(
                        handle,
                        module_handles[i],
                        ctypes.byref(module_info),
                        ctypes.sizeof(module_info)
                    )
                    
                    if success:
                        # Get module name
                        module_name = self._get_module_name(handle, module_handles[i])
                        
                        modules.append({
                            'handle': module_handles[i],
                            'name': module_name,
                            'base_address': module_info.lpBaseOfDll,
                            'size': module_info.SizeOfImage,
                            'entry_point': module_info.EntryPoint
                        })
            
            return modules
            
        except Exception as e:
            logger.error(f"Error enumerating modules: {e}")
            return modules
    
    def _get_module_name(self, handle: int, module_handle: int) -> str:
        """Get module name from handle"""
        try:
            # Try GetModuleFileNameEx
            buffer = ctypes.create_unicode_buffer(260)  # MAX_PATH
            length = self.psapi.GetModuleFileNameExW(
                handle,
                module_handle,
                buffer,
                260
            )
            
            if length:
                full_path = buffer.value
                return Path(full_path).name
            else:
                return f"Module_{module_handle:X}"
                
        except Exception:
            return f"Module_{module_handle:X}"
    
    def find_pattern_in_memory(self, handle: int, pattern: bytes, start_address: int = 0, 
                             end_address: int = 0x7FFFFFFF, alignment: int = 1) -> List[int]:
        """Find byte pattern in process memory
        
        Args:
            handle: Process handle
            pattern: Byte pattern to search for
            start_address: Start search address
            end_address: End search address
            alignment: Memory alignment for search
            
        Returns:
            List of addresses where pattern was found
        """
        found_addresses = []
        current_address = start_address
        chunk_size = 1024 * 1024  # 1MB chunks
        
        try:
            while current_address < end_address:
                # Query memory region
                memory_info = self.query_memory_info(handle, current_address)
                if not memory_info:
                    current_address += 0x1000  # Skip 4KB
                    continue
                
                # Skip if region is not committed or readable
                if (memory_info['state'] != 0x1000 or  # MEM_COMMIT
                    memory_info['protect'] & 0x01 or   # PAGE_NOACCESS
                    memory_info['protect'] & 0x100):   # PAGE_GUARD
                    current_address = memory_info['base_address'] + memory_info['region_size']
                    continue
                
                # Read memory in chunks
                region_start = memory_info['base_address']
                region_size = memory_info['region_size']
                
                for offset in range(0, region_size, chunk_size):
                    chunk_address = region_start + offset
                    read_size = min(chunk_size, region_size - offset)
                    
                    data = self.read_process_memory(handle, chunk_address, read_size)
                    if data:
                        # Search for pattern in chunk
                        pattern_addresses = self._search_pattern_in_data(
                            data, pattern, chunk_address, alignment
                        )
                        found_addresses.extend(pattern_addresses)
                
                current_address = region_start + region_size
                
                # Limit results to prevent memory issues
                if len(found_addresses) > 10000:
                    logger.warning("Pattern search found too many results, truncating")
                    break
            
            return found_addresses
            
        except Exception as e:
            logger.error(f"Error in pattern search: {e}")
            return found_addresses
    
    def _search_pattern_in_data(self, data: bytes, pattern: bytes, base_address: int, 
                               alignment: int) -> List[int]:
        """Search for pattern in data chunk"""
        addresses = []
        
        for i in range(0, len(data) - len(pattern) + 1, alignment):
            if data[i:i+len(pattern)] == pattern:
                addresses.append(base_address + i)
        
        return addresses
    
    def resolve_pointer_chain(self, handle: int, base_address: int, 
                            offsets: List[int]) -> Optional[int]:
        """Resolve a pointer chain
        
        Args:
            handle: Process handle
            base_address: Base address to start from
            offsets: List of offsets to follow
            
        Returns:
            Final address or None if failed
        """
        try:
            current_address = base_address
            
            for i, offset in enumerate(offsets):
                if i < len(offsets) - 1:
                    # Read pointer value (assuming 64-bit)
                    pointer_data = self.read_process_memory(handle, current_address + offset, 8)
                    if not pointer_data:
                        return None
                    
                    # Unpack as 64-bit pointer
                    try:
                        current_address = struct.unpack('<Q', pointer_data)[0]
                    except struct.error:
                        return None
                else:
                    # Final offset
                    current_address += offset
            
            return current_address
            
        except Exception as e:
            logger.error(f"Error resolving pointer chain: {e}")
            return None
    
    def create_ce_process_info(self, pid: int) -> Optional[CEProcess]:
        """Create CEProcess object with full process information"""
        try:
            handle = self.open_process_handle(pid)
            if not handle:
                return None
            
            # Get process name
            import psutil
            try:
                process = psutil.Process(pid)
                process_name = process.name()
            except psutil.NoSuchProcess:
                process_name = f"Process_{pid}"
            
            # Get modules
            modules = self.enum_process_modules(handle)
            
            # Get base address (first module's base address)
            base_address = modules[0]['base_address'] if modules else 0
            
            return CEProcess(
                pid=pid,
                name=process_name,
                handle=handle,
                base_address=base_address,
                modules=modules
            )
            
        except Exception as e:
            logger.error(f"Error creating CE process info for PID {pid}: {e}")
            return None
    
    def get_detailed_memory_map(self, handle: int) -> List[Dict[str, Any]]:
        """Get detailed memory map of process"""
        memory_regions = []
        current_address = 0
        
        try:
            while current_address < 0x7FFFFFFF:  # 2GB limit for 32-bit compat
                memory_info = self.query_memory_info(handle, current_address)
                if not memory_info:
                    current_address += 0x1000
                    continue
                
                # Add region info
                region = {
                    'base_address': memory_info['base_address'],
                    'region_size': memory_info['region_size'],
                    'state': self._memory_state_to_string(memory_info['state']),
                    'protect': self._memory_protect_to_string(memory_info['protect']),
                    'type': self._memory_type_to_string(memory_info['type']),
                    'readable': self._is_memory_readable(memory_info['protect']),
                    'writable': self._is_memory_writable(memory_info['protect']),
                    'executable': self._is_memory_executable(memory_info['protect'])
                }
                
                memory_regions.append(region)
                current_address = memory_info['base_address'] + memory_info['region_size']
                
                # Prevent infinite loops
                if len(memory_regions) > 10000:
                    break
            
            return memory_regions
            
        except Exception as e:
            logger.error(f"Error getting memory map: {e}")
            return memory_regions
    
    def _memory_state_to_string(self, state: int) -> str:
        """Convert memory state constant to string"""
        states = {
            0x1000: "MEM_COMMIT",
            0x10000: "MEM_FREE",
            0x2000: "MEM_RESERVE"
        }
        return states.get(state, f"Unknown_{state:X}")
    
    def _memory_protect_to_string(self, protect: int) -> str:
        """Convert memory protection constant to string"""
        protections = {
            0x01: "PAGE_NOACCESS",
            0x02: "PAGE_READONLY",
            0x04: "PAGE_READWRITE",
            0x08: "PAGE_WRITECOPY",
            0x10: "PAGE_EXECUTE",
            0x20: "PAGE_EXECUTE_READ",
            0x40: "PAGE_EXECUTE_READWRITE",
            0x80: "PAGE_EXECUTE_WRITECOPY"
        }
        
        base_protect = protect & 0xFF
        result = protections.get(base_protect, f"Unknown_{base_protect:X}")
        
        # Add modifiers
        if protect & 0x100:
            result += " | PAGE_GUARD"
        if protect & 0x200:
            result += " | PAGE_NOCACHE"
        if protect & 0x400:
            result += " | PAGE_WRITECOMBINE"
        
        return result
    
    def _memory_type_to_string(self, mem_type: int) -> str:
        """Convert memory type constant to string"""
        types = {
            0x1000000: "MEM_IMAGE",
            0x40000: "MEM_MAPPED",
            0x20000: "MEM_PRIVATE"
        }
        return types.get(mem_type, f"Unknown_{mem_type:X}")
    
    def _is_memory_readable(self, protect: int) -> bool:
        """Check if memory is readable"""
        readable_protects = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}
        return (protect & 0xFF) in readable_protects
    
    def _is_memory_writable(self, protect: int) -> bool:
        """Check if memory is writable"""
        writable_protects = {0x04, 0x08, 0x40, 0x80}
        return (protect & 0xFF) in writable_protects
    
    def _is_memory_executable(self, protect: int) -> bool:
        """Check if memory is executable"""
        executable_protects = {0x10, 0x20, 0x40, 0x80}
        return (protect & 0xFF) in executable_protects
