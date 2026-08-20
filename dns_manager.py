#!/usr/bin/env python3
"""
Volcengine DNS Toolkit - DNS Record Manager

Manage Volcengine (火山引擎) DNS records via official SDK.
Supports: create, list, update, delete records + DDNS auto-update.

Credentials loaded from:
  1. Environment variables: VOLC_ACCESS_KEY_ID, VOLC_SECRET_ACCESS_KEY
  2. Config file (.env or path in CONF_PATH env var)

Usage:
  python dns_manager.py --test              # Test API connection & list zones
  python dns_manager.py list-records --zone example.com
  python dns_manager.py add-record --zone example.com --host www --type A --value 1.2.3.4
  python dns_manager.py delete-record --zone example.com --record-id 12345
  python dns_manager.py ddns                # DDNS mode: update domains to current IP

Security: Never hardcode credentials. Use .env file or environment variables.
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List, Dict

# SDK Imports
try:
    from volcenginesdkcore.auth import StaticCredentialProvider
    from volcenginesdkcore.configuration import Configuration
    from volcenginesdkcore.api_client import ApiClient
    from volcenginesdkdns import DNSApi
    from volcenginesdkdns.models import (
        ListZonesRequest,
        ListRecordsRequest,
        CreateRecordRequest,
        DeleteRecordRequest,
    )
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Install with: pip install -r requirements.txt")
    sys.exit(1)

# ============================================================================
# Configuration
# ============================================================================

DEFAULT_REGION = "cn-beijing"
DEFAULT_API_HOST = "open.volcengineapi.com"
DEFAULT_CONF_PATH = ".env"
DEFAULT_TTL = 600
DEFAULT_LINE = "default"


def load_credentials() -> Tuple[str, str]:
    """
    Load Volcengine credentials from environment variables or config file.

    Priority:
      1. Environment variables (VOLC_ACCESS_KEY_ID, VOLC_SECRET_ACCESS_KEY)
      2. Config file (.env or CONF_PATH env var)

    Returns:
        Tuple of (access_key_id, secret_access_key)

    Raises:
        SystemExit: If credentials not found
    """
    # Try environment variables first
    ak = os.environ.get("VOLC_ACCESS_KEY_ID", "").strip()
    sk = os.environ.get("VOLC_SECRET_ACCESS_KEY", "").strip()

    if ak and sk:
        return ak, sk

    # Try config file
    conf_path = os.environ.get("CONF_PATH", DEFAULT_CONF_PATH)

    if os.path.exists(conf_path):
        try:
            with open(conf_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("VOLC_ACCESS_KEY_ID=") and not ak:
                        ak = line.split("=", 1)[1].strip()
                    elif line.startswith("VOLC_SECRET_ACCESS_KEY=") and not sk:
                        sk = line.split("=", 1)[1].strip()
        except Exception as e:
            print(f"⚠️  Failed to read {conf_path}: {e}", file=sys.stderr)

    if not ak or not sk:
        print(
            "❌ Missing credentials. Set environment variables or create .env file:\n"
            f"   VOLC_ACCESS_KEY_ID=your-key\n"
            f"   VOLC_SECRET_ACCESS_KEY=your-secret\n"
            f"\n"
            f"Or copy .env.example to .env and fill in your keys.",
            file=sys.stderr,
        )
        sys.exit(1)

    return ak, sk


def get_region() -> str:
    """Get API region from env or default."""
    return os.environ.get("VOLC_REGION", DEFAULT_REGION)


# ============================================================================
# Custom Request Classes (SDK Workarounds)
# ============================================================================

class DeleteRecordRequestWithZid(DeleteRecordRequest):
    """
    Workaround: Official SDK's DeleteRecordRequest lacks `zid` field.
    This subclass adds zid so to_dict() includes ZID in the API request.
    """

    def __init__(self, zid: int, record_id: int, **kwargs):
        super().__init__(record_id=str(record_id), **kwargs)
        self.zid = str(zid)

    @property
    def swagger_types(self):
        types = dict(getattr(super(), 'swagger_types', {}))
        types['zid'] = str
        return types

    @property
    def attribute_map(self):
        attr_map = dict(getattr(super(), 'attribute_map', {}))
        attr_map['zid'] = 'ZID'
        return attr_map


# ============================================================================
# API Client
# ============================================================================

class VolcengineDNSClient:
    """High-level client for Volcengine DNS API."""

    def __init__(self, region: Optional[str] = None):
        ak, sk = load_credentials()
        self.region = region or get_region()

        provider = StaticCredentialProvider(
            access_key_id=ak,
            secret_access_key=sk
        )

        conf = Configuration()
        conf.credential_provider = provider
        conf.region = self.region
        conf.host = DEFAULT_API_HOST

        self.api = DNSApi(ApiClient(conf))
        print(f"✅ Connected to Volcengine DNS (region: {self.region})")

    def list_zones(self, page_size: int = 100) -> Dict[str, int]:
        """
        List all DNS zones.

        Returns:
            Dict mapping zone_name -> zone_id
        """
        req = ListZonesRequest(page_size=page_size, page_number=1)
        resp = self.api.list_zones(req)

        zones = {}
        for z in (resp.zones or []):
            name = getattr(z, 'zone_name', None)
            zid = getattr(z, 'zid', None)
            if name and zid:
                zones[name] = int(zid)

        return zones

    def list_records(
        self,
        zone_id: int,
        host: Optional[str] = None,
        record_type: Optional[str] = None,
        page_size: int = 100
    ) -> List[Dict]:
        """
        List DNS records for a zone.

        Args:
            zone_id: Zone ID
            host: Filter by host (e.g., 'www', '@')
            record_type: Filter by type ('A', 'CNAME', 'TXT', etc.)
            page_size: Records per page

        Returns:
            List of dicts with record info
        """
        kwargs = {
            'zid': zone_id,
            'page_size': page_size,
            'page_number': 1
        }
        if host:
            kwargs['host'] = host
        if record_type:
            kwargs['type'] = record_type

        req = ListRecordsRequest(**kwargs)
        resp = self.api.list_records(req)

        records = []
        for r in (resp.records or []):
            records.append({
                'record_id': int(getattr(r, 'record_id', 0)),
                'host': getattr(r, 'host', ''),
                'type': getattr(r, 'type', ''),
                'value': getattr(r, 'value', ''),
                'ttl': getattr(r, 'ttl', 0),
                'line': getattr(r, 'line', ''),
                'enabled': getattr(r, 'enable', True),
            })

        return records

    def create_record(
        self,
        zone_id: int,
        host: str,
        record_type: str,
        value: str,
        ttl: int = DEFAULT_TTL,
        line: str = DEFAULT_LINE
    ) -> Dict:
        """
        Create a new DNS record.

        Args:
            zone_id: Zone ID
            host: Hostname (e.g., 'www', '@', 'api')
            record_type: Record type ('A', 'CNAME', 'TXT', etc.)
            value: Record value (IP address, domain, text, etc.)
            TTL: Time-to-live in seconds
            line: Line/ISP (default: 'default')

        Returns:
            Dict with created record info
        """
        req = CreateRecordRequest(
            zid=zone_id,
            host=host,
            type=record_type,
            value=value,
            ttl=ttl,
            line=line
        )

        resp = self.api.create_record(req)

        return {
            'record_id': int(getattr(resp, 'record_id', 0)),
            'fqdn': getattr(resp, 'fqdn', ''),
            'host': getattr(resp, 'host', ''),
            'type': getattr(resp, 'type', ''),
            'value': getattr(resp, 'value', ''),
            'ttl': getattr(resp, 'ttl', 0),
            'created_at': getattr(resp, 'created_at', ''),
        }

    def delete_record(self, zone_id: int, record_id: int) -> bool:
        """
        Delete a DNS record.

        Args:
            zone_id: Zone ID
            record_id: Record ID to delete

        Returns:
            True if deleted successfully
        """
        req = DeleteRecordRequestWithZid(zid=zone_id, record_id=record_id)
        self.api.delete_record(req)
        return True

    def upsert_a_record(
        self,
        zone_id: int,
        host: str,
        value: int,
        ttl: int = DEFAULT_TTL
    ) -> str:
        """
        Create or update an A record (idempotent).

        If a record with correct value exists → unchanged
        If stale records exist → delete them, create new one
        If no record exists → create new one

        Args:
            zone_id: Zone ID
            host: Hostname
            value: IP address
            ttl: TTL in seconds

        Returns:
            Status string: 'unchanged', 'updated', or 'created'
        """
        recs = self.list_records(zone_id, host, record_type='A')

        have_correct = [r for r in recs if r['value'] == value]
        stale = [r for r in recs if r['value'] != value]

        if have_correct and not stale:
            return 'unchanged'

        # Remove stale records
        for r in stale:
            try:
                self.delete_record(zone_id, r['record_id'])
                print(f"  🗑️  Deleted stale record {r['record_id']} ({r['value']})")
            except Exception as e:
                raise RuntimeError(f"Failed to delete {r['record_id']}: {e}")

        # Create new record if needed
        if not have_correct:
            result = self.create_record(zone_id, host, 'A', value, ttl)
            print(f"  ✅ Created {host}.{result.get('fqdn', '')} -> {value}")
            return 'created'

        return 'updated'


# ============================================================================
# Helper Functions
# ============================================================================

def get_public_ipv4() -> str:
    """Get current public IPv4 address."""
    urls = [
        "https://ip.sb",
        "https://api.ipify.org",
        "https://ifconfig.me",
        "https://icanhazip.com",
    ]

    for url in urls:
        try:
            out = subprocess.run(
                ["curl", "-4", "-s", "--max-time", "8", url],
                capture_output=True,
                text=True
            )
            ip = out.stdout.strip()
            if ip and ip.replace(".", "").isdigit():
                return ip
        except Exception:
            continue

    raise SystemExit("❌ Cannot determine public IPv4 address")


def find_zone_id(client: VolcengineDNSClient, domain: str) -> Optional[int]:
    """Find zone ID by domain name."""
    zones = client.list_zones()
    return zones.get(domain)


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_test(args):
    """Test API connection and list zones."""
    client = VolcengineDNSClient()

    print("\n📋 Zone List:")
    zones = client.list_zones()
    for name, zid in sorted(zones.items()):
        print(f"  {name}: {zid}")

    if args.zone:
        print(f"\n📝 Records for {args.zone}:")
        zid = zones.get(args.zone)
        if zid:
            records = client.list_records(zid)
            for r in records:
                status = "✅" if r.get('enabled') else "❌"
                print(f"  {status} {r['host']}.{args.zone} -> {r['value']} [{r['type']} TTL:{r['ttl']}]")
        else:
            print(f"  ❌ Zone '{args.zone}' not found")


def cmd_list_records(args):
    """List records for a zone."""
    client = VolcengineDNSClient()

    zid = find_zone_id(client, args.zone)
    if not zid:
        print(f"❌ Zone '{args.zone}' not found")
        sys.exit(1)

    print(f"\n📝 DNS Records for {args.zone} (Zone ID: {zid}):")
    print("-" * 80)

    records = client.list_records(zid, host=args.host, record_type=args.type)

    if not records:
        print("  No records found")
        return

    for r in records:
        status = "✅" if r.get('enabled') else "❌"
        print(
            f"  {status} {r['host']:20s} -> {r['value']:30s} "
            f"[{r['type']:^5s} TTL:{r['ttl']:>5d} ID:{r['record_id']}]"
        )

    print("-" * 80)
    print(f"  Total: {len(records)} records")


def cmd_add_record(args):
    """Create a new DNS record."""
    client = VolcengineDNSClient()

    zid = find_zone_id(client, args.zone)
    if not zid:
        print(f"❌ Zone '{args.zone}' not found")
        sys.exit(1)

    print(f"\n➕ Creating {args.host}.{args.zone} [{args.type}] -> {args.value}...")

    try:
        result = client.create_record(
            zone_id=zid,
            host=args.host,
            record_type=args.type.upper(),
            value=args.value,
            ttl=args.ttl
        )

        fqdn = result.get('fqdn', '')
        rid = result.get('record_id', '')

        print(f"  ✅ Success!")
        print(f"     FQDN: {fqdn}")
        print(f"     Record ID: {rid}")
        print(f"     Value: {result.get('value')}")
        print(f"     TTL: {result.get('ttl')}s")
        print(f"     Created: {result.get('created_at')}")

    except Exception as e:
        print(f"  ❌ Failed: {e}")
        sys.exit(1)


def cmd_delete_record(args):
    """Delete a DNS record."""
    client = VolcengineDNSClient()

    zid = find_zone_id(client, args.zone)
    if not zid:
        print(f"❌ Zone '{args.zone}' not found")
        sys.exit(1)

    print(f"\n🗑️  Deleting record {args.record_id} from {args.zone}...")

    try:
        client.delete_record(zid, args.record_id)
        print(f"  ✅ Record {args.record_id} deleted successfully")

    except Exception as e:
        print(f"  ❌ Failed: {e}")
        sys.exit(1)


def cmd_ddns(args):
    """DDNS mode: Update A records to current public IP."""
    client = VolcengineDNSClient()

    ip = get_public_ipv4()
    print(f"\n🌐 Current Public IP: {ip}")

    zones = client.list_zones()

    domains = [args.zone] if args.zone else []

    if not domains:
        # Use default domains from env or common ones
        domains_str = os.environ.get("DDNS_DOMAINS", "")
        if domains_str:
            domains = [d.strip() for d in domains_str.split(",") if d.strip()]

    if not domains:
        print("⚠️  No domains specified. Use --zone or set DDNS_DOMAINS env var")
        print("\nExample:")
        print("  DDNS_DOMAINS=example.com,www.example.com python dns_manager.py ddns")
        return

    hosts = ["@", "www"] if not args.host else [args.host]

    for domain in domains:
        zid = zones.get(domain)
        if not zid:
            print(f"  ⚠️  {domain}: Zone not found, skipping")
            continue

        for host in hosts:
            try:
                status = client.upsert_a_record(zid, host, ip)
                icon = {"created": "✅", "updated": "🔄", "unchanged": "✅"}.get(status, "ℹ️")
                print(f"  {icon} {host}.{domain} -> {ip} ({status})")
            except Exception as e:
                print(f"  ❌ {host}.{domain} failed: {e}")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Volcengine DNS Toolkit - Manage DNS records via API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --test                          Test connection & list zones
  %(prog)s list-records --zone example.com  List all records
  %(prog)s add-record --zone example.com \\
      --host api --type A --value 1.2.3.4   Add A record
  %(prog)s ddns --zone example.com          DDNS: update to current IP
        """
    )

    parser.add_argument("--test", action="store_true", help="Test API connection")
    parser.add_argument("--zone", "-z", help="Domain/Zone name")
    parser.add_argument("--region", "-r", help="API region (default: cn-beijing)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list-records
    p_list = subparsers.add_parser("list-records", help="List DNS records")
    p_list.add_argument("--zone", "-z", required=True, help="Zone name")
    p_list.add_argument("--host", help="Filter by host")
    p_list.add_argument("--type", "-t", help="Filter by record type (A, CNAME, TXT...)")

    # add-record
    p_add = subparsers.add_parser("add-record", help="Create DNS record")
    p_add.add_argument("--zone", "-z", required=True, help="Zone name")
    p_add.add_argument("--host", required=True, help="Host name (@, www, api...)")
    p_add.add_argument("--type", "-t", required=True, help="Record type (A, CNAME, TXT...)")
    p_add.add_argument("--value", "-v", required=True, help="Record value")
    p_add.add_argument("--ttl", type=int, default=DEFAULT_TTL, help=f"TTL (default: {DEFAULT_TTL})")

    # delete-record
    p_del = subparsers.add_parser("delete-record", help="Delete DNS record")
    p_del.add_argument("--zone", "-z", required=True, help="Zone name")
    p_del.add_argument("--record-id", type=int, required=True, help="Record ID to delete")

    # ddns
    p_ddns = subparsers.add_parser("ddns", help="DDNS mode: update IP")
    p_ddns.add_argument("--zone", "-z", help="Domain(s) to update (comma-separated)")
    p_ddns.add_argument("--host", help="Host(s) to update (default: @,www)")

    args = parser.parse_args()

    # Override region if specified
    if args.region:
        os.environ["VOLC_REGION"] = args.region

    # Execute command
    if args.test or args.command is None:
        cmd_test(args)
    elif args.command == "list-records":
        cmd_list_records(args)
    elif args.command == "add-record":
        cmd_add_record(args)
    elif args.command == "delete-record":
        cmd_delete_record(args)
    elif args.command == "ddns":
        cmd_ddns(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
