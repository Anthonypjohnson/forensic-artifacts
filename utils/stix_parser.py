"""
STIX 1.x XML and STIX 2.x JSON parser.

Returns a list of IOC dicts compatible with ioc_model.create().
Extra key '_tags' carries tag names (list[str]).
"""

import json
import re
import xml.etree.ElementTree as ET

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB

# Maps MITRE ATT&CK kill-chain phase names → display tactic strings
_MITRE_PHASE_MAP = {
    'reconnaissance': 'Reconnaissance',
    'resource-development': 'Resource Development',
    'initial-access': 'Initial Access',
    'execution': 'Execution',
    'persistence': 'Persistence',
    'privilege-escalation': 'Privilege Escalation',
    'defense-evasion': 'Defense Evasion',
    'credential-access': 'Credential Access',
    'discovery': 'Discovery',
    'lateral-movement': 'Lateral Movement',
    'collection': 'Collection',
    'command-and-control': 'Command and Control',
    'exfiltration': 'Exfiltration',
    'impact': 'Impact',
}

_VALID_MITRE = set(_MITRE_PHASE_MAP.values())


# ── Public API ────────────────────────────────────────────────────────────────

def parse_stix(content: bytes, filename: str) -> list:
    """
    Auto-detect STIX format and parse.

    Returns list of IOC dicts.  Raises ValueError on parse failure.
    """
    stripped = content.lstrip()
    if stripped and stripped[0:1] in (b'{', b'['):
        return _parse_stix2_json(content)
    return _parse_stix1_xml(content)


# ── STIX 2.x JSON ─────────────────────────────────────────────────────────────

def _parse_stix2_json(content: bytes) -> list:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    objects = []
    if isinstance(data, dict):
        obj_type = data.get('type', '')
        if obj_type == 'bundle':
            objects = data.get('objects', [])
        elif obj_type == 'indicator':
            objects = [data]
        else:
            # Try objects key anyway
            objects = data.get('objects', [data])
    elif isinstance(data, list):
        objects = data
    else:
        raise ValueError("Unexpected JSON structure — not a bundle or list.")

    results = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        if obj.get('type') == 'indicator':
            ioc = _parse_stix2_indicator(obj)
            if _has_any_indicator(ioc):
                results.append(ioc)
    return results


def _parse_stix2_indicator(obj: dict) -> dict:
    ioc = {
        'category': '',
        'severity': 'Medium',
        'hostname': '',
        'ip_address': '',
        'domain': '',
        'url': '',
        'hash_value': '',
        'hash_type': '',
        'filename': '',
        'file_path': '',
        'registry_key': '',
        'command_line': '',
        'email': '',
        'user_account': '',
        'notes': '',
        'user_agent': '',
        'mitre_category': '',
        'detection_rule': '',
        'network_port': '',
        'network_protocol': '',
        '_tags': [],
    }

    ioc['category'] = (obj.get('name') or '')[:256]
    ioc['notes'] = (obj.get('description') or '')[:4096]

    # Labels → tags
    for label in obj.get('labels', []):
        if isinstance(label, str) and label.strip():
            ioc['_tags'].append(label.strip()[:64])

    # Confidence → severity
    conf = obj.get('confidence')
    if conf is not None:
        try:
            ioc['severity'] = _confidence_to_severity(int(conf))
        except (TypeError, ValueError):
            pass

    # Kill-chain phases → MITRE tactic
    for phase in obj.get('kill_chain_phases', []):
        if not isinstance(phase, dict):
            continue
        kc_name = (phase.get('kill_chain_name') or '').lower()
        if 'mitre' not in kc_name and 'attack' not in kc_name:
            continue
        phase_name = (phase.get('phase_name') or '').lower().strip()
        tactic = _MITRE_PHASE_MAP.get(phase_name)
        if tactic:
            ioc['mitre_category'] = tactic
            break

    # Pattern extraction
    pattern = obj.get('pattern') or ''
    if pattern:
        _extract_stix2_pattern(pattern, ioc)

    return ioc


