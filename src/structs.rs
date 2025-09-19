use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JRebelLeasesStruct {
    #[serde(rename = "serverVersion")]
    pub server_version: String,
    
    #[serde(rename = "serverProtocolVersion")]
    pub server_protocol_version: String,
    
    #[serde(rename = "serverGuid")]
    pub server_guid: String,
    
    #[serde(rename = "groupType")]
    pub group_type: String,
    
    pub id: i32,
    
    #[serde(rename = "licenseType")]
    pub license_type: i32,
    
    #[serde(rename = "evaluationLicense")]
    pub evaluation_license: bool,
    
    pub signature: String,
    
    #[serde(rename = "serverRandomness")]
    pub server_randomness: String,
    
    #[serde(rename = "seatPoolType")]
    pub seat_pool_type: String,
    
    #[serde(rename = "statusCode")]
    pub status_code: String,
    
    pub offline: bool,
    
    #[serde(rename = "validFrom")]
    pub valid_from: Option<i64>,
    
    #[serde(rename = "validUntil")]
    pub valid_until: Option<i64>,
    
    pub company: String,
    
    #[serde(rename = "orderId")]
    pub order_id: String,
    
    #[serde(rename = "zeroIds")]
    pub zero_ids: Vec<serde_json::Value>,
    
    #[serde(rename = "licenseValidFrom")]
    pub license_valid_from: i64,
    
    #[serde(rename = "licenseValidUntil")]
    pub license_valid_until: i64,
}

impl Default for JRebelLeasesStruct {
    fn default() -> Self {
        Self {
            server_version: "3.2.4".to_string(),
            server_protocol_version: "1.1".to_string(),
            server_guid: "a1b4aea8-b031-4302-b602-670a990272cb".to_string(),
            group_type: "managed".to_string(),
            id: 1,
            license_type: 1,
            evaluation_license: false,
            signature: "OJE9wGg2xncSb+VgnYT+9HGCFaLOk28tneMFhCbpVMKoC/Iq4LuaDKPirBjG4o394/UjCDGgTBpIrzcXNPdVxVr8PnQzpy7ZSToGO8wv/KIWZT9/ba7bDbA8/RZ4B37YkCeXhjaixpmoyz/CIZMnei4q7oWR7DYUOlOcEWDQhiY=".to_string(),
            server_randomness: "H2ulzLlh7E0=".to_string(),
            seat_pool_type: "standalone".to_string(),
            status_code: "SUCCESS".to_string(),
            offline: false,
            valid_from: None,
            valid_until: None,
            company: "Administrator".to_string(),
            order_id: "".to_string(),
            zero_ids: vec![],
            license_valid_from: 1490544001000,
            license_valid_until: 1891839999000,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JRebelLeases1Struct {
    #[serde(rename = "serverVersion")]
    pub server_version: String,
    
    #[serde(rename = "serverProtocolVersion")]
    pub server_protocol_version: String,
    
    #[serde(rename = "serverGuid")]
    pub server_guid: String,
    
    #[serde(rename = "groupType")]
    pub group_type: String,
    
    #[serde(rename = "statusCode")]
    pub status_code: String,
    
    pub company: String,
    
    pub msg: Option<serde_json::Value>,
    
    #[serde(rename = "statusMessage")]
    pub status_message: Option<serde_json::Value>,
    
    pub signature: String,
}

impl Default for JRebelLeases1Struct {
    fn default() -> Self {
        Self {
            server_version: "3.2.4".to_string(),
            server_protocol_version: "1.1".to_string(),
            server_guid: "a1b4aea8-b031-4302-b602-670a990272cb".to_string(),
            group_type: "managed".to_string(),
            status_code: "SUCCESS".to_string(),
            company: "Administrator".to_string(),
            msg: None,
            status_message: None,
            signature: "dGVzdA==".to_string(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JRebelValidateStruct {
    #[serde(rename = "serverVersion")]
    pub server_version: String,
    
    #[serde(rename = "serverProtocolVersion")]
    pub server_protocol_version: String,
    
    #[serde(rename = "serverGuid")]
    pub server_guid: String,
    
    #[serde(rename = "groupType")]
    pub group_type: String,
    
    #[serde(rename = "statusCode")]
    pub status_code: String,
    
    pub company: String,
    
    #[serde(rename = "canGetLease")]
    pub can_get_lease: bool,
    
    #[serde(rename = "licenseType")]
    pub license_type: i32,
    
    #[serde(rename = "evaluationLicense")]
    pub evaluation_license: bool,
    
    #[serde(rename = "seatPoolType")]
    pub seat_pool_type: String,
}

impl Default for JRebelValidateStruct {
    fn default() -> Self {
        Self {
            server_version: "3.2.4".to_string(),
            server_protocol_version: "1.1".to_string(),
            server_guid: "a1b4aea8-b031-4302-b602-670a990272cb".to_string(),
            group_type: "managed".to_string(),
            status_code: "SUCCESS".to_string(),
            company: "Administrator".to_string(),
            can_get_lease: true,
            license_type: 1,
            evaluation_license: false,
            seat_pool_type: "standalone".to_string(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct Config {
    pub port: u16,
    pub offline_days: i32,
    pub log_level: String,
    pub export_schema: String,
    pub export_host: String,
    pub new_index: bool,
    pub jrebel_work_mode: i32,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            port: 12345,
            offline_days: 30,
            log_level: "info".to_string(),
            export_schema: "http".to_string(),
            export_host: "".to_string(),
            new_index: true,
            jrebel_work_mode: 0, // 0: auto, 1: force offline mode, 2: force online mode, 3: oldGuid
        }
    }
}