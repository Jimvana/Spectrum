# Secret References

Store references to secrets, not raw secrets.

Examples:

- SSH key: available through local ssh-agent.
- Password vault: 1Password or Bitwarden item name.
- Env file: path on the server or local machine.

## Cloudflare

- API key file: `C:\Users\james\Documents\codex - api key for cloudflare.txt`
- Handling: read only when a Cloudflare operation explicitly needs it.
- Do not print, pack, commit, or expose the raw key value.
- Ask before making Cloudflare account, DNS, tunnel, cache, or worker changes.