def _extract_stix2_pattern(pattern: str, ioc: dict) -> None:
    """Regex-based extraction of IOC fields from a STIX 2.x pattern string."""

    def _val(m):
        """Strip surrounding quotes from a regex match group 1."""
        return (m.group(1) or '').strip("'\"")

    # IP addresses
    m = re.search(r"ipv[46]-addr:value\s*=\s*'([^']+)'", pattern)
    if m and not ioc['ip_address']:
        ioc['ip_address'] = _val(m)[:45]

    # Domain
    m = re.search(r"domain-name:value\s*=\s*'([^']+)'", pattern)
    if m and not ioc['domain']:
        ioc['domain'] = _val(m)[:512]

    # URL
    m = re.search(r"url:value\s*=\s*'([^']+)'", pattern)
    if m and not ioc['url']:
        ioc['url'] = _val(m)[:2048]

    # Email
    m = re.search(r"email-addr:value\s*=\s*'([^']+)'", pattern)
    if m and not ioc['email']:
        ioc['email'] = _val(m)[:512]

    # Filename
    m = re.search(r"file:name\s*=\s*'([^']+)'", pattern)
    if m and not ioc['filename']:
        ioc['filename'] = _val(m)[:512]

    # File hashes (ordered by specificity)
    for hash_name in ('SHA-512', 'SHA-256', 'SHA-1', 'SSDEEP', 'MD5'):
        m = re.search(
            r"file:hashes\." + re.escape(hash_name) + r"\s*=\s*'([^']+)'",
            pattern, re.IGNORECASE)
        if m:
            ioc['hash_value'] = _val(m)[:256]
            ioc['hash_type'] = hash_name.replace('-', '')[:6]
            break

    # File path / directory
    m = re.search(r"(?:directory:path|file:parent_directory_ref\.path)\s*=\s*'([^']+)'", pattern)
    if m and not ioc['file_path']:
        ioc['file_path'] = _val(m)[:1024]

    # Command line
    m = re.search(r"process:command_line\s*=\s*'([^']+)'", pattern)
    if m and not ioc['command_line']:
        ioc['command_line'] = _val(m)[:2048]

    # Registry key
    m = re.search(r"windows-registry-key:key\s*=\s*'([^']+)'", pattern)
    if m and not ioc['registry_key']:
        ioc['registry_key'] = _val(m)[:1024]

    # User account
    m = re.search(r"user-account:user_id\s*=\s*'([^']+)'", pattern)
    if m and not ioc['user_account']:
        ioc['user_account'] = _val(m)[:256]

    # Hostname
    m = re.search(r"hostname:value\s*=\s*'([^']+)'", pattern)
    if m and not ioc['hostname']:
        ioc['hostname'] = _val(m)[:512]

    # Network port
    m = re.search(r"network-traffic:dst_port\s*=\s*(\d+)", pattern)
    if m and not ioc['network_port']:
        ioc['network_port'] = m.group(1)[:64]

    # Network protocol
    m = re.search(r"network-traffic:protocols\[\d+\]\s*=\s*'([^']+)'", pattern)
    if m and not ioc['network_protocol']:
        proto = _val(m).upper()
        _VALID_PROTOS = {
            'TCP', 'UDP', 'ICMP', 'HTTP', 'HTTPS', 'DNS',
            'SMTP', 'FTP', 'SSH', 'SMB', 'RDP', 'TLS',
        }
        if proto in _VALID_PROTOS:
            ioc['network_protocol'] = proto

    # User-Agent (HTTP request extension)
    m = re.search(r"'User-Agent'\s*=\s*'([^']+)'", pattern)
    if m and not ioc['user_agent']:
        ioc['user_agent'] = _val(m)[:1024]


# ── STIX 1.x XML ──────────────────────────────────────────────────────────────

def _parse_stix1_xml(content: bytes) -> list:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML: {exc}") from exc

    results = []
    # Collect all elements whose local name is 'Indicator', namespace-agnostic
    for el in root.iter():
        local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        if local == 'Indicator':
            ioc = _parse_stix1_indicator(el)
            if _has_any_indicator(ioc):
                results.append(ioc)
    return results


