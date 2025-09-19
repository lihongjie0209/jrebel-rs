use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::{Html, Json, Response},
    Form,
};
use serde::Deserialize;
use std::collections::HashMap;
use std::sync::Arc;
use tracing::{info, debug, warn, error};

use crate::structs::{Config, JRebelLeasesStruct, JRebelLeases1Struct, JRebelValidateStruct};
use crate::crypto::{to_lease_create_json, sign_with_md5};
use crate::utils::{new_server_randomness, new_uuid_v4_string, current_time_millis, bytes_to_hex};

#[derive(Deserialize)]
pub struct LeaseParams {
    randomness: Option<String>,
    username: Option<String>,
    guid: Option<String>,
    product: Option<String>,
    offline: Option<String>,
    #[serde(rename = "clientTime")]
    client_time: Option<String>,
    #[serde(rename = "offlineDays")]
    offline_days: Option<String>,
    #[serde(rename = "oldGuid")]
    old_guid: Option<String>,
}

pub async fn index_handler(
    State(config): State<Arc<Config>>,
    headers: HeaderMap,
) -> Html<String> {
    info!("Processing index page request");
    debug!("Request headers: {:?}", headers);
    
    let host = if config.export_host.is_empty() {
        let host_header = headers
            .get("host")
            .and_then(|h| h.to_str().ok())
            .unwrap_or("localhost");
        format!("{}://{}", config.export_schema, host_header)
    } else {
        format!("{}://{}", config.export_schema, config.export_host)
    };

    debug!("Generated host URL: {}", host);

    let uuid = new_uuid_v4_string();
    debug!("Generated UUID: {}", uuid);

    let html = if config.new_index {
        debug!("Using new index page template");
        create_new_index_html(&host, &uuid)
    } else {
        debug!("Using simple index page template");
        create_simple_index_html(&host, &uuid)
    };

    info!("Index page generated successfully");
    Html(html)
}

pub async fn jrebel_leases_handler(
    State(config): State<Arc<Config>>,
    Form(form_data): Form<HashMap<String, String>>,
) -> Result<Json<JRebelLeasesStruct>, StatusCode> {
    info!("Processing JRebel leases request");
    debug!("Received form data: {:?}", form_data);

    // Validate required parameters
    let client_randomness = form_data.get("randomness");
    let username = form_data.get("username");
    let guid = form_data.get("guid");

    if client_randomness.is_none() {
        error!("Missing required parameter: randomness");
        return Err(StatusCode::BAD_REQUEST);
    }
    if username.is_none() {
        error!("Missing required parameter: username");
        return Err(StatusCode::BAD_REQUEST);
    }
    if guid.is_none() {
        error!("Missing required parameter: guid");
        return Err(StatusCode::BAD_REQUEST);
    }

    let client_randomness = client_randomness.unwrap();
    let username = username.unwrap();
    let guid = guid.unwrap();

    debug!("Parameters - randomness: {}, username: {}, guid: {}", 
           client_randomness, username, guid);

    if client_randomness.is_empty() || username.is_empty() || guid.is_empty() {
        warn!("One or more required parameters are empty");
        return Err(StatusCode::BAD_REQUEST);
    }

    // Determine offline mode
    let offline = determine_offline_mode(&form_data, config.as_ref());
    info!("Determined offline mode: {}", offline);

    let mut response_body = JRebelLeasesStruct::default();
    response_body.company = username.clone();

    let (valid_from, valid_until) = if offline {
        debug!("Processing offline license request");
        
        let client_time = form_data
            .get("clientTime")
            .and_then(|t| {
                debug!("Parsing client time: {}", t);
                t.parse::<i64>().map_err(|e| {
                    warn!("Failed to parse client time '{}': {}", t, e);
                    e
                }).ok()
            })
            .unwrap_or_else(|| {
                let current = current_time_millis();
                debug!("Using current time as client time: {}", current);
                current
            });

        let offline_days = form_data
            .get("offlineDays")
            .and_then(|d| {
                debug!("Parsing offline days: {}", d);
                d.parse::<i64>().map_err(|e| {
                    warn!("Failed to parse offline days '{}': {}", d, e);
                    e
                }).ok()
            })
            .unwrap_or_else(|| {
                let default_days = config.offline_days as i64;
                debug!("Using default offline days: {}", default_days);
                default_days
            });

        let expire_time = client_time + (offline_days * 24 * 60 * 60 * 1000);
        
        debug!("License timing - client_time: {}, offline_days: {}, expire_time: {}", 
               client_time, offline_days, expire_time);
        
        response_body.offline = true;
        response_body.valid_from = Some(client_time);
        response_body.valid_until = Some(expire_time);

        (client_time.to_string(), expire_time.to_string())
    } else {
        debug!("Processing online license request");
        ("".to_string(), "".to_string())
    };

    let server_randomness = new_server_randomness();
    debug!("Generated server randomness: {}", server_randomness);
    
    debug!("Calling signature generation...");
    let signature = match to_lease_create_json(
        client_randomness,
        &server_randomness,
        guid,
        offline,
        &valid_from,
        &valid_until,
    ) {
        Ok(sig) => {
            info!("Signature generated successfully");
            sig
        },
        Err(e) => {
            error!("Failed to generate signature: {:?}", e);
            return Err(StatusCode::INTERNAL_SERVER_ERROR);
        }
    };

    response_body.server_randomness = server_randomness;
    response_body.signature = signature;

    debug!("Response body prepared: {:?}", response_body);
    info!("JRebel leases request processed successfully");
    Ok(Json(response_body))
}

