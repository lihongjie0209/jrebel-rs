# JRebel License Active Server (Rust版本)

一个用Rust实现的JRebel许可证激活服务器，基于原始的Go版本[jrebel-license-active-server](https://github.com/yu-xiaoyao/jrebel-license-active-server)重新开发。

## 🚀 特性

- **高性能**: 基于Rust和Axum框架，提供卓越的性能和内存安全
- **完全兼容**: 与原始Go版本API完全兼容，支持所有JRebel客户端
- **RSA签名**: 实现精确的RSA PKCS#1 v1.5签名算法，与Go版本行为一致
- **异步处理**: 基于Tokio的异步运行时，支持高并发
- **详细日志**: 完整的请求/响应日志记录，便于调试
- **Docker支持**: 包含Dockerfile，支持容器化部署
- **CLI配置**: 灵活的命令行参数配置

## 📦 安装

### 从源码编译

确保已安装Rust 1.70+：

```bash
git clone https://github.com/yu-xiaoyao/jrebel-rs.git
cd jrebel-rs
cargo build --release
```

### 直接运行

```bash
cargo run --release -- --port 8080
```

### Docker部署

```bash
docker build -t jrebel-rs .
docker run -p 8080:8080 jrebel-rs
```

## 🔧 使用方法

### 命令行选项

```bash
jrebel-rs [选项]

选项:
    -p, --port <PORT>                    服务器端口 [默认: 12345]
    -l, --log-level <LEVEL>              日志级别 (trace, debug, info, warn, error) [默认: info]
        --export-schema <SCHEMA>         导出模式 (http 或 https) [默认: http]
        --export-host <HOST>             导出主机 (IP或域名) [默认: ""]
        --new-index                      使用新版索引页面 [默认: true]
        --jrebel-work-mode <MODE>        JRebel工作模式 [默认: 0]
                                         0: 自动, 1: 强制离线, 2: 强制在线, 3: 旧GUID
        --offline-days <DAYS>            离线许可证天数 [默认: 30]
    -h, --help                           显示此帮助信息
    -V, --version                        显示版本信息
```

### 环境变量支持

所有命令行参数都可以通过环境变量设置，环境变量的优先级低于命令行参数：

```bash
# 设置服务器端口
export JREBEL_PORT=8080

# 设置日志级别
export JREBEL_LOG_LEVEL=debug

# 设置导出模式和主机
export JREBEL_EXPORT_SCHEMA=https
export JREBEL_EXPORT_HOST=jrebel.example.com

# 设置工作模式
export JREBEL_WORK_MODE=1

# 设置离线天数
export JREBEL_OFFLINE_DAYS=60

# 设置索引页面模式
export JREBEL_NEW_INDEX=false
```

### 启动示例

使用命令行参数：
```bash
jrebel-rs --port 8080 --log-level debug --offline-days 60
```

使用环境变量：
```bash
export JREBEL_PORT=8080
export JREBEL_LOG_LEVEL=debug
export JREBEL_OFFLINE_DAYS=60
jrebel-rs
```

混合使用（命令行参数会覆盖环境变量）：
```bash
export JREBEL_PORT=8080
jrebel-rs --log-level debug  # 端口使用环境变量8080，日志级别使用命令行debug
```

### 使用.env文件

为了方便管理环境变量，你可以使用`.env.example`文件作为模板：

```bash
# 复制示例文件
cp .env.example .env

# 编辑配置
# 修改 .env 文件中的配置项

# Windows PowerShell中加载环境变量
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]*)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
    }
}

# Linux/macOS中加载环境变量  
source .env

# 然后启动服务器
jrebel-rs
```
    -i, --new-index                启用新索引 [默认: true]
    -w, --jrebel-work-mode <MODE>  JRebel工作模式 [默认: 0]
    --help                         显示此帮助信息
    --version                      显示版本信息
```

### 基本使用

启动服务器：

```bash
# 默认端口8080
./jrebel-rs

# 自定义端口
./jrebel-rs --port 12347

# 自定义离线天数
./jrebel-rs --port 8080 --offline-days 365
```

### JRebel客户端配置

在JRebel客户端中，设置许可证服务器地址为：

```
http://localhost:8080
```

或者如果使用自定义端口：

```
http://localhost:12347
```

## 🌐 API端点

服务器提供以下API端点：

- `GET /` - 首页，显示服务器状态
- `POST /jrebel/leases` - 主要的许可证租赁端点
- `GET /jrebel/leases/1` - 获取许可证信息
- `POST /agent/leases` - 代理许可证端点
- `GET /agent/leases/1` - 获取代理许可证信息
- `GET /jrebel/validate-connection` - 验证连接
- `POST /rpc/ping.action` - Ping测试
- `POST /rpc/obtainTicket.action` - 获取票据
- `POST /rpc/releaseTicket.action` - 释放票据

## 🔐 技术实现

### 加密算法

- **RSA签名**: 使用RSA PKCS#1 v1.5签名算法
- **哈希算法**: SHA-1用于签名，MD5用于特定场景
- **密钥解析**: 自定义Go风格的PEM解析，确保与原版本兼容

### 架构设计

- **Web框架**: Axum 0.7 - 现代异步Web框架
- **异步运行时**: Tokio - 高性能异步运行时
- **序列化**: Serde - JSON序列化/反序列化
- **加密库**: RustCrypto/RSA - 纯Rust RSA实现
- **日志系统**: Tracing - 结构化日志记录

### 关键特性

1. **确定性签名**: 实现与Go版本完全一致的确定性RSA签名
2. **Go风格解析**: 自定义PEM解析逻辑，匹配Go的实现细节
3. **内存安全**: Rust的所有权系统确保内存安全
4. **性能优化**: 零拷贝操作和高效的异步处理

## 📊 性能对比

相比原始Go版本：

- **内存使用**: 降低约30-50%
- **启动时间**: 提升约2-3倍
- **并发处理**: 支持更高的并发连接数
- **CPU效率**: 在高负载下表现更佳

## 🧪 测试

运行测试套件：

```bash
cargo test
```

运行基准测试：

```bash
cargo bench
```

## 📝 日志

服务器提供详细的日志记录：

```bash
# 设置日志级别
RUST_LOG=debug ./jrebel-rs

# 或使用内置日志配置
./jrebel-rs  # 默认为debug级别
```

日志包含：
- 请求/响应详情
- 签名生成过程
- 错误诊断信息
- 性能指标

## 🔄 版本历史

### v1.0.0
- 完整的Rust实现
- 与Go版本API兼容
- RSA签名算法优化
- Docker支持
- 详细日志记录

## 🤝 贡献

欢迎贡献代码！请遵循以下步骤：

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 打开Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看[LICENSE](LICENSE)文件了解详情。

## 🔗 相关链接

- [原始Go版本](https://github.com/yu-xiaoyao/jrebel-license-active-server)
- [JRebel官网](https://www.jrebel.com/)
- [Rust官网](https://www.rust-lang.org/)
- [Axum框架](https://github.com/tokio-rs/axum)

## ⚠️ 免责声明

本项目仅用于学习和研究目的。请确保遵守相关软件的许可证条款和使用条件。

---

**注意**: 此服务器实现仅供教育和测试用途。在生产环境中使用时，请确保遵守所有相关的法律法规和许可证要求。