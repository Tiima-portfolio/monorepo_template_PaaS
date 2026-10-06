# radiator-web: the page from public/ and the scripts tsc compiled into dist/,
# served by unprivileged nginx (port 8080), pinned by digest. In the
# air-gapped network, use the internal registry's copy.
FROM nginxinc/nginx-unprivileged:1.29-alpine@sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6
COPY public/ /usr/share/nginx/html/
COPY dist/main.js dist/radiator.js /usr/share/nginx/html/
# The base image's nginx user, as a number so Kubernetes can check it isn't root.
USER 101
EXPOSE 8080