pub async fn jrebel_leases1_handler(
    Form(form_data): Form<HashMap<String, String>>,
) -> Json<JRebelLeases1Struct> {
    info!("Processing JRebel leases1 request");

    let mut response_body = JRebelLeases1Struct::default();
    
    if let Some(username) = form_data.get("username") {
        if !username.is_empty() {
            response_body.company = username.clone();
        }
    }

    Json(response_body)
}

pub async fn jrebel_validate_handler() -> Json<JRebelValidateStruct> {
    info!("Processing JRebel validate request");
    Json(JRebelValidateStruct::default())
}

pub async fn ping_handler(
    Form(form_data): Form<HashMap<String, String>>,
) -> Result<Response<String>, StatusCode> {
    info!("Processing ping request");
    debug!("Ping form data: {:?}", form_data);

    let salt = form_data.get("salt");
    if salt.is_none() {
        error!("Missing required parameter: salt");
        return Err(StatusCode::BAD_REQUEST);
    }
    
    let salt = salt.unwrap();
    if salt.is_empty() {
        warn!("Salt parameter is empty");
        return Err(StatusCode::BAD_REQUEST);
    }

    debug!("Using salt: {}", salt);

    let xml_content = format!(
        "<PingResponse><message></message><responseCode>OK</responseCode><salt>{}</salt></PingResponse>",
        salt
    );
    debug!("Generated XML content: {}", xml_content);

    let signature = match sign_with_md5(xml_content.as_bytes()) {
        Ok(sig) => {
            debug!("MD5 signature generated successfully for ping");
            sig
        },
        Err(e) => {
            error!("Failed to generate MD5 signature for ping: {:?}", e);
            return Err(StatusCode::INTERNAL_SERVER_ERROR);
        }
    };
    
    let hex_signature = bytes_to_hex(&signature);
    debug!("Hex signature: {}", hex_signature);
    
    let body = format!("<!-- {} -->\n{}", hex_signature, xml_content);
    debug!("Final ping response body: {}", body);

    info!("Ping request processed successfully");
    Ok(Response::builder()
        .status(StatusCode::OK)
        .header("content-type", "text/html; charset=utf-8")
        .body(body)
        .unwrap())
}

pub async fn obtain_ticket_handler(
    Form(form_data): Form<HashMap<String, String>>,
) -> Result<Response<String>, StatusCode> {
    info!("Processing obtain ticket request");

    let salt = form_data.get("salt").ok_or(StatusCode::FORBIDDEN)?;
    let username = form_data.get("userName").ok_or(StatusCode::FORBIDDEN)?;

    if salt.is_empty() || username.is_empty() {
        return Err(StatusCode::FORBIDDEN);
    }

    let prolongation_period = "607875500";
    let xml_content = format!(
        "<ObtainTicketResponse><message></message><prolongationPeriod>{}</prolongationPeriod><responseCode>OK</responseCode><salt>{}</salt><ticketId>1</ticketId><ticketProperties>licensee={}\tlicenseType=0\t</ticketProperties></ObtainTicketResponse>",
        prolongation_period, salt, username
    );

    let signature = sign_with_md5(xml_content.as_bytes())
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    
    let hex_signature = bytes_to_hex(&signature);
    let body = format!("<!-- {} -->\n{}", hex_signature, xml_content);

    Ok(Response::builder()
        .status(StatusCode::OK)
        .header("content-type", "application/json; charset=utf-8")
        .body(body)
        .unwrap())
}

pub async fn release_ticket_handler(
    Form(form_data): Form<HashMap<String, String>>,
) -> Result<Response<String>, StatusCode> {
    info!("Processing release ticket request");

    let salt = form_data.get("salt").ok_or(StatusCode::FORBIDDEN)?;
    
    if salt.is_empty() {
        return Err(StatusCode::FORBIDDEN);
    }

    let xml_content = format!(
        "<ReleaseTicketResponse><message></message><responseCode>OK</responseCode><salt>{}</salt></ReleaseTicketResponse>",
        salt
    );

    let signature = sign_with_md5(xml_content.as_bytes())
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    
    let hex_signature = bytes_to_hex(&signature);
    let body = format!("<!-- {} -->\n{}", hex_signature, xml_content);

    Ok(Response::builder()
        .status(StatusCode::OK)
        .header("content-type", "text/html; charset=utf-8")
        .body(body)
        .unwrap())
}

