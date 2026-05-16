# Server

## Production

- Hosting provider: Oracle Cloud
- Server type: VM
- Public IP: `145.241.234.63`
- Web server: nginx
- Site type: static site
- Web root: `/var/www/spectrum`
- Main nginx config: `/etc/nginx/sites-available/spectrum`

## Domains

- https://bytespectrum.cc
- https://www.bytespectrum.cc

## DNS

- Provider: Cloudflare
- `bytespectrum.cc` A record -> `145.241.234.63`
- `www.bytespectrum.cc` CNAME -> `bytespectrum.cc`

## Unknowns To Confirm

- reload command
- log paths
- deploy command or file sync process

## HTTPS

- Let's Encrypt certificate managed by Certbot
- Certbot auto-renewal is enabled
