#!/usr/bin/env python3
"""
GCP Cloud Run 配置初始化脚本
帮助自动化设置GCP项目、服务账户、权限和GitHub Secrets
"""

import os
import sys
import json
import subprocess
import tempfile
import base64
from pathlib import Path
from datetime import datetime

# 第三方库
try:
    import click
    from inquirer import List as InquirerList, prompt, Text, Confirm
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.syntax import Syntax
    from rich import print as rprint
    import requests
    import yaml
except ImportError as e:
    print(f"❌ 缺少依赖库: {e}")
    print("请安装依赖: pip install -r scripts/requirements-gcp.txt")
    sys.exit(1)

console = Console()

class GCPProjectManager:
    """GCP项目管理器"""
    
    def __init__(self):
        self.project_id = None
        self.region = None
        self.service_name = None
        self.service_account_name = "github-actions-cloud-run"
        self.gcloud_path = None
        
    def _get_git_project_name(self):
        """获取git项目名称"""
        try:
            # 尝试从git remote获取项目名称
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=os.getcwd()
            )
            
            if result.returncode == 0 and result.stdout.strip():
                url = result.stdout.strip()
                # 从URL中提取项目名称
                if '/' in url:
                    project_name = url.split('/')[-1]
                    # 移除.git后缀
                    if project_name.endswith('.git'):
                        project_name = project_name[:-4]
                    return project_name
            
            # 如果获取remote失败，尝试从当前目录名获取
            current_dir = os.path.basename(os.getcwd())
            if current_dir:
                return current_dir
                
        except Exception:
            pass
        
        # 默认返回
        return "qrcode-server-rs"
        
    def _find_gcloud_path(self):
        """查找gcloud的绝对路径"""
        # 常见的Google Cloud SDK安装路径
        possible_paths = [
            r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
            r"C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
            r"C:\Users\{}\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd".format(os.getenv('USERNAME', '')),
            "gcloud"  # 系统PATH中的gcloud
        ]
        
        for path in possible_paths:
            if path == "gcloud":
                # 检查系统PATH中是否有gcloud
                try:
                    result = subprocess.run(
                        ["where", "gcloud"],
                        capture_output=True,
                        text=True,
                        shell=True,
                        encoding='utf-8'
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        self.gcloud_path = result.stdout.strip().split('\n')[0]
                        console.print(f"📍 找到gcloud路径: {self.gcloud_path}", style="blue")
                        return True
                except:
                    continue
            else:
                # 检查绝对路径是否存在
                if os.path.exists(path):
                    self.gcloud_path = path
                    console.print(f"📍 找到gcloud路径: {self.gcloud_path}", style="blue")
                    return True
        
        console.print("❌ 未找到Google Cloud SDK安装路径", style="red")
        console.print("💡 请确保Google Cloud SDK已正确安装", style="yellow")
        console.print("💡 下载地址: https://cloud.google.com/sdk/docs/install", style="yellow")
        return False
        
    def _run_gcloud_command(self, args):
        """运行gcloud命令，使用找到的路径"""
        if not self.gcloud_path:
            if not self._find_gcloud_path():
                raise FileNotFoundError("未找到gcloud命令")
        
        cmd = [self.gcloud_path] + args
        return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
    def check_gcloud_auth(self):
        """检查gcloud认证状态"""
        try:
            # 首先查找gcloud路径
            if not self._find_gcloud_path():
                return False
                
            result = self._run_gcloud_command([
                "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"
            ])
            
            if result.returncode == 0 and result.stdout.strip():
                account = result.stdout.strip()
                console.print(f"✅ 已登录GCP账户: {account}", style="green")
                return True
            else:
                console.print("❌ 未登录GCP账户", style="red")
                return False
        except FileNotFoundError:
            console.print("❌ 未找到gcloud命令，请安装Google Cloud SDK", style="red")
            return False
    
    def login_gcloud(self):
        """登录gcloud"""
        console.print("🔐 开始GCP登录流程...")
        try:
            result = self._run_gcloud_command(["auth", "login"])
            if result.returncode == 0:
                console.print("✅ GCP登录成功", style="green")
                return True
            else:
                console.print("❌ GCP登录失败", style="red")
                return False
        except Exception as e:
            console.print(f"❌ GCP登录失败: {e}", style="red")
            return False
    
    def list_projects(self):
        """列出可用项目"""
        try:
            result = self._run_gcloud_command([
                "projects", "list", "--format=value(projectId,name)"
            ])
            
            projects = []
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('\t', 1)
                        if len(parts) == 2:
                            project_id, name = parts
                            projects.append({'id': project_id, 'name': name})
            
            return projects
        except:
            return []
    
    def select_project(self):
        """选择GCP项目"""
        projects = self.list_projects()
        
        if not projects:
            console.print("❌ 未找到可用项目", style="red")
            # 提供创建新项目的选项
            questions = [
                Confirm('create_new',
                       message="是否创建新项目?",
                       default=True)
            ]
            answers = prompt(questions)
            
            if answers['create_new']:
                return self._create_new_project()
            else:
                return False
        
        choices = []
        for project in projects:
            choices.append(f"{project['id']} - {project['name']}")
        choices.append("创建新项目")
        
        questions = [
            InquirerList('project',
                 message="选择GCP项目:",
                 choices=choices,
                 carousel=True)
        ]
        
        answers = prompt(questions)
        
        if answers['project'] == "创建新项目":
            return self._create_new_project()
        else:
            self.project_id = answers['project'].split(' - ')[0]
            console.print(f"✅ 已选择项目: {self.project_id}", style="green")
            return True
    
    def _create_new_project(self):
        """创建新项目"""
        # 获取git项目名称作为默认项目名称
        git_project_name = self._get_git_project_name()
        
        questions = [
            Text('project_id',
                 message="输入项目ID (只能包含小写字母、数字和连字符):",
                 validate=lambda _, x: len(x) >= 6 and x.replace('-', '').isalnum()),
            Text('project_name',
                 message="输入项目名称:",
                 default=git_project_name)
        ]
        
        answers = prompt(questions)
        
        try:
            console.print(f"🏗️ 创建项目: {answers['project_id']}")
            result = self._run_gcloud_command([
                "projects", "create", answers['project_id'],
                "--name", answers['project_name']
            ])
            
            if result.returncode == 0:
                self.project_id = answers['project_id']
                console.print(f"✅ 项目创建成功: {self.project_id}", style="green")
                return True
            else:
                console.print(f"❌ 项目创建失败: {result.stderr}", style="red")
                return False
        except Exception as e:
            console.print(f"❌ 项目创建失败: {e}", style="red")
            return False
    
    def set_project(self):
        """设置当前项目"""
        try:
            result = self._run_gcloud_command(["config", "set", "project", self.project_id])
            if result.returncode == 0:
                console.print(f"✅ 已设置当前项目: {self.project_id}", style="green")
                return True
            else:
                console.print(f"❌ 设置项目失败: {result.stderr}", style="red")
                return False
        except Exception as e:
            console.print(f"❌ 设置项目失败: {e}", style="red")
            return False

class GCPServiceManager:
    """GCP服务管理器"""
    
    def __init__(self, project_manager):
        self.project_id = project_manager.project_id
        self.project_manager = project_manager
    
    def enable_apis(self):
        """启用必要的API"""
        apis = [
            "run.googleapis.com",
            "containerregistry.googleapis.com",
            "artifactregistry.googleapis.com",
            "iam.googleapis.com"
        ]
        
        console.print("🔧 启用必要的API服务...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            for api in apis:
                task = progress.add_task(f"启用 {api}...", total=None)
                
                try:
                    result = self.project_manager._run_gcloud_command([
                        "services", "enable", api
                    ])
                    
                    progress.remove_task(task)
                    if result.returncode == 0:
                        console.print(f"  ✅ {api}", style="green")
                    else:
                        console.print(f"  ❌ {api}: {result.stderr}", style="red")
                except Exception as e:
                    progress.remove_task(task)
                    console.print(f"  ❌ {api}: {e}", style="red")
        
        console.print("✅ API启用完成", style="green")

class ServiceAccountManager:
    """服务账户管理器"""
    
    def __init__(self, project_manager, service_account_name):
        self.project_id = project_manager.project_id
        self.project_manager = project_manager
        self.service_account_name = service_account_name
        self.service_account_email = f"{service_account_name}@{self.project_id}.iam.gserviceaccount.com"
    
    def create_service_account(self):
        """创建服务账户"""
        console.print(f"👤 创建服务账户: {self.service_account_name}")
        
        try:
            # 检查服务账户是否已存在
            result = self.project_manager._run_gcloud_command([
                "iam", "service-accounts", "describe", self.service_account_email
            ])
            
            if result.returncode == 0:
                console.print(f"✅ 服务账户已存在: {self.service_account_email}", style="yellow")
                return True, False  # 存在，但不是新创建的
            
            # 创建新服务账户
            result = self.project_manager._run_gcloud_command([
                "iam", "service-accounts", "create", self.service_account_name,
                "--display-name", "GitHub Actions Cloud Run Deployer",
                "--description", "Service account for GitHub Actions to deploy to Cloud Run"
            ])
            
            if result.returncode == 0:
                console.print(f"✅ 服务账户创建成功: {self.service_account_email}", style="green")
                return True, True  # 创建成功，且是新创建的
            else:
                console.print(f"❌ 服务账户创建失败: {result.stderr}", style="red")
                return False, False
            
        except Exception as e:
            console.print(f"❌ 服务账户创建失败: {e}", style="red")
            return False, False
    
    def assign_permissions(self, is_new_service_account=True):
        """分配权限"""
        if not is_new_service_account:
            console.print("⏭️ 服务账户已存在，跳过权限分配步骤", style="yellow")
            return
        
        permissions = [
            "roles/run.developer",
            "roles/iam.serviceAccountUser",
            "roles/storage.objectViewer"
        ]
        
        console.print("🔐 分配服务账户权限...")
        
        for role in permissions:
            try:
                result = self.project_manager._run_gcloud_command([
                    "projects", "add-iam-policy-binding", self.project_id,
                    "--member", f"serviceAccount:{self.service_account_email}",
                    "--role", role
                ])
                
                if result.returncode == 0:
                    console.print(f"  ✅ {role}", style="green")
                else:
                    console.print(f"  ❌ {role}: {result.stderr}", style="red")
                
            except Exception as e:
                console.print(f"  ❌ {role}: {e}", style="red")
        
        console.print("✅ 权限分配完成", style="green")
    
    def create_key(self):
        """创建密钥文件"""
        console.print("🗝️ 创建服务账户密钥...")
        
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
                key_file = f.name
            
            result = self.project_manager._run_gcloud_command([
                "iam", "service-accounts", "keys", "create", key_file,
                "--iam-account", self.service_account_email
            ])
            
            if result.returncode == 0:
                # 读取密钥内容
                with open(key_file, 'r') as f:
                    key_content = f.read()
                
                # 删除临时文件
                os.unlink(key_file)
                
                console.print("✅ 服务账户密钥创建成功", style="green")
                return key_content
            else:
                console.print(f"❌ 密钥创建失败: {result.stderr}", style="red")
                return None
            
        except Exception as e:
            console.print(f"❌ 密钥创建失败: {e}", style="red")
            return None

class GitHubSecretsManager:
    """GitHub Secrets和Variables管理器"""
    
    def __init__(self):
        self.repo_info = None
        
    def _retry_command(self, func, *args, max_attempts=3, **kwargs):
        """重试命令执行"""
        for attempt in range(max_attempts):
            try:
                result = func(*args, **kwargs)
                if result:
                    return True
                if attempt < max_attempts - 1:
                    console.print(f"⚠️ 第{attempt + 1}次尝试失败，{max_attempts - attempt - 1}次重试剩余...", style="yellow")
                    import time
                    time.sleep(2)  # 等待2秒后重试
            except Exception as e:
                if attempt < max_attempts - 1:
                    console.print(f"⚠️ 第{attempt + 1}次尝试异常: {e}，{max_attempts - attempt - 1}次重试剩余...", style="yellow")
                    import time
                    time.sleep(2)
                else:
                    console.print(f"❌ 所有重试失败: {e}", style="red")
        return False
        
    def _check_gh_cli(self):
        """检查GitHub CLI是否已安装和认证"""
        try:
            # 检查gh命令是否存在
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                console.print("❌ 未找到GitHub CLI (gh)命令", style="red")
                console.print("💡 请安装GitHub CLI: https://cli.github.com/", style="yellow")
                return False
            
            # 检查是否已认证
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode != 0:
                console.print("❌ GitHub CLI未认证", style="red")
                console.print("💡 请运行: gh auth login", style="yellow")
                return False
            
            console.print("✅ GitHub CLI已安装并认证", style="green")
            return True
            
        except FileNotFoundError:
            console.print("❌ 未找到GitHub CLI (gh)命令", style="red")
            console.print("💡 请安装GitHub CLI: https://cli.github.com/", style="yellow")
            return False
    
    def _get_repo_info(self):
        """获取当前仓库信息"""
        try:
            result = subprocess.run(
                ["gh", "repo", "view", "--json", "owner,name"],
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode == 0:
                repo_data = json.loads(result.stdout)
                self.repo_info = {
                    'owner': repo_data['owner']['login'],
                    'name': repo_data['name']
                }
                console.print(f"📍 检测到仓库: {self.repo_info['owner']}/{self.repo_info['name']}", style="blue")
                return True
            else:
                console.print("❌ 无法获取仓库信息，请确保在Git仓库目录中运行", style="red")
                return False
                
        except Exception as e:
            console.print(f"❌ 获取仓库信息失败: {e}", style="red")
            return False
    
    def _set_secret_internal(self, secret_name, secret_value):
        """内部设置GitHub Secret方法"""
        if not self._check_gh_cli():
            return False
        
        if not self.repo_info and not self._get_repo_info():
            return False
        
        try:
            # 使用gh命令设置secret，通过stdin传递内容，指定为actions应用
            result = subprocess.run([
                "gh", "secret", "set", secret_name,
                "--app", "actions"
            ], input=secret_value, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                console.print(f"✅ 已设置GitHub Secret: {secret_name}", style="green")
                return True
            else:
                console.print(f"❌ 设置GitHub Secret失败: {secret_name}", style="red")
                console.print(f"错误信息: {result.stderr}", style="red")
                return False
                
        except Exception as e:
            console.print(f"❌ 设置GitHub Secret失败: {e}", style="red")
            return False
    
    def set_secret(self, secret_name, secret_value):
        """设置GitHub Secret（带重试）"""
        return self._retry_command(self._set_secret_internal, secret_name, secret_value)
    
    def _set_variable_internal(self, variable_name, variable_value):
        """内部设置GitHub Variable方法"""
        if not self._check_gh_cli():
            return False
        
        if not self.repo_info and not self._get_repo_info():
            return False
        
        try:
            # 使用gh命令设置variable
            result = subprocess.run([
                "gh", "variable", "set", variable_name,
                "--body", variable_value
            ], capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                console.print(f"✅ 已设置GitHub Variable: {variable_name} = {variable_value}", style="green")
                return True
            else:
                console.print(f"❌ 设置GitHub Variable失败: {variable_name}", style="red")
                console.print(f"错误信息: {result.stderr}", style="red")
                return False
                
        except Exception as e:
            console.print(f"❌ 设置GitHub Variable失败: {e}", style="red")
            return False
    
    def set_variable(self, variable_name, variable_value):
        """设置GitHub Variable（带重试）"""
        return self._retry_command(self._set_variable_internal, variable_name, variable_value)
    
    def set_multiple_variables(self, variables_dict):
        """批量设置GitHub Variables"""
        console.print("⚙️ 设置GitHub Variables...")
        
        success_count = 0
        total_count = len(variables_dict)
        
        for name, value in variables_dict.items():
            if self.set_variable(name, str(value)):
                success_count += 1
        
        if success_count == total_count:
            console.print(f"✅ 所有GitHub Variables设置成功 ({success_count}/{total_count})", style="green")
            return True
        else:
            console.print(f"⚠️ 部分GitHub Variables设置失败 ({success_count}/{total_count})", style="yellow")
            return False

class GitHubSetupManager:
    """GitHub独立设置管理器"""
    
    def __init__(self):
        # 使用临时目录存储敏感信息文件
        self.temp_dir = Path(tempfile.gettempdir()) / "gcp-config"
        self.temp_dir.mkdir(exist_ok=True)
        self.config_file = self.temp_dir / "gcp-config.yaml"
        self.service_account_key_file = self.temp_dir / "gcp-service-account-key.json"
        self.config = None
        self.service_account_key = None
    
    def _get_git_project_name(self):
        """获取git项目名称"""
        try:
            # 尝试从git remote获取项目名称
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=os.getcwd()
            )
            
            if result.returncode == 0 and result.stdout.strip():
                url = result.stdout.strip()
                # 从URL中提取项目名称
                if '/' in url:
                    project_name = url.split('/')[-1]
                    # 移除.git后缀
                    if project_name.endswith('.git'):
                        project_name = project_name[:-4]
                    return project_name
            
            # 如果获取remote失败，尝试从当前目录名获取
            current_dir = os.path.basename(os.getcwd())
            if current_dir:
                return current_dir
                
        except Exception:
            pass
        
        # 默认返回
        return "img-server-rs"
    
    def load_config(self):
        """从文件加载配置"""
        try:
            if not self.config_file.exists():
                console.print(f"❌ 配置文件不存在: {self.config_file}", style="red")
                console.print("💡 请先运行完整的GCP配置: python scripts/gcp_init.py", style="yellow")
                console.print("💡 配置文件现在存储在临时目录中，重启后可能需要重新配置", style="yellow")
                return False
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            console.print(f"✅ 已加载配置文件: {self.config_file}", style="green")
            return True
            
        except Exception as e:
            console.print(f"❌ 加载配置文件失败: {e}", style="red")
            return False
    
    def load_service_account_key(self):
        """从文件加载服务账户密钥"""
        try:
            if not self.service_account_key_file.exists():
                console.print(f"❌ 服务账户密钥文件不存在: {self.service_account_key_file}", style="red")
                console.print("💡 请先运行完整的GCP配置: python scripts/gcp_init.py", style="yellow")
                return False
            
            with open(self.service_account_key_file, 'r', encoding='utf-8') as f:
                self.service_account_key = f.read()
            
            console.print(f"✅ 已加载服务账户密钥文件: {self.service_account_key_file}", style="green")
            return True
            
        except Exception as e:
            console.print(f"❌ 加载服务账户密钥文件失败: {e}", style="red")
            return False
    
    def generate_variables(self):
        """根据配置生成GitHub Variables"""
        if not self.config:
            return {}
        
        # 获取git项目名称作为默认服务名称
        git_project_name = self._get_git_project_name()
        
        variables = {
            'CLOUD_RUN_SERVICE_NAME': self.config.get('service_name', git_project_name),
            'GCP_REGION': self.config.get('region', 'asia-east2'),
            'CLOUD_RUN_MEMORY': self.config.get('memory', '1Gi'),
            'CLOUD_RUN_CPU': str(self.config.get('cpu', '1')),
            'CLOUD_RUN_CONCURRENCY': str(self.config.get('concurrency', '80')),
            'CLOUD_RUN_MAX_INSTANCES': str(self.config.get('max_instances', '10')),
            'CLOUD_RUN_MIN_INSTANCES': str(self.config.get('min_instances', '0')),
            'GUNICORN_WORKERS': str(self.config.get('gunicorn_workers', '2')),
            'GUNICORN_LOG_LEVEL': 'info'
        }
        
        return variables
    
    def setup_from_config(self):
        """从配置文件设置GitHub Secrets和Variables"""
        console.print("\n🔧 [bold]从配置文件设置GitHub Secrets和Variables[/bold]")
        
        # 加载配置文件
        if not self.load_config():
            return False
        
        # 加载服务账户密钥
        if not self.load_service_account_key():
            return False
        
        # 显示配置信息
        console.print("\n📋 [bold]当前配置:[/bold]")
        config_table = Table()
        config_table.add_column("配置项", style="cyan")
        config_table.add_column("值", style="green")
        
        if self.config:
            config_table.add_row("项目ID", self.config.get('project_id', 'N/A'))
            config_table.add_row("区域", self.config.get('region', 'N/A'))
            config_table.add_row("服务名", self.config.get('service_name', 'N/A'))
            config_table.add_row("内存", self.config.get('memory', 'N/A'))
            config_table.add_row("CPU", str(self.config.get('cpu', 'N/A')))
        else:
            config_table.add_row("错误", "配置文件未加载")
        
        console.print(config_table)
        
        # 询问是否继续
        questions = [
            Confirm('confirm_setup',
                   message="确认使用上述配置设置GitHub Secrets和Variables?",
                   default=True)
        ]
        answers = prompt(questions)
        
        if not answers['confirm_setup']:
            console.print("❌ 用户取消操作", style="yellow")
            return False
        
        # 创建GitHub管理器并设置
        github_manager = GitHubSecretsManager()
        
        # 设置GitHub Secret (服务账户密钥)
        console.print("\n🔐 设置GitHub Secrets...")
        if not github_manager.set_secret("GCP_SA_KEY", self.service_account_key):
            return False
        
        # 设置GitHub Variables
        console.print("\n⚙️ 设置GitHub Variables...")
        variables = self.generate_variables()
        if not github_manager.set_multiple_variables(variables):
            return False
        
        console.print("\n✅ [bold green]GitHub配置完成![/bold green]", style="green")
        console.print("💡 可以通过以下命令验证设置:")
        console.print("   [dim]gh secret list[/dim]")
        console.print("   [dim]gh variable list[/dim]")
        
        return True

class ConfigurationManager:
    """配置管理器"""
    
    def __init__(self):
        self.config = {}
        # 使用临时目录存储配置文件
        self.temp_dir = Path(tempfile.gettempdir()) / "gcp-config"
        self.temp_dir.mkdir(exist_ok=True)
        self.config_file = self.temp_dir / "gcp-config.yaml"
        self.project_id = None
    
    def _get_git_project_name(self):
        """获取git项目名称"""
        try:
            # 尝试从git remote获取项目名称
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=os.getcwd()
            )
            
            if result.returncode == 0 and result.stdout.strip():
                url = result.stdout.strip()
                # 从URL中提取项目名称
                if '/' in url:
                    project_name = url.split('/')[-1]
                    # 移除.git后缀
                    if project_name.endswith('.git'):
                        project_name = project_name[:-4]
                    return project_name
            
            # 如果获取remote失败，尝试从当前目录名获取
            current_dir = os.path.basename(os.getcwd())
            if current_dir:
                return current_dir
                
        except Exception:
            pass
        
        # 默认返回
        return "img-server-rs"
    
    def collect_configuration(self):
        """收集配置信息"""
        console.print("\n⚙️ [bold]配置Cloud Run参数[/bold]")
        console.print("我们将分步骤收集配置信息，请按照提示选择：\n")
        
        # 获取git项目名称作为默认服务名称
        git_project_name = self._get_git_project_name()
        
        # 区域选择
        regions = [
            ("us-central1", "美国中部 (推荐)"),
            ("us-east1", "美国东部"),
            ("us-west1", "美国西部"),
            ("asia-east2", "亚洲东部2 (香港，推荐中国用户)"),
            ("asia-northeast1", "亚洲东北部 (东京，推荐中国用户)"),
            ("asia-southeast1", "亚洲东南部 (新加坡)"),
            ("europe-west1", "欧洲西部 (比利时)"),
            ("europe-west2", "欧洲西部 (伦敦)")
        ]
        
        region_choices = [f"{region[0]} - {region[1]}" for region in regions]
        
        # 分步骤收集配置信息，避免界面冲突
        answers = {}
        
        # 第1步：区域选择
        console.print("📍 [bold blue]步骤 1/6: 选择部署区域[/bold blue]")
        region_question = [
            InquirerList('region',
                 message="选择部署区域:",
                 choices=region_choices,
                 default=region_choices[3])  # 默认选择asia-east2 (香港)
        ]
        region_answer = prompt(region_question)
        answers.update(region_answer)
        
        # 第2步：服务名称
        console.print("\n🏷️ [bold blue]步骤 2/6: 设置服务名称[/bold blue]")
        service_question = [
            Text('service_name',
                 message="Cloud Run服务名称:",
                 default=git_project_name)
        ]
        service_answer = prompt(service_question)
        answers.update(service_answer)
        
        # 第3步：内存配置
        console.print("\n💾 [bold blue]步骤 3/6: 选择内存配置[/bold blue]")
        memory_question = [
            InquirerList('memory',
                 message="内存配置:",
                 choices=["512Mi", "1Gi", "2Gi", "4Gi"],
                 default="1Gi")
        ]
        memory_answer = prompt(memory_question)
        answers.update(memory_answer)
        
        # 第4步：CPU配置
        console.print("\n🖥️ [bold blue]步骤 4/6: 选择CPU配置[/bold blue]")
        cpu_question = [
            InquirerList('cpu',
                 message="CPU配置:",
                 choices=["1", "2", "4"],
                 default="1")
        ]
        cpu_answer = prompt(cpu_question)
        answers.update(cpu_answer)
        
        # 第5步：实例配置
        console.print("\n⚖️ [bold blue]步骤 5/6: 配置实例参数[/bold blue]")
        instance_questions = [
            Text('max_instances',
                 message="最大实例数:",
                 default="10"),
            
            Text('min_instances',
                 message="最小实例数 (0=按需启动):",
                 default="0"),
            
            Text('concurrency',
                 message="单实例并发数:",
                 default="80")
        ]
        instance_answers = prompt(instance_questions)
        answers.update(instance_answers)
        
        # 第6步：Gunicorn配置
        console.print("\n🔧 [bold blue]步骤 6/6: 配置应用参数[/bold blue]")
        gunicorn_question = [
            Text('gunicorn_workers',
                 message="Gunicorn工作进程数:",
                 default="2")
        ]
        gunicorn_answer = prompt(gunicorn_question)
        answers.update(gunicorn_answer)
        
        # 显示配置总结
        console.print("\n✅ [bold green]配置收集完成![/bold green]")
        console.print("\n📋 [bold]配置总结:[/bold]")
        
        config_summary = Table()
        config_summary.add_column("配置项", style="cyan")
        config_summary.add_column("值", style="green")
        
        config_summary.add_row("部署区域", answers['region'])
        config_summary.add_row("服务名称", answers['service_name'])
        config_summary.add_row("内存配置", answers['memory'])
        config_summary.add_row("CPU配置", answers['cpu'])
        config_summary.add_row("最大实例数", answers['max_instances'])
        config_summary.add_row("最小实例数", answers['min_instances'])
        config_summary.add_row("并发数", answers['concurrency'])
        config_summary.add_row("工作进程数", answers['gunicorn_workers'])
        
        console.print(config_summary)
        
        self.config = {
            'project_id': getattr(self, 'project_id', ''),
            'region': answers['region'].split(' - ')[0],
            'service_name': answers['service_name'],
            'memory': answers['memory'],
            'cpu': answers['cpu'],
            'max_instances': int(answers['max_instances']),
            'min_instances': int(answers['min_instances']),
            'concurrency': int(answers['concurrency']),
            'gunicorn_workers': int(answers['gunicorn_workers']),
            'created_at': datetime.now().isoformat()
        }
        
        return self.config
    
    def save_configuration(self):
        """保存配置到文件"""
        try:
            # 确保目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            
            console.print(f"✅ 配置已保存到: {self.config_file}", style="green")
            return True
        except Exception as e:
            console.print(f"❌ 配置保存失败: {e}", style="red")
            return False
    
    def generate_github_variables_instructions(self):
        """生成GitHub Variables设置说明"""
        # 获取git项目名称作为默认服务名称
        git_project_name = self._get_git_project_name()
        
        variables = {
            'CLOUD_RUN_SERVICE_NAME': self.config.get('service_name', git_project_name),
            'GCP_REGION': self.config.get('region', 'asia-east2'),
            'CLOUD_RUN_MEMORY': self.config.get('memory', '1Gi'),
            'CLOUD_RUN_CPU': str(self.config.get('cpu', '1')),
            'CLOUD_RUN_CONCURRENCY': str(self.config.get('concurrency', '80')),
            'CLOUD_RUN_MAX_INSTANCES': str(self.config.get('max_instances', '10')),
            'CLOUD_RUN_MIN_INSTANCES': str(self.config.get('min_instances', '0')),
            'GUNICORN_WORKERS': str(self.config.get('gunicorn_workers', '2')),
            'GUNICORN_LOG_LEVEL': 'info'
        }
        
        return variables

class GCPInitializer:
    """GCP初始化管理器"""
    
    def __init__(self):
        self.project_manager = GCPProjectManager()
        self.config_manager = ConfigurationManager()
        self.service_account_key = None
        
    def run(self):
        """运行初始化流程"""
        
        # 显示欢迎信息
        self._show_welcome()
        
        # 检查前置条件
        if not self._check_prerequisites():
            return False
        
        # 选择或创建项目
        if not self.project_manager.select_project():
            return False
        
        # 设置当前项目
        if not self.project_manager.set_project():
            return False
        
        # 启用API服务
        service_manager = GCPServiceManager(self.project_manager)
        service_manager.enable_apis()
        
        # 创建服务账户
        sa_manager = ServiceAccountManager(
            self.project_manager,
            self.project_manager.service_account_name
        )
        
        success, is_new = sa_manager.create_service_account()
        if not success:
            return False
        
        sa_manager.assign_permissions(is_new)
        
        # 创建密钥
        self.service_account_key = sa_manager.create_key()
        if not self.service_account_key:
            return False
        
        # 收集配置
        self.config_manager.project_id = self.project_manager.project_id
        config = self.config_manager.collect_configuration()
        self.config_manager.save_configuration()
        
        # 自动设置GitHub Secrets和Variables
        self._setup_github_secrets_and_variables()
        
        # 显示设置说明
        self._show_setup_instructions(sa_manager.service_account_email)
        
        return True
    
    def _show_welcome(self):
        """显示欢迎信息"""
        console.print()
        console.print(Panel.fit(
            "🌐 [bold blue]GCP Cloud Run 配置初始化工具[/bold blue]\n\n"
            "此工具将帮助你:\n"
            "• 设置GCP项目和权限\n"
            "• 创建服务账户和密钥\n"
            "• 配置Cloud Run参数\n"
            "• 生成GitHub配置说明",
            title="GCP配置工具",
            style="blue"
        ))
    
    def _check_prerequisites(self):
        """检查前置条件"""
        console.print("\n🔍 [bold]检查前置条件[/bold]")
        
        # 检查gcloud认证
        if not self.project_manager.check_gcloud_auth():
            questions = [
                Confirm('login_now',
                       message="是否立即登录GCP?",
                       default=True)
            ]
            answers = prompt(questions)
            
            if answers['login_now']:
                if not self.project_manager.login_gcloud():
                    return False
            else:
                console.print("❌ 需要先登录GCP", style="red")
                return False
        
        return True
    
    def _setup_github_secrets_and_variables(self):
        """自动设置GitHub Secrets和Variables"""
        console.print("\n🔧 [bold]自动配置GitHub Secrets和Variables[/bold]")
        
        # 创建GitHub管理器
        github_manager = GitHubSecretsManager()
        
        # 询问是否自动设置
        questions = [
            Confirm('auto_setup',
                   message="是否自动设置GitHub Secrets和Variables?",
                   default=True)
        ]
        answers = prompt(questions)
        
        if not answers['auto_setup']:
            console.print("⏭️ 跳过自动设置，将在最后显示手动设置说明", style="yellow")
            return
        
        # 设置GitHub Secret (服务账户密钥)
        console.print("\n🔐 设置GitHub Secrets...")
        github_manager.set_secret("GCP_SA_KEY", self.service_account_key)
        
        # 设置GitHub Variables
        console.print("\n⚙️ 设置GitHub Variables...")
        variables = self.config_manager.generate_github_variables_instructions()
        github_manager.set_multiple_variables(variables)
        
        console.print("\n✅ GitHub配置完成!", style="green")
    
    def _show_setup_instructions(self, service_account_email):
        """显示设置说明"""
        console.print("\n" + "="*60)
        console.print("🎉 [bold green]GCP配置完成![/bold green]")
        console.print("="*60)
        
        # 显示项目信息
        console.print("\n📋 [bold]项目信息:[/bold]")
        project_table = Table()
        project_table.add_column("项目", style="cyan")
        project_table.add_column("值", style="green")
        
        project_table.add_row("项目ID", self.project_manager.project_id)
        project_table.add_row("区域", self.config_manager.config['region'])
        project_table.add_row("服务名", self.config_manager.config['service_name'])
        project_table.add_row("服务账户", service_account_email)
        
        console.print(project_table)
        
        # 检查是否自动设置了GitHub配置
        try:
            # 检查是否有gh命令并且已认证
            result = subprocess.run(["gh", "auth", "status"], capture_output=True, encoding='utf-8')
            auto_setup_available = (result.returncode == 0)
        except:
            auto_setup_available = False
        
        if auto_setup_available:
            console.print("\n✅ [bold green]GitHub Secrets和Variables已自动配置完成![/bold green]")
            console.print("如需手动验证，请查看GitHub仓库的 Settings > Secrets and variables > Actions")
        else:
            # 显示手动设置说明
            self._show_manual_github_setup()
        
        # 保存密钥到临时文件
        temp_dir = Path(tempfile.gettempdir()) / "gcp-config"
        temp_dir.mkdir(exist_ok=True)
        key_file = temp_dir / "gcp-service-account-key.json"
        
        if self.service_account_key:
            try:
                with open(key_file, 'w') as f:
                    f.write(self.service_account_key)
                console.print(f"\n💾 服务账户密钥已保存到临时目录: [cyan]{key_file}[/cyan]")
                console.print("⚠️ [yellow]此文件存储在临时目录中，重启后可能丢失![/yellow]")
                console.print("⚠️ [yellow]如需长期保存，请妥善备份，不要提交到代码库![/yellow]")
            except Exception as e:
                console.print(f"❌ 密钥文件保存失败: {e}", style="red")
        else:
            console.print("❌ 没有服务账户密钥可保存", style="red")
        
        # 下一步说明
        console.print("\n🚀 [bold]下一步操作:[/bold]")
        console.print("1. 验证GitHub Secrets和Variables已正确设置")
        console.print("2. 推送版本标签测试自动部署:")
        console.print("   [dim]git tag v1.0.x && git push origin v1.0.x[/dim]")
    
    def _show_manual_github_setup(self):
        """显示手动GitHub设置说明"""
        # GitHub Secrets设置
        console.print("\n🔐 [bold]GitHub Secrets 手动设置:[/bold]")
        console.print("在GitHub仓库的 [cyan]Settings > Secrets and variables > Actions[/cyan] 中添加:")
        
        secrets_table = Table()
        secrets_table.add_column("Secret名称", style="yellow")
        secrets_table.add_column("说明", style="white")
        
        secrets_table.add_row("GCP_SA_KEY", "服务账户密钥 (JSON格式)")
        console.print(secrets_table)
        
        console.print("\n📄 [bold]服务账户密钥内容:[/bold]")
        syntax = Syntax(self.service_account_key, "json", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, title="GCP_SA_KEY", expand=False))
        
        # GitHub Variables设置
        console.print("\n⚙️ [bold]GitHub Variables 手动设置:[/bold]")
        console.print("在GitHub仓库的 [cyan]Settings > Secrets and variables > Actions > Variables[/cyan] 中添加:")
        
        variables = self.config_manager.generate_github_variables_instructions()
        variables_table = Table()
        variables_table.add_column("Variable名称", style="cyan")
        variables_table.add_column("值", style="green")
        
        for name, value in variables.items():
            variables_table.add_row(name, value)
        
        console.print(variables_table)

@click.command()
@click.option('--project-id', default=None, help='指定GCP项目ID')
@click.option('--region', default=None, help='指定部署区域')
@click.option('--service-name', default=None, help='指定Cloud Run服务名称')
@click.option('--github-only', is_flag=True, default=False, help='只设置GitHub Secrets和Variables（需要先运行完整配置）')
def main(project_id, region, service_name, github_only):
    """GCP Cloud Run 配置初始化工具"""
    
    try:
        if github_only:
            # 只设置GitHub相关信息
            github_setup = GitHubSetupManager()
            success = github_setup.setup_from_config()
        else:
            # 完整的GCP配置流程
            initializer = GCPInitializer()
            
            # 如果提供了命令行参数，直接使用
            if project_id:
                initializer.project_manager.project_id = project_id
            if region:
                initializer.project_manager.region = region
            if service_name:
                initializer.project_manager.service_name = service_name
            
            success = initializer.run()
        
        if success:
            console.print("\n🎉 [bold green]配置完成![/bold green]")
        else:
            console.print("\n❌ [bold red]配置失败[/bold red]")
            sys.exit(1)
            
    except KeyboardInterrupt:
        console.print("\n❌ 用户取消操作", style="yellow")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n❌ 配置失败: {e}", style="red")
        sys.exit(1)

if __name__ == "__main__":
    main()  # type: ignore
