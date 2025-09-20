mod structs;
mod crypto;
mod utils;
mod handlers;

use axum::{
    routing::{get, post},
    Router,
};
use clap::Parser;
use std::sync::Arc;
use tower::ServiceBuilder;
use tower_http::trace::TraceLayer;
use tracing::{info, debug, error, Level};
use tracing_subscriber;

use structs::Config;
use handlers::*;

#[derive(Parser)]
#[command(name = "jrebel-rs")]
#[command(about = "JRebel License Active Server implemented in Rust")]
struct Args {
    /// Server port, value range 1-65535
    #[arg(short, long, default_value_t = 12345, env = "JREBEL_PORT")]
    port: u16,

    /// Log level (trace, debug, info, warn, error)
    #[arg(short, long, default_value = "info", env = "JREBEL_LOG_LEVEL")]
    log_level: String,

    /// Index page export schema (http or https)
    #[arg(long, default_value = "http", env = "JREBEL_EXPORT_SCHEMA")]
    export_schema: String,

    /// Index page export host, ip or domain
    #[arg(long, default_value = "", env = "JREBEL_EXPORT_HOST")]
    export_host: String,

    /// Use New Index Page
    #[arg(long, default_value_t = true, env = "JREBEL_NEW_INDEX")]
    new_index: bool,

    /// JRebel Work mode. 0: auto, 1: force offline mode, 2: force online mode, 3: oldGuid
    #[arg(long, default_value_t = 0, env = "JREBEL_WORK_MODE")]
    jrebel_work_mode: i32,

    /// Offline days for license
    #[arg(long, default_value_t = 30, env = "JREBEL_OFFLINE_DAYS")]
    offline_days: i32,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    // Initialize tracing
    let level = match args.log_level.to_lowercase().as_str() {
        "trace" => Level::TRACE,
        "debug" => Level::DEBUG,
        "info" => Level::INFO,
        "warn" => Level::WARN,
        "error" => Level::ERROR,
        _ => Level::INFO,
    };

    tracing_subscriber::fmt()
        .with_max_level(level)
        .with_target(true)
        .with_thread_ids(true)
        .with_file(true)
        .with_line_number(true)
        .init();

    info!("Starting JRebel License Active Server (Rust)");
    info!("Log level set to: {}", args.log_level);
    debug!("Configuration: port={}, offline_days={}, export_schema={}, export_host={}, new_index={}, jrebel_work_mode={}", 
           args.port, args.offline_days, args.export_schema, args.export_host, args.new_index, args.jrebel_work_mode);

    let config = Arc::new(Config {
        port: args.port,
        offline_days: args.offline_days,
        log_level: args.log_level,
        export_schema: args.export_schema,
        export_host: args.export_host,
        new_index: args.new_index,
        jrebel_work_mode: args.jrebel_work_mode,
    });

    // Build our application with routes
    let app = Router::new()
        .route("/", get(index_handler))
        .route("/health", get(health_check_handler))
        .route("/health/simple", get(health_simple_handler))
        .route("/jrebel/leases", post(jrebel_leases_handler))
        .route("/jrebel/leases/1", post(jrebel_leases1_handler))
        .route("/agent/leases", post(jrebel_leases_handler))
        .route("/agent/leases/1", post(jrebel_leases1_handler))
        .route("/jrebel/validate-connection", post(jrebel_validate_handler))
        .route("/rpc/ping.action", post(ping_handler))
        .route("/rpc/obtainTicket.action", post(obtain_ticket_handler))
        .route("/rpc/releaseTicket.action", post(release_ticket_handler))
        .layer(ServiceBuilder::new().layer(TraceLayer::new_for_http()))
        .with_state(config.clone());

    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", config.port)).await
        .map_err(|e| {
            error!("Failed to bind to port {}: {}", config.port, e);
            e
        })?;
    
    info!(
        "Start server with port = {}, schema = {}",
        config.port, config.export_schema
    );
    info!("Server listening on http://0.0.0.0:{}", config.port);
    debug!("Routes registered: /, /health, /health/simple, /jrebel/leases, /jrebel/leases/1, /agent/leases, /agent/leases/1, /jrebel/validate-connection, /rpc/ping.action, /rpc/obtainTicket.action, /rpc/releaseTicket.action");

    // Start the server and run indefinitely
    axum::serve(listener, app).await?;

    Ok(())
}
