FROM rust:1-slim-bookworm AS build
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --locked

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends bzip2 ca-certificates curl libdbus-1-3 libxcb1 \
    && rm -rf /var/lib/apt/lists/*
# The Goose CLI the quickstart drives, pinned to the version its README documents.
RUN curl -fsSL https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh \
    | CONFIGURE=false GOOSE_VERSION=v1.54.0 GOOSE_BIN_DIR=/usr/local/bin bash
COPY --from=build /app/target/release/goose-release-manager /app/target/release/crash_test /usr/local/bin/
WORKDIR /app
# Goose keeps its sessions under /root/.local/share/goose. Mount a volume there so
# a restarted container can resume the session an interrupted turn was in.
VOLUME /root/.local/share/goose
EXPOSE 8001
CMD ["goose-release-manager"]
