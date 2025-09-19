use anyhow::{Result, Context};
use base64::{Engine as _, engine::general_purpose};
use rsa::{RsaPrivateKey, pkcs8::DecodePrivateKey};
use rsa::pkcs1v15::{SigningKey};
use rsa::signature::{Signer, SignatureEncoding};
use sha1::{Sha1, Digest};
use md5::{Md5, Digest as Md5Digest};
use tracing::{debug, info};

// PEM private key - same as in Go version
const PRIVATE_KEY: &str = "-----BEGIN PRIVATE KEY-----
MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBAND3cI/pKMSd4OLMIXU/8xoEZ/nz
a+g00Vy7ygyGB1Nn83qpro7tckOvUVILJoN0pKw8J3E8rtjhSyr9849qzaQKBhxFL+J5uu08QVn/
tMt+Tf0cu5MSPOjT8I2+NWyBZ6H0FjOcVrEUMvHt8sqoJDrDU4pJyex2rCOlpfBeqK6XAgMBAAEC
gYBM5C+8FIxWxM1CRuCs1yop0aM82vBC0mSTXdo7/3lknGSAJz2/A+o+s50Vtlqmll4drkjJJw4j
acsR974OcLtXzQrZ0G1ohCM55lC3kehNEbgQdBpagOHbsFa4miKnlYys537Wp+Q61mhGM1weXzos
gCH/7e/FjJ5uS6DhQc0Y+QJBAP43hlSSEo1BbuanFfp55yK2Y503ti3Rgf1SbE+JbUvIIRsvB24x
Ha1/IZ+ttkAuIbOUomLN7fyyEYLWphIy9kUCQQDSbqmxZaJNRa1o4ozGRORxR2KBqVn3EVISXqNc
UH3gAP52U9LcnmA3NMSZs8tzXhUhYkWQ75Q6umXvvDm4XZ0rAkBoymyWGeyJy8oyS/fUW0G63mIr
oZZ4Rp+F098P3j9ueJ2k/frbImXwabJrhwjUZe/Afel+PxL2ElUDkQW+BMHdAkEAk/U7W4Aanjpf
s1+Xm9DUztFicciheRa0njXspvvxhY8tXAWUPYseG7L+iRPh+Twtn0t5nm7VynVFN0shSoCIAQJA
Ljo7A6bzsvfnJpV+lQiOqD/WCw3A2yPwe+1d0X/13fQkgzcbB3K0K81Euo/fkKKiBv0A7yR7wvrN
jzefE9sKUw==
-----END PRIVATE KEY-----";

const ASM_PRIVATE_KEY: &str = "-----BEGIN PRIVATE KEY-----
MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEAt5yrcHAAjhglnCEn
6yecMWPeUXcMyo0+itXrLlkpcKIIyqPw546bGThhlb1ppX1ySX/OUA4jSakHekNP
5eWPawIDAQABAkBbr9pUPTmpuxkcy9m5LYBrkWk02PQEOV/fyE62SEPPP+GRhv4Q
Fgsu+V2GCwPQ69E3LzKHPsSNpSosIHSO4g3hAiEA54JCn41fF8GZ90b9L5dtFQB2
/yIcGX4Xo7bCvl8DaPMCIQDLCUN8YiXppydqQ+uYkTQgvyq+47cW2wcGumRS46dd
qQIhAKp2v5e8AMj9ROFO5B6m4SsVrIkwFICw17c0WzDRxTEBAiAYDmftk990GLcF
0zhV4lZvztasuWRXE+p4NJtwasLIyQIgVKzknJe8VOt5a3shCMOyysoNEg+YAt02
O98RPCU0nJg=
-----END PRIVATE KEY-----";

