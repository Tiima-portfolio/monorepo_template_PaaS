# The generic lint image: linters copied from their upstream images, each
# pinned by digest, and the rest installed from their package index at a fixed
# version. In the air-gapped network, use the internal registry's copies and
# the package mirrors.
FROM hadolint/hadolint:v2.15.1@sha256:32dac94127fd60b7b7e3fbfc65e1383b9b5e25c9bfd7b8536de7a539fe68a12d AS hadolint
FROM koalaman/shellcheck:v0.11.0@sha256:61862eba1fcf09a484ebcc6feea46f1782532571a34ed51fedf90dd25f925a8d AS shellcheck
FROM rhysd/actionlint:1.7.12@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667 AS actionlint

# Python for yamllint.
FROM python:3.13-alpine3.22@sha256:e81548ac35b07a3bd4805f275107592ef458b1e893c0e04d45aedaa19416cca5
COPY --from=hadolint /bin/hadolint /usr/local/bin/hadolint
COPY --from=shellcheck /bin/shellcheck /usr/local/bin/shellcheck
COPY --from=actionlint /usr/local/bin/actionlint /usr/local/bin/actionlint
# Toolchain images run as the caller's user, with HOME writable by anyone.
RUN pip install --no-cache-dir yamllint==1.38.0 \
 && mkdir -m 1777 /home/ci
ENV HOME=/home/ci
USER 10001
