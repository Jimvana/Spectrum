# Deploy

## Current Known Deployment Shape

- Hosting type: nginx static site on Oracle Cloud VM
- Production server: `ubuntu@145.241.234.63`
- SSH key reference: `C:\Users\james\.ssh\spectrum_oci_ed25519`
- DNS is managed in Cloudflare.
- Local source path: `C:\Users\james\Documents\GitHub\Spectrum\site`
- Deploy path on VM: `/var/www/spectrum`

## Main Production Files

- `/var/www/spectrum/index.html`
- `/var/www/spectrum/styles.css`
- `/var/www/spectrum/benchmarks/index.html`

## Nginx

- Config path: `/etc/nginx/sites-available/spectrum`
- Web root: `/var/www/spectrum`

## HTTPS

- TLS certificate: Let's Encrypt via Certbot
- Renewal: auto-renewal enabled

## Deployment Details Still Needed

- file sync command, for example `rsync`
- verification commands after deploy
- rollback process

## Safety Rules

- Verify the target path before uploading or deleting files.
- Ask before modifying nginx config or restarting/reloading nginx.
- Ask before making Cloudflare DNS or cache changes.
