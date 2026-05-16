# SSH

## Production VM

- Host/IP: `145.241.234.63`
- User: `ubuntu`
- SSH key file: `C:\Users\james\.ssh\spectrum_oci_ed25519`
- SSH alias: none configured currently

## SSH Command

```powershell
ssh -i $HOME\.ssh\spectrum_oci_ed25519 ubuntu@145.241.234.63
```

## Suggested SSH Config

Suggested entry for `C:\Users\james\.ssh\config`:

```sshconfig
Host bytespectrum
    HostName 145.241.234.63
    User ubuntu
    IdentityFile C:\Users\james\.ssh\spectrum_oci_ed25519
```

## Handling Rules

- Treat the SSH key path as a secret reference.
- Do not print, pack, commit, or expose private key contents.
- Ask before running production SSH commands that modify files, nginx, services,
  DNS, or deployment state.
