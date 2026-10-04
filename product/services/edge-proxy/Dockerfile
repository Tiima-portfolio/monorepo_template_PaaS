# Pinned by digest; in the air-gapped network use the internal registry's copy.
FROM alpine:3.22@sha256:5291449c3df73caf6ed85e649dec1b9e818b39a5d8c871e97afc13e9cd5e8fa8
RUN adduser -D -u 10001 app
USER app
CMD ["echo", "Hello from edge-proxy"]
