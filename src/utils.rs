use rand::Rng;
use uuid::Uuid;

const RAND_CHARSET: &[u8] = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890";

/// Generate server randomness similar to Go version
pub fn new_server_randomness() -> String {
    let mut rng = rand::thread_rng();
    let mut b = vec![0u8; 11];
    
    for i in 0..11 {
        let idx = rng.gen_range(0..RAND_CHARSET.len());
        b[i] = RAND_CHARSET[idx];
    }
    
    format!("{}=", String::from_utf8_lossy(&b))
}

/// Generate UUID v4 string
pub fn new_uuid_v4_string() -> String {
    Uuid::new_v4().to_string()
}

/// Convert bytes to hexadecimal string
pub fn bytes_to_hex(data: &[u8]) -> String {
    data.iter()
        .map(|b| format!("{:02x}", b))
        .collect::<String>()
}

/// Get current timestamp in milliseconds
pub fn current_time_millis() -> i64 {
    chrono::Utc::now().timestamp_millis()
}

/// Parse form-encoded body to key-value pairs
pub fn parse_form_body(body: &str) -> std::collections::HashMap<String, String> {
    let mut params = std::collections::HashMap::new();
    
    for pair in body.split('&') {
        if let Some((key, value)) = pair.split_once('=') {
            let decoded_key = urlencoding::decode(key).unwrap_or_default();
            let decoded_value = urlencoding::decode(value).unwrap_or_default();
            params.insert(decoded_key.to_string(), decoded_value.to_string());
        }
    }
    
    params
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_server_randomness() {
        let randomness = new_server_randomness();
        assert_eq!(randomness.len(), 12); // 11 chars + '='
        assert!(randomness.ends_with('='));
    }

    #[test]
    fn test_new_uuid_v4_string() {
        let uuid_str = new_uuid_v4_string();
        assert_eq!(uuid_str.len(), 36); // UUID format: 8-4-4-4-12
        assert!(uuid_str.contains('-'));
    }

    #[test]
    fn test_parse_form_body() {
        let body = "key1=value1&key2=value%202&key3=";
        let params = parse_form_body(body);
        
        assert_eq!(params.get("key1"), Some(&"value1".to_string()));
        assert_eq!(params.get("key2"), Some(&"value 2".to_string()));
        assert_eq!(params.get("key3"), Some(&"".to_string()));
    }
}