"""
Cheat Engine Table Parser
Handles reading and parsing .CT (Cheat Table) files
"""

import struct
import logging
from typing import Dict, List, Optional, Any, BinaryIO
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

@dataclass
class CheatEntry:
    """Represents a single cheat entry"""
    id: str
    description: str
    address: Optional[int] = None
    offsets: List[int] = None
    variable_type: str = "4 Bytes"
    value: Any = None
    enabled: bool = False
    hotkey: Optional[str] = None
    script: Optional[str] = None
    group_header: bool = False
    
    def __post_init__(self):
        if self.offsets is None:
            self.offsets = []

@dataclass
class AddressList:
    """Collection of cheat entries"""
    entries: List[CheatEntry]
    title: str = "Cheat Table"
    target_process: str = ""
    
    def __post_init__(self):
        if self.entries is None:
            self.entries = []

class CheatTableParser:
    """Parser for Cheat Engine .CT files"""
    
    def __init__(self):
        self.type_map = {
            "Binary": "binary",
            "Byte": "byte", 
            "2 Bytes": "word",
            "4 Bytes": "dword",
            "8 Bytes": "qword",
            "Float": "float",
            "Double": "double",
            "String": "string",
            "Array of byte": "aob",
            "Pointer": "pointer"
        }
    
    def parse_file(self, file_path: str) -> Optional[AddressList]:
        """Parse a .CT file and return the address list
        
        Args:
            file_path: Path to the .CT file
            
        Returns:
            AddressList object or None if parsing failed
        """
        try:
            if not Path(file_path).exists():
                logger.error(f"Cheat table file not found: {file_path}")
                return None
            
            # Try to determine if it's binary or XML format
            with open(file_path, 'rb') as f:
                header = f.read(4)
                f.seek(0)
                
                if header.startswith(b'<?xml') or header.startswith(b'<CheatTable'):
                    # XML format (newer CE versions)
                    return self._parse_xml_format(f)
                else:
                    # Binary format (older CE versions)
                    return self._parse_binary_format(f)
                    
        except Exception as e:
            logger.error(f"Error parsing cheat table {file_path}: {e}")
            return None
    
    def _parse_xml_format(self, file_handle: BinaryIO) -> Optional[AddressList]:
        """Parse XML format .CT file"""
        try:
            # Read the entire file as text for XML parsing
            file_handle.seek(0)
            content = file_handle.read().decode('utf-8', errors='ignore')
            
            # Parse XML
            root = ET.fromstring(content)
            
            # Find CheatTable root element
            if root.tag != 'CheatTable':
                cheat_table = root.find('.//CheatTable')
                if cheat_table is None:
                    logger.error("No CheatTable element found")
                    return None
                root = cheat_table
            
            # Parse header information
            title = "Cheat Table"
            target_process = ""
            
            # Look for table info
            for child in root:
                if child.tag == 'CheatTableInfo':
                    title_elem = child.find('Title')
                    if title_elem is not None and title_elem.text:
                        title = title_elem.text
                
                elif child.tag == 'Options':
                    process_elem = child.find('TargetProcess')
                    if process_elem is not None and process_elem.text:
                        target_process = process_elem.text
            
            # Parse address list
            address_list_elem = root.find('.//CheatEntries')
            if address_list_elem is None:
                logger.warning("No CheatEntries found in table")
                return AddressList(entries=[], title=title, target_process=target_process)
            
            entries = self._parse_xml_entries(address_list_elem)
            
            return AddressList(
                entries=entries,
                title=title,
                target_process=target_process
            )
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing XML format: {e}")
            return None
    
    def _parse_xml_entries(self, parent_elem: ET.Element) -> List[CheatEntry]:
        """Parse cheat entries from XML elements"""
        entries = []
        
        for entry_elem in parent_elem.findall('CheatEntry'):
            try:
                entry = self._parse_xml_entry(entry_elem)
                if entry:
                    entries.append(entry)
                    
                    # Recursively parse child entries
                    child_entries_elem = entry_elem.find('CheatEntries')
                    if child_entries_elem is not None:
                        child_entries = self._parse_xml_entries(child_entries_elem)
                        entries.extend(child_entries)
                        
            except Exception as e:
                logger.warning(f"Error parsing cheat entry: {e}")
                continue
        
        return entries
    
    def _parse_xml_entry(self, entry_elem: ET.Element) -> Optional[CheatEntry]:
        """Parse a single cheat entry from XML"""
        try:
            # Get basic attributes
            entry_id = entry_elem.get('ID', '')
            description = self._get_xml_text(entry_elem, 'Description', 'Unknown')
            
            # Check if it's a group header
            group_header = entry_elem.get('GroupHeader', '0') == '1'
            
            # Parse address information
            address = None
            address_text = self._get_xml_text(entry_elem, 'Address')
            if address_text:
                address = self._parse_address(address_text)
            
            # Parse offsets
            offsets = []
            offsets_elem = entry_elem.find('Offsets')
            if offsets_elem is not None:
                for offset_elem in offsets_elem.findall('Offset'):
                    if offset_elem.text:
                        try:
                            offset_val = int(offset_elem.text, 16) if offset_elem.text.startswith('0x') else int(offset_elem.text)
                            offsets.append(offset_val)
                        except ValueError:
                            continue
            
            # Parse variable type
            var_type = self._get_xml_text(entry_elem, 'VariableType', '4 Bytes')
            
            # Parse value
            value = None
            value_elem = entry_elem.find('LastState')
            if value_elem is not None and value_elem.get('Value'):
                value = value_elem.get('Value')
            
            # Parse enabled state
            enabled = entry_elem.get('Enabled', '0') == '1'
            
            # Parse hotkey
            hotkey = None
            hotkey_elem = entry_elem.find('Hotkeys/Hotkey')
            if hotkey_elem is not None:
                hotkey = hotkey_elem.get('Keys', '')
            
            # Parse script
            script = None
            script_elem = entry_elem.find('LuaScript')
            if script_elem is not None and script_elem.text:
                script = script_elem.text.strip()
            
            return CheatEntry(
                id=entry_id,
                description=description,
                address=address,
                offsets=offsets,
                variable_type=var_type,
                value=value,
                enabled=enabled,
                hotkey=hotkey,
                script=script,
                group_header=group_header
            )
            
        except Exception as e:
            logger.warning(f"Error parsing XML entry: {e}")
            return None
    
    def _get_xml_text(self, parent: ET.Element, tag: str, default: str = '') -> str:
        """Get text content from XML element"""
        elem = parent.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return default
    
    def _parse_binary_format(self, file_handle: BinaryIO) -> Optional[AddressList]:
        """Parse binary format .CT file (older Cheat Engine versions)"""
        try:
            # This is a simplified parser for older binary format
            # The exact format varies by CE version and can be complex
            logger.warning("Binary .CT format parsing has limited support")
            
            # Try to read header
            file_handle.seek(0)
            data = file_handle.read()
            
            # Look for text patterns that might indicate addresses/descriptions
            entries = []
            
            # Simple heuristic: look for potential address patterns
            import re
            
            # Look for hex addresses in the binary data
            address_pattern = rb'[0-9A-Fa-f]{8}'
            matches = re.finditer(address_pattern, data)
            
            for i, match in enumerate(matches):
                if i >= 50:  # Limit results
                    break
                
                try:
                    addr_str = match.group().decode('ascii')
                    address = int(addr_str, 16)
                    
                    entry = CheatEntry(
                        id=f"binary_entry_{i}",
                        description=f"Address from binary table",
                        address=address,
                        variable_type="4 Bytes"
                    )
                    entries.append(entry)
                    
                except (ValueError, UnicodeDecodeError):
                    continue
            
            return AddressList(
                entries=entries,
                title="Binary Cheat Table",
                target_process=""
            )
            
        except Exception as e:
            logger.error(f"Error parsing binary format: {e}")
            return None
    
    def _parse_address(self, address_str: str) -> Optional[int]:
        """Parse an address string to integer"""
        try:
            if not address_str:
                return None
            
            address_str = address_str.strip()
            
            # Handle different address formats
            if address_str.startswith('0x'):
                return int(address_str, 16)
            elif address_str.startswith('$'):
                return int(address_str[1:], 16)
            elif all(c in '0123456789ABCDEFabcdef' for c in address_str):
                return int(address_str, 16)
            else:
                # Might be a symbolic address or expression
                return None
                
        except ValueError:
            return None
    
    def export_to_dict(self, address_list: AddressList) -> Dict[str, Any]:
        """Export address list to dictionary format"""
        return {
            'title': address_list.title,
            'target_process': address_list.target_process,
            'entries': [
                {
                    'id': entry.id,
                    'description': entry.description,
                    'address': f"0x{entry.address:08X}" if entry.address else None,
                    'offsets': [f"0x{offset:X}" for offset in entry.offsets],
                    'variable_type': entry.variable_type,
                    'value': entry.value,
                    'enabled': entry.enabled,
                    'hotkey': entry.hotkey,
                    'has_script': entry.script is not None,
                    'group_header': entry.group_header
                }
                for entry in address_list.entries
            ]
        }
    
    def create_mcp_tools_from_table(self, address_list: AddressList) -> List[Dict[str, Any]]:
        """Create MCP tool definitions from cheat table entries
        
        Args:
            address_list: Parsed cheat table
            
        Returns:
            List of MCP tool definitions
        """
        tools = []
        
        for entry in address_list.entries:
            if entry.group_header or not entry.address:
                continue
            
            # Create a read tool for this entry
            tool_name = f"read_{entry.id}" if entry.id else f"read_entry_{len(tools)}"
            tool_name = self._sanitize_tool_name(tool_name)
            
            tool_def = {
                "name": tool_name,
                "description": f"Read {entry.description} ({entry.variable_type})",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                },
                "metadata": {
                    "cheat_entry": {
                        "address": entry.address,
                        "offsets": entry.offsets,
                        "type": entry.variable_type,
                        "description": entry.description
                    }
                }
            }
            
            tools.append(tool_def)
        
        return tools
    
    def _sanitize_tool_name(self, name: str) -> str:
        """Sanitize a tool name for MCP compatibility"""
        import re
        # Replace invalid characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Ensure it starts with a letter or underscore
        if sanitized and sanitized[0].isdigit():
            sanitized = 'entry_' + sanitized
        return sanitized or 'unnamed_entry'
    
    def get_summary(self, address_list: AddressList) -> Dict[str, Any]:
        """Get a summary of the cheat table"""
        entry_types = {}
        enabled_count = 0
        script_count = 0
        group_count = 0
        
        for entry in address_list.entries:
            # Count by type
            var_type = entry.variable_type
            entry_types[var_type] = entry_types.get(var_type, 0) + 1
            
            # Count enabled entries
            if entry.enabled:
                enabled_count += 1
            
            # Count scripts
            if entry.script:
                script_count += 1
            
            # Count groups
            if entry.group_header:
                group_count += 1
        
        return {
            'title': address_list.title,
            'target_process': address_list.target_process,
            'total_entries': len(address_list.entries),
            'enabled_entries': enabled_count,
            'group_headers': group_count,
            'script_entries': script_count,
            'entry_types': entry_types,
            'has_offsets': sum(1 for e in address_list.entries if e.offsets),
            'has_hotkeys': sum(1 for e in address_list.entries if e.hotkey)
        }