def _parse_stix1_indicator(el) -> dict:
    ioc = {
        'category': '',
        'severity': 'Medium',
        'hostname': '',
        'ip_address': '',
        'domain': '',
        'url': '',
        'hash_value': '',
        'hash_type': '',
        'filename': '',
        'file_path': '',
        'registry_key': '',
        'command_line': '',
        'email': '',
        'user_account': '',
        'notes': '',
        'user_agent': '',
        'mitre_category': '',
        'detection_rule': '',
        'network_port': '',
        'network_protocol': '',
        '_tags': [],
    }

    # Title → category
    for child in el.iter():
        local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local == 'Title' and child.text:
            ioc['category'] = child.text.strip()[:256]
            break

    # Description → notes
    for child in el.iter():
        local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local == 'Description' and child.text:
            ioc['notes'] = child.text.strip()[:4096]
            break

    # Kill-chain phases
    for child in el.iter():
        local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local == 'Kill_Chain_Phase':
            phase_name = (child.get('phase_name') or '').lower().strip()
            tactic = _MITRE_PHASE_MAP.get(phase_name)
            if tactic:
                ioc['mitre_category'] = tactic
                break

    # CybOX Observable → dispatch on xsi:type
    for child in el.iter():
        # Look for Properties elements (CybOX object properties)
        local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local != 'Properties':
            continue

        xsi_type = ''
        for attr_name, attr_val in child.attrib.items():
            if attr_name.endswith('}type') or attr_name == 'xsi:type':
                xsi_type = attr_val
                break

        type_suffix = xsi_type.split(':')[-1] if ':' in xsi_type else xsi_type

        if type_suffix == 'AddressObjectType':
            _stix1_extract_address(child, ioc)
        elif type_suffix == 'DomainNameObjectType':
            _stix1_extract_text(child, 'Value', ioc, 'domain', 512)
        elif type_suffix == 'URIObjectType':
            _stix1_extract_text(child, 'Value', ioc, 'url', 2048)
        elif type_suffix == 'EmailMessageObjectType':
            _stix1_extract_email(child, ioc)
        elif type_suffix == 'FileObjectType':
            _stix1_extract_file(child, ioc)
        elif type_suffix == 'ProcessObjectType':
            _stix1_extract_text(child, 'Argument_List', ioc, 'command_line', 2048)
            if not ioc['command_line']:
                _stix1_extract_text(child, 'Name', ioc, 'command_line', 2048)
        elif type_suffix == 'WindowsRegistryKeyObjectType':
            _stix1_extract_text(child, 'Key', ioc, 'registry_key', 1024)
        elif type_suffix == 'UserAccountObjectType':
            _stix1_extract_text(child, 'Username', ioc, 'user_account', 256)
        elif type_suffix == 'HostnameObjectType':
            _stix1_extract_text(child, 'Hostname_Value', ioc, 'hostname', 512)

    return ioc


def _stix1_text(el, local_name: str) -> str:
    """Find first child element with given local name and return its text."""
    for child in el.iter():
        local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local == local_name and child.text:
            return child.text.strip()
    return ''


def _stix1_extract_text(el, local_name: str, ioc: dict, field: str, maxlen: int) -> None:
    val = _stix1_text(el, local_name)
    if val and not ioc[field]:
        ioc[field] = val[:maxlen]


def _stix1_extract_address(el, ioc: dict) -> None:
    # category attr: ipv4-addr, ipv6-addr, e-mail, etc.
    cat = el.get('category', '').lower()
    val = _stix1_text(el, 'Address_Value')
    if not val:
        return
    if 'mail' in cat:
        if not ioc['email']:
            ioc['email'] = val[:512]
    else:
        if not ioc['ip_address']:
            ioc['ip_address'] = val[:45]


def _stix1_extract_email(el, ioc: dict) -> None:
    # Try From/To header first
    for tag in ('From', 'To', 'Sender'):
        val = _stix1_text(el, tag)
        if val and not ioc['email']:
            ioc['email'] = val[:512]
            return
    # Fallback: Address_Value inside headers
    val = _stix1_text(el, 'Address_Value')
    if val and not ioc['email']:
        ioc['email'] = val[:512]


def _stix1_extract_file(el, ioc: dict) -> None:
    _stix1_extract_text(el, 'File_Name', ioc, 'filename', 512)
    _stix1_extract_text(el, 'File_Path', ioc, 'file_path', 1024)
    # Hashes
    _HASH_ORDER = [
        ('SHA512', 'SHA512'), ('SHA256', 'SHA256'),
        ('SHA1', 'SHA1'), ('MD5', 'MD5'), ('SSDEEP', 'SSDEEP'),
    ]
    for hash_type_key, hash_type_val in _HASH_ORDER:
        for child in el.iter():
            local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if local == 'Hash':
                type_el_text = _stix1_text(child, 'Type')
                if type_el_text.upper().replace('-', '') == hash_type_key:
                    val = _stix1_text(child, 'Simple_Hash_Value')
                    if val and not ioc['hash_value']:
                        ioc['hash_value'] = val[:256]
                        ioc['hash_type'] = hash_type_val
                        return


# ── Helpers ───────────────────────────────────────────────────────────────────

def _has_any_indicator(ioc: dict) -> bool:
    """Return True if the IOC has at least one substantive field populated."""
    _INDICATOR_FIELDS = [
        'hostname', 'ip_address', 'domain', 'url', 'hash_value',
        'filename', 'file_path', 'registry_key', 'command_line',
        'email', 'user_account', 'user_agent', 'network_port',
    ]
    return any(ioc.get(f, '').strip() for f in _INDICATOR_FIELDS)


def _confidence_to_severity(conf: int) -> str:
    """Map STIX 2.x confidence (0–100) to severity string."""
    if conf >= 85:
        return 'Critical'
    if conf >= 60:
        return 'High'
    if conf >= 30:
        return 'Medium'
    return 'Low'