// Helper function to parse private key like Go does: pem.Decode + x509.ParsePKCS8PrivateKey
fn parse_private_key_go_style(pem_str: &str) -> Result<RsaPrivateKey> {
    debug!("Parsing private key using Go-style method");
    
    // Step 1: Parse PEM block like Go's pem.Decode()
    let lines: Vec<&str> = pem_str.lines().collect();
    if lines.len() < 3 {
        return Err(anyhow::anyhow!("Invalid PEM format: too few lines"));
    }
    
    // Extract base64 content (skip BEGIN/END lines)
    let mut base64_lines = Vec::new();
    let mut in_content = false;
    
    for line in lines {
        if line.starts_with("-----BEGIN") {
            in_content = true;
            continue;
        }
        if line.starts_with("-----END") {
            break;
        }
        if in_content {
            // Remove spaces and tabs like Go's removeSpacesAndTabs()
            let cleaned = line.chars()
                .filter(|&c| c != ' ' && c != '\t')
                .collect::<String>();
            if !cleaned.is_empty() {
                base64_lines.push(cleaned);
            }
        }
    }
    
    let base64_content = base64_lines.join("");
    debug!("Cleaned base64 content length: {}", base64_content.len());
    
    // Step 2: Decode base64 to get DER bytes
    let der_bytes = general_purpose::STANDARD.decode(&base64_content)
        .context("Failed to decode base64 content")?;
    
    debug!("Successfully decoded {} DER bytes", der_bytes.len());
    
    // Step 3: Parse PKCS#8 DER like Go's x509.ParsePKCS8PrivateKey()
    let private_key = RsaPrivateKey::from_pkcs8_der(&der_bytes)
        .context("Failed to parse PKCS#8 DER")?;
    
    debug!("Successfully parsed RSA private key");
    Ok(private_key)
}

pub fn sign_with_sha1(data: &[u8]) -> Result<Vec<u8>> {
    debug!("Starting SHA1 signature process, data length: {}", data.len());
    debug!("Data to sign: {:?}", String::from_utf8_lossy(data));
    
    let private_key = parse_private_key_go_style(PRIVATE_KEY)
        .context("Failed to parse RSA private key")?;
    debug!("Successfully parsed RSA private key");
    
    // Create the signing key - this handles the hash computation internally
    let signing_key = SigningKey::<Sha1>::new(private_key);
    
    // Use deterministic signing (matches Go's deterministic SignPKCS1v15)
    // This is like calling signing_key.sign(data) which hashes then signs
    let signature = signing_key.sign(data);
    
    let signature_bytes = signature.to_vec();
    debug!("Signature generated successfully, length: {}", signature_bytes.len());
    info!("SHA1 signature completed successfully");
    
    Ok(signature_bytes)
}

pub fn sign_with_md5(data: &[u8]) -> Result<Vec<u8>> {
    debug!("Starting MD5 signature process, data length: {}", data.len());
    debug!("Data to sign: {:?}", String::from_utf8_lossy(data));
    
    let private_key = parse_private_key_go_style(ASM_PRIVATE_KEY)
        .context("Failed to parse ASM RSA private key")?;
    debug!("Successfully parsed ASM RSA private key");
    
    // Create MD5 hash
    let mut hasher = Md5::new();
    hasher.update(data);
    let hashed = hasher.finalize();
    debug!("MD5 hash computed: {:02x?}", hashed);
    
    // Create signing key and sign the hash
    let signing_key = SigningKey::<Md5>::new_unprefixed(private_key);
    let signature = signing_key.sign(&hashed);
    
    debug!("MD5 signature generated successfully, length: {}", signature.to_vec().len());
    info!("MD5 signature completed successfully");
    
    Ok(signature.to_vec())
}

pub fn to_lease_create_json(
    client_randomness: &str,
    server_randomness: &str,
    guid: &str,
    offline: bool,
    valid_from: &str,
    valid_until: &str,
) -> Result<String> {
    debug!("Creating lease signature with parameters:");
    debug!("  client_randomness: {}", client_randomness);
    debug!("  server_randomness: {}", server_randomness);
    debug!("  guid: {}", guid);
    debug!("  offline: {}", offline);
    debug!("  valid_from: {}", valid_from);
    debug!("  valid_until: {}", valid_until);
    
    let s2 = if offline {
        format!(
            "{};{};{};{};{};{}",
            client_randomness, server_randomness, guid, offline, valid_from, valid_until
        )
    } else {
        format!(
            "{};{};{};{}",
            client_randomness, server_randomness, guid, offline
        )
    };
    
    debug!("String to sign: {}", s2);
    
    let signature = sign_with_sha1(s2.as_bytes())
        .context("Failed to create SHA1 signature for lease")?;
    debug!("Raw signature bytes: {:02x?}", signature);
    
    let encoded = general_purpose::STANDARD.encode(&signature);
    debug!("Base64 encoded signature: {}", encoded);
    
    info!("Lease signature created successfully, length: {}", encoded.len());
    Ok(encoded)
}

pub fn encode_base64(data: &[u8]) -> String {
    general_purpose::STANDARD.encode(data)
}

pub fn decode_base64(s: &str) -> Result<Vec<u8>> {
    Ok(general_purpose::STANDARD.decode(s)?)
}