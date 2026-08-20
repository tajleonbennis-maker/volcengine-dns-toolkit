# Volcengine DNS Toolkit

Python toolkit for managing [Volcengine DNS (火山引擎)](https://www.volcengine.com/product/dns) records via official SDK.

## Features

- ✅ **DNS Record Management**: Create, list, update, delete A/CNAME/TXT records
- ✅ **DDNS Support**: Auto-update home broadband IP to domain records (systemd timer)
- ✅ **Zone Management**: List and query DNS zones
- ✅ **Idempotent Operations**: Safe to run multiple times (upsert pattern)
- ✅ **Configurable Credentials**: Load keys from env vars or config file (never hardcode)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

**Option A: Environment Variables (Recommended)**
```bash
export VOLC_ACCESS_KEY_ID="your-access-key-id"
export VOLC_SECRET_ACCESS_KEY="your-secret-key"
```

**Option B: Config File**
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Test Connection

```bash
python dns_manager.py --test
```

Output:
```
Zone Map: {'cyberstroll.top': 202658, 'cyberstroll.cn': 230113}
  @.cyberstroll.top : [(record_id, 'value')]
  www.cyberstroll.top : [(record_id, 'value')]
```

## Usage Examples

### Add a Subdomain Record

```bash
python dns_manager.py add-record \
    --zone cyberstroll.top \
    --host www.deeptutor \
    --type A \
    --value 165.154.226.119 \
    --ttl 600
```

### List All Records for a Zone

```bash
python dns_manager.py list-records --zone cyberstroll.top
```

### Delete a Record

```bash
python dns_manager.py delete-record \
    --zone cyberstroll.top \
    --host www.deeptutor \
    --record-id 50056244
```

### DDNS Mode (Auto-update IP)

```bash
# Run once
python dns_manager.py ddns

# Or setup systemd timer for auto-update every 5 minutes
sudo cp volc-ddns.timer /etc/systemd/system/
sudo cp volc-ddns.service /etc/systemd/system/
sudo systemctl enable --now volc-ddns.timer
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `VOLC_ACCESS_KEY_ID` | Volcengine Access Key ID | ✅ Yes |
| `VOLC_SECRET_ACCESS_KEY` | Volcengine Secret Access Key | ✅ Yes |
| `VOLC_REGION` | API region (default: `cn-beijing`) | No |
| `CONF_PATH` | Path to config file (default: `.env`) | No |

### Config File Format (.env)

```ini
VOLC_ACCESS_KEY_ID=your-access-key-id-here
VOLC_SECRET_ACCESS_KEY=your-secret-key-here
VOLC_REGION=cn-beijing
```

## Project Structure

```
volcengine-dns-toolkit/
├── dns_manager.py          # Main CLI tool
├── ddns_updater.py         # DDNS auto-updater (for systemd timer)
├── requirements.txt        # Python dependencies
├── .env.example            # Credential template
├── .gitignore              # Exclude sensitive files
├── volc-ddns.service       # Systemd service unit
├── volc-ddns.timer         # Systemd timer unit
└── README.md               # This file
```

## API Reference

### Supported Record Types

- **A**: IPv4 address mapping
- **CNAME**: Canonical name (alias)
- **TXT**: Text records (SPF, DKIM, verification)
- **MX**: Mail exchange
- **NS**: Name server

### SDK Workarounds

The official `volcengine-python-sdk` has some model limitations:

1. **Missing `zid` field in DeleteRecordRequest**: Fixed with custom subclass
2. **Region must be `cn-beijing`**: Not `cn-north-1` as documented
3. **API Host**: `open.volcengineapi.com` (not `dns.volcengineapi.com`)

See `dns_manager.py` for implementation details.

## Security

⚠️ **Never commit real credentials to Git!**

- `.env` is in `.gitignore`
- Use `.env.example` as template
- Prefer environment variables in production
- Rotate keys if accidentally exposed

## Troubleshooting

### InvalidSignature: Signature mismatch

**Cause**: Wrong region or secret key format

**Fix**:
1. Use region `cn-beijing` (not `cn-north-1`)
2. Ensure secret key is not Base64-decoded unless required

### ErrParsingParams: Missing zid

**Cause**: SDK model missing `zid` field

**Fix**: Code uses custom `DelReq` subclass (already implemented)

### Connection Timeout

**Cause**: Network or firewall blocking API

**Fix**: Test from different server:
```bash
curl -s https://open.volcengineapi.com/ -d "Action=ListZones" -d "Version=2018-08-01"
```

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

**Author**: tajleonbennis-maker
**GitHub**: https://github.com/tajleonbennis-maker/volcengine-dns-toolkit
