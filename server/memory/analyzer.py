"""
Memory Analyzer Module
Handles data structure analysis and pattern recognition
"""

import struct
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import re

try:
    import capstone
    CAPSTONE_AVAILABLE = True
except ImportError:
    CAPSTONE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Capstone not available - disassembly features disabled")

logger = logging.getLogger(__name__)

@dataclass
class FieldInfo:
    """Information about a structure field"""
    offset: int
    size: int
    type: str
    name: str
    value: Any
    confidence: float

@dataclass
class StructureInfo:
    """Information about an analyzed structure"""
    base_address: int
    total_size: int
    fields: List[FieldInfo]
    confidence: float
    name: Optional[str] = None

class StructureAnalyzer:
    """Analyzes memory data to identify probable data structures"""
    
    def __init__(self):
        self.known_patterns = self._initialize_patterns()
        
        # Initialize Capstone for disassembly
        if CAPSTONE_AVAILABLE:
            try:
                self.cs_x86 = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
                self.cs_x64 = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
                self.cs_x86.detail = True
                self.cs_x64.detail = True
            except Exception as e:
                logger.warning(f"Failed to initialize Capstone: {e}")
                self.cs_x86 = None
                self.cs_x64 = None
        else:
            self.cs_x86 = None
            self.cs_x64 = None
    
    def _initialize_patterns(self) -> Dict[str, Any]:
        """Initialize known data patterns for structure detection"""
        return {
            'vtable_patterns': [
                # Common C++ vtable patterns
                b'\x00\x00\x00\x00',  # NULL entries
                b'\xFF\xFF\xFF\xFF',  # Invalid pointers
            ],
            'string_patterns': [
                # Common string prefixes
                rb'[A-Za-z0-9_\-\.\s]',
            ],
            'number_patterns': {
                'small_int': (0, 1000),
                'large_int': (1000, 0xFFFFFFFF),
                'negative_int': (-1000, 0),
            }
        }
    
    def analyze_structure(self, data: bytes, base_address: int, hint_type: Optional[str] = None) -> StructureInfo:
        """Analyze memory data to identify probable structure layout
        
        Args:
            data: Raw memory data
            base_address: Base address of the data
            hint_type: Optional hint about expected structure type
            
        Returns:
            StructureInfo object with analysis results
        """
        try:
            fields = []
            offset = 0
            
            while offset < len(data) - 4:  # Need at least 4 bytes
                field_info = self._analyze_field(data, offset, base_address + offset)
                if field_info:
                    fields.append(field_info)
                    offset += field_info.size
                else:
                    offset += 1  # Move forward if no field detected
            
            # Calculate overall confidence
            total_confidence = sum(f.confidence for f in fields) / len(fields) if fields else 0.0
            
            structure = StructureInfo(
                base_address=base_address,
                total_size=len(data),
                fields=fields,
                confidence=total_confidence,
                name=self._guess_structure_name(fields, hint_type)
            )
            
            return structure
            
        except Exception as e:
            logger.error(f"Error analyzing structure: {e}")
            return StructureInfo(
                base_address=base_address,
                total_size=len(data),
                fields=[],
                confidence=0.0
            )
    
    def _analyze_field(self, data: bytes, offset: int, address: int) -> Optional[FieldInfo]:
        """Analyze a potential field at the given offset"""
        remaining = len(data) - offset
        if remaining < 1:
            return None
        
        # Try different field types in order of likelihood
        
        # 1. Try pointer (4 or 8 bytes)
        if remaining >= 8:
            ptr_field = self._try_pointer_field(data, offset, address, 8)
            if ptr_field and ptr_field.confidence > 0.7:
                return ptr_field
        
        if remaining >= 4:
            ptr_field = self._try_pointer_field(data, offset, address, 4)
            if ptr_field and ptr_field.confidence > 0.7:
                return ptr_field
        
        # 2. Try integer types
        if remaining >= 4:
            int_field = self._try_integer_field(data, offset, address, 4)
            if int_field and int_field.confidence > 0.5:
                return int_field
        
        if remaining >= 2:
            int_field = self._try_integer_field(data, offset, address, 2)
            if int_field and int_field.confidence > 0.5:
                return int_field
        
        # 3. Try float
        if remaining >= 4:
            float_field = self._try_float_field(data, offset, address)
            if float_field and float_field.confidence > 0.5:
                return float_field
        
        # 4. Try string
        string_field = self._try_string_field(data, offset, address)
        if string_field and string_field.confidence > 0.3:
            return string_field
        
        # 5. Default to byte
        return FieldInfo(
            offset=offset,
            size=1,
            type="uint8",
            name=f"byte_{offset:X}",
            value=data[offset],
            confidence=0.1
        )
    
    def _try_pointer_field(self, data: bytes, offset: int, address: int, size: int) -> Optional[FieldInfo]:
        """Try to identify a pointer field"""
        if len(data) - offset < size:
            return None
        
        try:
            if size == 4:
                value = struct.unpack('<I', data[offset:offset+4])[0]
            else:
                value = struct.unpack('<Q', data[offset:offset+8])[0]
            
            # Heuristics for pointer validation
            confidence = 0.0
            
            # Check if it looks like a valid memory address
            if size == 4:
                # 32-bit pointer heuristics
                if 0x00400000 <= value <= 0x7FFFFFFF:  # Typical user space
                    confidence += 0.6
                elif 0x10000 <= value <= 0x00400000:  # Lower user space
                    confidence += 0.3
            else:
                # 64-bit pointer heuristics
                if 0x000000010000 <= value <= 0x00007FFFFFFFFFFF:  # User space
                    confidence += 0.6
                elif 0xFFFF800000000000 <= value <= 0xFFFFFFFFFFFFFFFF:  # Kernel space
                    confidence += 0.4
            
            # Check alignment
            if value % 4 == 0:
                confidence += 0.2
            if value % 8 == 0:
                confidence += 0.1
            
            # Check for NULL
            if value == 0:
                confidence = 0.8  # NULL pointers are very common
            
            type_name = f"ptr{size*8}"
            field_name = f"ptr_{offset:X}"
            
            return FieldInfo(
                offset=offset,
                size=size,
                type=type_name,
                name=field_name,
                value=f"0x{value:0{size*2}X}",
                confidence=min(confidence, 1.0)
            )
            
        except Exception:
            return None
    
    def _try_integer_field(self, data: bytes, offset: int, address: int, size: int) -> Optional[FieldInfo]:
        """Try to identify an integer field"""
        if len(data) - offset < size:
            return None
        
        try:
            if size == 4:
                value = struct.unpack('<I', data[offset:offset+4])[0]
                signed_value = struct.unpack('<i', data[offset:offset+4])[0]
                type_name = "uint32"
            elif size == 2:
                value = struct.unpack('<H', data[offset:offset+2])[0]
                signed_value = struct.unpack('<h', data[offset:offset+2])[0]
                type_name = "uint16"
            else:
                value = data[offset]
                signed_value = struct.unpack('<b', data[offset:offset+1])[0]
                type_name = "uint8"
            
            confidence = 0.3  # Base confidence for integers
            
            # Heuristics for integer validation
            if 0 <= value <= 1000:
                confidence += 0.3  # Small positive numbers are common
            elif value == 0xFFFFFFFF or value == 0xFFFF or value == 0xFF:
                confidence += 0.2  # Max values are common
            
            # Check if signed value makes more sense
            if abs(signed_value) < value and signed_value != 0:
                value = signed_value
                type_name = type_name.replace('uint', 'int')
                confidence += 0.1
            
            return FieldInfo(
                offset=offset,
                size=size,
                type=type_name,
                name=f"field_{offset:X}",
                value=value,
                confidence=confidence
            )
            
        except Exception:
            return None
    
    def _try_float_field(self, data: bytes, offset: int, address: int) -> Optional[FieldInfo]:
        """Try to identify a float field"""
        if len(data) - offset < 4:
            return None
        
        try:
            value = struct.unpack('<f', data[offset:offset+4])[0]
            
            confidence = 0.0
            
            # Heuristics for float validation
            if not (value != value):  # Check for NaN
                if -1000000.0 <= value <= 1000000.0:
                    confidence += 0.4
                    if 0.0 <= value <= 1.0:
                        confidence += 0.2  # Common range for normalized values
                    elif abs(value) < 10.0:
                        confidence += 0.1  # Small floats are common
            
            # Check for special values
            if value == 0.0 or value == 1.0:
                confidence += 0.2
            
            return FieldInfo(
                offset=offset,
                size=4,
                type="float",
                name=f"float_{offset:X}",
                value=value,
                confidence=confidence
            )
            
        except Exception:
            return None
    
    def _try_string_field(self, data: bytes, offset: int, address: int) -> Optional[FieldInfo]:
        """Try to identify a string field"""
        try:
            # Look for printable ASCII characters
            string_data = []
            current_offset = offset
            
            while current_offset < len(data):
                byte_val = data[current_offset]
                
                if byte_val == 0:  # Null terminator
                    break
                elif 32 <= byte_val <= 126:  # Printable ASCII
                    string_data.append(chr(byte_val))
                    current_offset += 1
                else:
                    break
            
            if len(string_data) >= 3:  # Minimum string length
                string_value = ''.join(string_data)
                confidence = 0.3
                
                # Heuristics for string validation
                if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', string_value):
                    confidence += 0.3  # Identifier-like strings
                elif ' ' in string_value:
                    confidence += 0.2  # Natural language strings
                
                return FieldInfo(
                    offset=offset,
                    size=len(string_data) + 1,  # Include null terminator
                    type="string",
                    name=f"str_{offset:X}",
                    value=string_value,
                    confidence=confidence
                )
            
            return None
            
        except Exception:
            return None
    
    def _guess_structure_name(self, fields: List[FieldInfo], hint_type: Optional[str]) -> Optional[str]:
        """Guess the structure name based on field patterns"""
        if hint_type:
            return hint_type
        
        # Simple heuristics based on field patterns
        pointer_count = sum(1 for f in fields if 'ptr' in f.type)
        string_count = sum(1 for f in fields if f.type == 'string')
        
        if pointer_count > len(fields) * 0.5:
            return "vtable_or_object"
        elif string_count > 0:
            return "string_container"
        elif len(fields) < 5:
            return "simple_struct"
        else:
            return "complex_struct"
    
    def disassemble_code(self, data: bytes, base_address: int, architecture: str = "x86") -> List[Dict[str, Any]]:
        """Disassemble code from memory data
        
        Args:
            data: Raw code bytes
            base_address: Base address of the code
            architecture: Target architecture ("x86" or "x64")
            
        Returns:
            List of instruction dictionaries
        """
        if not CAPSTONE_AVAILABLE:
            return [{"error": "Capstone disassembly library not available"}]
        
        try:
            if architecture == "x64":
                cs = self.cs_x64
            else:
                cs = self.cs_x86
            
            if not cs:
                return [{"error": "Disassembler not initialized"}]
            
            instructions = []
            
            for insn in cs.disasm(data, base_address):
                inst_info = {
                    'address': insn.address,
                    'mnemonic': insn.mnemonic,
                    'op_str': insn.op_str,
                    'bytes': ' '.join(f'{b:02X}' for b in insn.bytes),
                    'size': insn.size
                }
                
                # Add additional details if available
                if hasattr(insn, 'operands'):
                    inst_info['operands'] = []
                    for op in insn.operands:
                        op_info = {'type': op.type}
                        if op.type == capstone.CS_OP_REG:
                            op_info['reg'] = insn.reg_name(op.reg)
                        elif op.type == capstone.CS_OP_IMM:
                            op_info['imm'] = op.imm
                        elif op.type == capstone.CS_OP_MEM:
                            op_info['mem'] = {
                                'base': insn.reg_name(op.mem.base) if op.mem.base != 0 else None,
                                'index': insn.reg_name(op.mem.index) if op.mem.index != 0 else None,
                                'disp': op.mem.disp
                            }
                        inst_info['operands'].append(op_info)
                
                instructions.append(inst_info)
            
            return instructions
            
        except Exception as e:
            logger.error(f"Error disassembling code: {e}")
            return [{"error": f"Disassembly failed: {e}"}]
    
    def detect_data_types(self, data: bytes, base_address: int) -> List[Dict[str, Any]]:
        """Detect various data types in a memory region
        
        Args:
            data: Raw memory data
            base_address: Base address of the data
            
        Returns:
            List of detected data type information
        """
        detections = []
        
        try:
            # Look for strings
            strings = self._find_strings(data, base_address)
            detections.extend(strings)
            
            # Look for pointers
            pointers = self._find_pointers(data, base_address)
            detections.extend(pointers)
            
            # Look for function signatures
            functions = self._find_function_signatures(data, base_address)
            detections.extend(functions)
            
            return sorted(detections, key=lambda x: x['address'])
            
        except Exception as e:
            logger.error(f"Error detecting data types: {e}")
            return []
    
    def _find_strings(self, data: bytes, base_address: int) -> List[Dict[str, Any]]:
        """Find string data in memory"""
        strings = []
        
        for encoding in ['ascii', 'utf-16le']:
            if encoding == 'ascii':
                pattern = rb'[ -~]{4,}'  # Printable ASCII, minimum 4 chars
            else:
                pattern = rb'(?:[ -~]\x00){4,}'  # UTF-16 LE pattern
            
            for match in re.finditer(pattern, data):
                try:
                    if encoding == 'ascii':
                        text = match.group().decode('ascii')
                    else:
                        text = match.group().decode('utf-16le')
                    
                    strings.append({
                        'address': base_address + match.start(),
                        'type': 'string',
                        'encoding': encoding,
                        'value': text,
                        'length': len(match.group())
                    })
                except UnicodeDecodeError:
                    continue
        
        return strings
    
    def _find_pointers(self, data: bytes, base_address: int) -> List[Dict[str, Any]]:
        """Find potential pointers in memory"""
        pointers = []
        
        # Check 4-byte aligned positions for 32-bit pointers
        for i in range(0, len(data) - 3, 4):
            try:
                value = struct.unpack('<I', data[i:i+4])[0]
                if 0x00400000 <= value <= 0x7FFFFFFF:  # Typical user space range
                    pointers.append({
                        'address': base_address + i,
                        'type': 'pointer32',
                        'value': f'0x{value:08X}',
                        'target': value
                    })
            except struct.error:
                continue
        
        # Check 8-byte aligned positions for 64-bit pointers
        for i in range(0, len(data) - 7, 8):
            try:
                value = struct.unpack('<Q', data[i:i+8])[0]
                if 0x000000010000 <= value <= 0x00007FFFFFFFFFFF:  # User space range
                    pointers.append({
                        'address': base_address + i,
                        'type': 'pointer64',
                        'value': f'0x{value:016X}',
                        'target': value
                    })
            except struct.error:
                continue
        
        return pointers
    
    def _find_function_signatures(self, data: bytes, base_address: int) -> List[Dict[str, Any]]:
        """Find potential function entry points"""
        functions = []
        
        # Common function prologue patterns
        prologues = [
            b'\x55\x8B\xEC',        # push ebp; mov ebp, esp
            b'\x48\x89\x5C\x24',    # mov [rsp+xx], rbx (x64)
            b'\x40\x53',            # push rbx (x64)
            b'\x48\x83\xEC',       # sub rsp, xx (x64)
        ]
        
        for prologue in prologues:
            offset = 0
            while True:
                pos = data.find(prologue, offset)
                if pos == -1:
                    break
                
                functions.append({
                    'address': base_address + pos,
                    'type': 'function_prologue',
                    'pattern': ' '.join(f'{b:02X}' for b in prologue),
                    'confidence': 0.7
                })
                
                offset = pos + 1
        
        return functions