fn determine_offline_mode(form_data: &HashMap<String, String>, config: &Config) -> bool {
    let empty_string = String::new();
    let product = form_data.get("product").unwrap_or(&empty_string);
    
    debug!("Determining offline mode for product: '{}'", product);
    debug!("JRebel work mode: {}", config.jrebel_work_mode);
    
    if product == "XRebel" {
        debug!("Product is XRebel, forcing online mode");
        return false;
    }

    let result = match config.jrebel_work_mode {
        1 => {
            debug!("Work mode 1: force offline mode");
            true
        },
        2 => {
            debug!("Work mode 2: force online mode");
            false
        },
        3 => {
            let old_guid = form_data.get("oldGuid");
            debug!("Work mode 3: oldGuid mode, oldGuid value: {:?}", old_guid);
            old_guid.map_or(false, |g| !g.is_empty())
        },
        _ => {
            let offline_param = form_data.get("offline");
            debug!("Work mode auto: offline parameter: {:?}", offline_param);
            offline_param
                .and_then(|s| {
                    match s.parse::<bool>() {
                        Ok(val) => {
                            debug!("Successfully parsed offline parameter: {}", val);
                            Some(val)
                        },
                        Err(e) => {
                            warn!("Failed to parse offline parameter '{}': {}", s, e);
                            None
                        }
                    }
                })
                .unwrap_or(false)
        }
    };
    
    info!("Offline mode determined: {}", result);
    result
}

fn create_new_index_html(host: &str, uuid: &str) -> String {
    format!(r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JRebel License Server</title>
    <style>
        :root {{
            --primary-color: #4a6bff;
            --secondary-color: #f5f5f5;
            --accent-color: #ff5252;
            --text-color: #333;
            --light-text: #666;
            --border-radius: 8px;
            --box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            --transition: all 0.3s ease;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 900px;
            margin: 40px auto;
            background-color: white;
            border-radius: var(--border-radius);
            box-shadow: var(--box-shadow);
            overflow: hidden;
        }}

        header {{
            background-color: var(--primary-color);
            color: white;
            padding: 20px 30px;
            position: relative;
        }}

        h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}

        .content {{
            padding: 30px;
        }}

        .info-card {{
            background-color: var(--secondary-color);
            border-radius: var(--border-radius);
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }}

        .info-card h2 {{
            font-size: 20px;
            margin-bottom: 15px;
            color: var(--primary-color);
        }}

        .activation-url {{
            display: flex;
            align-items: center;
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            margin: 10px 0;
            position: relative;
        }}

        .url-text {{
            flex-grow: 1;
            font-family: monospace;
            word-break: break-all;
        }}

        .highlight {{
            color: var(--accent-color);
            font-weight: bold;
        }}

        footer {{
            text-align: center;
            padding: 20px;
            color: var(--light-text);
            font-size: 14px;
            border-top: 1px solid #eee;
        }}

        footer a {{
            color: var(--primary-color);
            text-decoration: none;
        }}

        footer a:hover {{
            text-decoration: underline;
        }}

        @media (max-width: 768px) {{
            .container {{
                margin: 20px auto;
            }}

            header {{
                padding: 15px 20px;
            }}

            .content {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>JRebel License Server</h1>
    </header>

    <div class="content">
        <div class="info-card">
            <h2>Server Information</h2>
            <p>License Server started at:</p>
            <div class="activation-url">
                <span class="url-text">{}</span>
            </div>
        </div>

        <div class="info-card">
            <h2>JRebel 7.1 and Earlier Versions</h2>
            <p>Activation address (with any email):</p>
            <div class="activation-url">
                <span class="url-text">{}/<span class="highlight">{{tokenname}}</span></span>
            </div>
        </div>

        <div class="info-card">
            <h2>JRebel 2018.1 and Later Versions</h2>
            <p>Activation address (with any email address):</p>
            <div class="activation-url">
                <span class="url-text">{}/<span class="highlight">{}</span></span>
            </div>
        </div>
    </div>

    <footer>
        <p>
            <a href="https://github.com/yu-xiaoyao/jrebel-license-active-server" target="_blank">Developed from 2019 year</a>
        </p>
    </footer>
</div>

</body>
</html>"#, host, host, host, uuid)
}

fn create_simple_index_html(host: &str, uuid: &str) -> String {
    format!(r#"<h1>Hello,This is a Jrebel License Server!</h1>
<p>License Server started at {}</p>
<p>JRebel 7.1 and earlier version Activation address was: <span style='color:red'>{}/{{tokenname}}</span>, with any email.</p>
<p>JRebel 2018.1 and later version Activation address was: {}/{{guid}}(eg:<span style='color:red'> {}/{} </span>), with any email.</p>"#, 
    host, host, host, host, uuid)
}