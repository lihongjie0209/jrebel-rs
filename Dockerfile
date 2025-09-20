# Multi-stage build for Rust application
FROM rust:latest AS builder

WORKDIR /app

# Add the target for x86_64-unknown-linux-gnu
RUN rustup target add x86_64-unknown-linux-gnu

# Copy Cargo files for dependency caching
COPY Cargo.toml ./

# Create a dummy main.rs to cache dependencies
RUN mkdir src && echo "fn main() {}" > src/main.rs

# Build dependencies for the target platform
RUN cargo build --release --target x86_64-unknown-linux-gnu && rm src/main.rs

# Copy source code
COPY src ./src

# Build the application with static linking
ENV RUSTFLAGS="-C target-feature=+crt-static"
RUN cargo build --release --target x86_64-unknown-linux-gnu

# Runtime stage
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the binary from builder stage
COPY --from=builder /app/target/x86_64-unknown-linux-gnu/release/jrebel-rs /app/jrebel-rs

# Expose the default port
EXPOSE 12345

# Create a non-root user
RUN useradd -r -s /bin/false jrebel
RUN chown jrebel:jrebel /app/jrebel-rs
USER jrebel

# Run the application
CMD ["./jrebel-rs"]