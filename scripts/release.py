#!/usr/bin/env python3
"""
自动化版本发布脚本
支持版本号自动生成、AI生成提交信息、自动标签和推送
"""

import os
import sys
import re
import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime

# 第三方库
try:
    import click
    from inquirer import List as InquirerList, prompt, Text
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.syntax import Syntax
    from rich import print as rprint
    from packaging import version
except ImportError as e:
    print(f"❌ 缺少依赖库: {e}")
    print("请安装依赖: pip install -r requirements-release.txt")
    sys.exit(1)

console = Console()

class VersionManager:
    """版本管理器"""
    
    def __init__(self, project_root):
        self.project_root = project_root
        self.current_version = self._get_current_version()
    
    def _get_current_version(self):
        """获取当前版本号"""
        # 从git标签获取最新版本
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=self.project_root
            )
            if result.returncode == 0:
                tag = result.stdout.strip()
                # 移除v前缀
                return tag.lstrip('v')
        except:
            pass
        
        # 从文件中查找版本号
        version_files = [
            "Cargo.toml",
            "pyproject.toml",
            "setup.py", 
            "src/core/config.py",
            "__init__.py"
        ]
        
        for file_path in version_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                version_str = self._extract_version_from_file(full_path)
                if version_str:
                    return version_str
        
        return "0.1.0"  # 默认版本
    
    def _extract_version_from_file(self, file_path):
        """从文件中提取版本号"""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # 针对 Cargo.toml 文件的特殊处理
            if file_path.name == "Cargo.toml":
                import re
                match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
                if match:
                    return match.group(1)
            
            patterns = [
                r'version\s*=\s*["\']([^"\']+)["\']',
                r'__version__\s*=\s*["\']([^"\']+)["\']',
                r'app_version\s*=\s*["\']([^"\']+)["\']',
                r'VERSION\s*=\s*["\']([^"\']+)["\']'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1)
        except:
            pass
        
        return None
    
    def bump_version(self, bump_type):
        """升级版本号"""
        try:
            current = version.parse(self.current_version)
            
            if bump_type == "patch":
                new_version = f"{current.major}.{current.minor}.{current.micro + 1}"
            elif bump_type == "minor":
                new_version = f"{current.major}.{current.minor + 1}.0"
            elif bump_type == "major":
                new_version = f"{current.major + 1}.0.0"
            else:
                raise ValueError(f"Invalid bump type: {bump_type}")
            
            return new_version
        except Exception as e:
            console.print(f"❌ 版本号升级失败: {e}", style="red")
            sys.exit(1)
    
    def update_cargo_version(self, new_version):
        """更新 Cargo.toml 中的版本号"""
        cargo_toml_path = self.project_root / "Cargo.toml"
        
        if not cargo_toml_path.exists():
            console.print("⚠️ 未找到 Cargo.toml 文件", style="yellow")
            return False
        
        try:
            content = cargo_toml_path.read_text(encoding='utf-8')
            
            # 使用正则表达式替换版本号
            import re
            pattern = r'(^\s*version\s*=\s*["\'])([^"\']+)(["\'])'
            replacement = f'\\g<1>{new_version}\\g<3>'
            
            new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            
            if new_content != content:
                cargo_toml_path.write_text(new_content, encoding='utf-8')
                console.print(f"✅ 已更新 Cargo.toml 版本号: {new_version}", style="green")
                return True
            else:
                console.print("⚠️ Cargo.toml 中未找到版本号或版本号已是最新", style="yellow")
                return False
                
        except Exception as e:
            console.print(f"❌ 更新 Cargo.toml 失败: {e}", style="red")
            return False

class GitManager:
    """Git管理器"""
    
    def __init__(self, project_root):
        self.project_root = project_root
    
    def get_uncommitted_changes(self):
        """获取未提交的更改"""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                return [line for line in lines if line.strip()]
            return []
        except:
            return []
    
    def get_recent_commits(self, count=10):
        """获取最近的提交记录"""
        try:
            result = subprocess.run(
                ["git", "log", f"--max-count={count}", "--pretty=format:%H|%s|%an|%ad", "--date=short"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=self.project_root
            )
            
            commits = []
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        hash_val, subject, author, date = line.split('|', 3)
                        commits.append({
                            'hash': hash_val[:8],
                            'subject': subject,
                            'author': author,
                            'date': date
                        })
            return commits
        except:
            return []
    
    def commit_changes(self, message):
        """提交所有更改"""
        try:
            # 添加所有文件
            subprocess.run(["git", "add", "."], cwd=self.project_root, check=True, encoding='utf-8')
            
            # 提交
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.project_root,
                check=True,
                encoding='utf-8'
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def create_tag(self, tag, message):
        """创建标签"""
        try:
            subprocess.run(
                ["git", "tag", "-a", tag, "-m", message],
                cwd=self.project_root,
                check=True,
                encoding='utf-8'
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def delete_tag(self, tag):
        """删除本地和远程标签"""
        try:
            # 删除本地标签
            subprocess.run(
                ["git", "tag", "-d", tag],
                cwd=self.project_root,
                check=False,  # 如果标签不存在，不要失败
                capture_output=True,
                encoding='utf-8'
            )
            
            # 删除远程标签
            subprocess.run(
                ["git", "push", "origin", f":refs/tags/{tag}"],
                cwd=self.project_root,
                check=False,  # 如果远程标签不存在，不要失败
                capture_output=True,
                encoding='utf-8'
            )
            
            return True
        except subprocess.CalledProcessError:
            return False
    
    def get_existing_tags(self):
        """获取现有的版本标签"""
        try:
            result = subprocess.run(
                ["git", "tag", "-l", "v*"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                tags = result.stdout.strip().split('\n')
                # 过滤空行并移除v前缀，然后按版本号排序
                versions = []
                for tag in tags:
                    if tag.strip() and tag.startswith('v'):
                        version_str = tag[1:]  # 移除v前缀
                        try:
                            # 验证是否为有效版本号
                            version.parse(version_str)
                            versions.append(version_str)
                        except:
                            pass
                
                # 按版本号倒序排列（最新的在前）
                versions.sort(key=lambda x: version.parse(x), reverse=True)
                return versions
            return []
        except:
            return []
    
    def tag_exists(self, tag):
        """检查标签是否存在"""
        try:
            result = subprocess.run(
                ["git", "tag", "-l", tag],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=self.project_root
            )
            return result.returncode == 0 and result.stdout.strip() == tag
        except:
            return False
    
    def push_with_tags(self):
        """推送代码和标签"""
        try:
            subprocess.run(["git", "push", "origin", "master"], cwd=self.project_root, check=True, encoding='utf-8')
            subprocess.run(["git", "push", "origin", "--tags"], cwd=self.project_root, check=True, encoding='utf-8')
            return True
        except subprocess.CalledProcessError:
            return False

class AICommitGenerator:
    """AI提交信息生成器"""
    
    def __init__(self, required=True):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.required = required
        
        if not self.api_key and required:
            console.print("❌ 请设置OPENROUTER_API_KEY环境变量", style="red")
            console.print("💡 获取API密钥: https://openrouter.ai/", style="blue")
            console.print("💡 查看配置指南: scripts/setup_guide.md", style="blue")
            sys.exit(1)
        
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
    
    def generate_commit_message(self, changes, version):
        """生成提交信息"""
        
        # 如果没有API密钥，使用备用方案
        if not self.api_key:
            console.print("⚠️ 未设置API密钥，使用本地生成", style="yellow")
            change_summary = self._analyze_changes(changes)
            return self._fallback_commit_message(version, change_summary)
        
        # 分析更改类型
        change_summary = self._analyze_changes(changes)
        
        prompt = f"""
你是一个专业的Git提交信息生成器。请根据以下文件更改生成一个高质量的提交信息。

项目: ImageCompress - 高性能图像压缩服务
新版本: {version}

文件更改:
{chr(10).join(changes[:20])}  # 限制显示前20个更改

要求:
1. 使用中文
2. 遵循Conventional Commits规范
3. 第一行是简洁的标题(不超过50字符)
4. 如果有多个更改，在标题后添加详细描述
5. 突出版本发布的重要性

格式示例:
feat: 发布v{version}版本

- 新增功能A和功能B
- 修复重要bug C
- 优化性能和用户体验
- 更新文档和配置

请生成提交信息:
"""

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("🤖 AI正在生成提交信息...", total=None)
                
                response = requests.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "anthropic/claude-3.5-sonnet",
                        "messages": [
                            {
                                "role": "user", 
                                "content": prompt
                            }
                        ],
                        "max_tokens": 500,
                        "temperature": 0.7
                    },
                    timeout=30
                )
                
                progress.remove_task(task)
            
            if response.status_code == 200:
                result = response.json()
                commit_message = result['choices'][0]['message']['content'].strip()
                return commit_message
            else:
                console.print(f"❌ AI服务错误: {response.status_code}", style="red")
                return self._fallback_commit_message(version, change_summary)
                
        except Exception as e:
            console.print(f"❌ AI生成失败: {e}", style="yellow")
            return self._fallback_commit_message(version, change_summary)
    
    def _analyze_changes(self, changes):
        """分析更改类型"""
        summary = {
            'added': 0,
            'modified': 0,
            'deleted': 0,
            'renamed': 0,
            'files': []
        }
        
        for change in changes:
            if change.startswith('A '):
                summary['added'] += 1
            elif change.startswith('M '):
                summary['modified'] += 1
            elif change.startswith('D '):
                summary['deleted'] += 1
            elif change.startswith('R '):
                summary['renamed'] += 1
            
            # 提取文件名
            file_path = change[2:].strip()
            summary['files'].append(file_path)
        
        return summary
    
    def _fallback_commit_message(self, version, summary):
        """备用提交信息"""
        return f"""release: 发布v{version}版本

- 修改文件: {summary['modified']}个
- 新增文件: {summary['added']}个  
- 删除文件: {summary['deleted']}个
- 自动版本发布，详见更改历史"""

class ReleaseManager:
    """发布管理器"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.version_manager = VersionManager(self.project_root)
        self.git_manager = GitManager(self.project_root)
        self.ai_generator = AICommitGenerator(required=False)  # 不强制要求API密钥
    
    def run(self):
        """运行发布流程"""
        
        # 显示欢迎信息
        self._show_welcome()
        
        # 检查Git状态
        self._check_git_status()
        
        while True:
            # 选择版本类型
            bump_type = self._select_version_type()
            
            # 生成新版本号
            if bump_type == "override":
                new_version = self._select_override_version()
                if new_version is None:
                    console.print("❌ 版本选择失败", style="red")
                    return
                is_override = True
            else:
                new_version = self.version_manager.bump_version(bump_type)
                is_override = False
            
            # 确认发布
            if is_override:
                # 对于覆盖版本，直接确认
                console.print(f"\n⚠️ [yellow]将覆盖版本 v{new_version}[/yellow]")
                questions = [
                    InquirerList('confirm',
                         message="确认覆盖发布?",
                         choices=['是，覆盖发布', '否，取消发布', '重新选择版本'],
                         default='否，取消发布')
                ]
                answers = prompt(questions)
                
                if answers['confirm'].startswith('是'):
                    break
                elif answers['confirm'].startswith('重新'):
                    continue
                else:
                    console.print("❌ 发布已取消", style="yellow")
                    return
            else:
                confirm_result = self._confirm_release(new_version)
                
                if confirm_result == 'retry':
                    console.print("🔄 [yellow]请重新选择版本号...[/yellow]")
                    continue
                elif confirm_result == 'override':
                    is_override = True
                    break
                elif confirm_result:
                    is_override = False
                    break
                else:
                    console.print("❌ 发布已取消", style="yellow")
                    return
        
        # 显示更改预览
        self._show_changes_preview()
        
        # 生成提交信息
        commit_message = self._generate_commit_message(new_version)
        
        # 执行发布
        self._execute_release(new_version, commit_message, is_override)
    
    def _show_welcome(self):
        """显示欢迎信息"""
        console.print()
        console.print(Panel.fit(
            f"🚀 [bold blue]ImageCompress 自动化版本发布工具[/bold blue]\n\n"
            f"当前版本: [green]{self.version_manager.current_version}[/green]\n"
            f"项目路径: [dim]{self.project_root}[/dim]\n"
            f"AI服务: [green]{'✓' if os.getenv('OPENROUTER_API_KEY') else '✗'}[/green] OpenRouter",
            title="版本发布工具",
            style="blue"
        ))
    
    def _check_git_status(self):
        """检查Git状态"""
        changes = self.git_manager.get_uncommitted_changes()
        
        if not changes:
            console.print("❌ 没有发现未提交的更改", style="red")
            sys.exit(1)
        
        console.print(f"✅ 发现 {len(changes)} 个未提交的更改", style="green")
    
    def _select_version_type(self):
        """选择版本类型"""
        current = self.version_manager.current_version
        
        choices = [
            f"patch (补丁版本): {current} → {self.version_manager.bump_version('patch')}",
            f"minor (小版本): {current} → {self.version_manager.bump_version('minor')}",
            f"major (大版本): {current} → {self.version_manager.bump_version('major')}",
            f"override (覆盖已有版本): 从现有版本中选择"
        ]
        
        questions = [
            InquirerList('version_type',
                 message="选择版本升级类型:",
                 choices=choices,
                 carousel=True)
        ]
        
        answers = prompt(questions)
        return answers['version_type'].split()[0]
    
    def _select_override_version(self):
        """选择要覆盖的版本"""
        existing_versions = self.git_manager.get_existing_tags()
        
        if not existing_versions:
            console.print("❌ 未找到现有的版本标签", style="red")
            return None
        
        console.print(f"\n📋 [bold]发现 {len(existing_versions)} 个现有版本:[/bold]")
        
        # 限制显示数量，避免列表过长
        display_versions = existing_versions[:10]
        choices = [f"v{version}" for version in display_versions]
        
        if len(existing_versions) > 10:
            choices.append("... 查看更多版本")
        
        questions = [
            InquirerList('selected_version',
                 message="选择要覆盖的版本:",
                 choices=choices,
                 carousel=True)
        ]
        
        answers = prompt(questions)
        
        if answers['selected_version'] == "... 查看更多版本":
            # 显示所有版本
            choices = [f"v{version}" for version in existing_versions]
            questions = [
                InquirerList('selected_version',
                     message="选择要覆盖的版本:",
                     choices=choices,
                     carousel=True)
            ]
            answers = prompt(questions)
        
        # 移除v前缀返回版本号
        return answers['selected_version'][1:]
    
    def _confirm_release(self, new_version):
        """确认发布"""
        table = Table(title="发布信息确认")
        table.add_column("项目", style="cyan", no_wrap=True)
        table.add_column("当前版本", style="green")
        table.add_column("新版本", style="red")
        table.add_column("发布时间", style="yellow")
        
        table.add_row(
            "ImageCompress",
            self.version_manager.current_version,
            new_version,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        console.print(table)
        
        # 检查是否是相同版本（覆盖发布）
        tag_name = f"v{new_version}"
        is_override = self.git_manager.tag_exists(tag_name)
        
        if is_override:
            console.print(f"\n⚠️ [yellow]标签 {tag_name} 已存在！[/yellow]")
            
            choices = [
                '是，覆盖发布（删除现有标签后重新发布）',
                '否，取消发布',
                '选择不同的版本号'
            ]
            
            questions = [
                InquirerList('confirm',
                     message="检测到版本标签已存在，如何处理?",
                     choices=choices,
                     default='否，取消发布')
            ]
            
            answers = prompt(questions)
            
            if answers['confirm'].startswith('是'):
                return 'override'
            elif answers['confirm'].startswith('选择'):
                return 'retry'
            else:
                return False
        else:
            questions = [
                InquirerList('confirm',
                     message="确认发布?",
                     choices=['是，继续发布', '否，取消发布'],
                     default='是，继续发布')
            ]
            
            answers = prompt(questions)
            return answers['confirm'].startswith('是')
    
    def _show_changes_preview(self):
        """显示更改预览"""
        changes = self.git_manager.get_uncommitted_changes()
        
        console.print("\n📋 [bold]文件更改预览:[/bold]")
        
        # 限制显示数量
        display_changes = changes[:15]
        for change in display_changes:
            status = change[:2]
            file_path = change[2:].strip()
            
            if status.strip() == 'M':
                console.print(f"  [yellow]📝 修改[/yellow] {file_path}")
            elif status.strip() == 'A':
                console.print(f"  [green]➕ 新增[/green] {file_path}")
            elif status.strip() == 'D':
                console.print(f"  [red]🗑️  删除[/red] {file_path}")
            else:
                console.print(f"  [dim]🔄 其他[/dim] {file_path}")
        
        if len(changes) > 15:
            console.print(f"  [dim]... 还有 {len(changes) - 15} 个文件未显示[/dim]")
    
    def _generate_commit_message(self, new_version):
        """生成提交信息"""
        changes = self.git_manager.get_uncommitted_changes()
        
        console.print("\n🤖 [bold]生成提交信息...[/bold]")
        
        commit_message = self.ai_generator.generate_commit_message(changes, new_version)
        
        # 显示生成的提交信息
        console.print("\n📝 [bold]生成的提交信息:[/bold]")
        syntax = Syntax(commit_message, "text", theme="monokai", line_numbers=False)
        console.print(Panel(syntax, title="提交信息预览", expand=False))
        
        # 允许用户编辑
        questions = [
            InquirerList('edit_commit',
                 message="是否编辑提交信息?",
                 choices=['使用生成的信息', '手动编辑'],
                 default='使用生成的信息')
        ]
        
        answers = prompt(questions)
        
        if answers['edit_commit'] == '手动编辑':
            questions = [
                Text('custom_message',
                     message="请输入提交信息:",
                     default=commit_message)
            ]
            answers = prompt(questions)
            return answers['custom_message']
        
        return commit_message
    
    def _execute_release(self, new_version, commit_message, is_override=False):
        """执行发布"""
        console.print("\n🚀 [bold]开始执行发布...[/bold]")
        
        tag_name = f"v{new_version}"
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            # 如果是覆盖发布，先删除现有标签
            if is_override:
                task_delete = progress.add_task("🗑️ 删除现有标签...", total=None)
                if self.git_manager.delete_tag(tag_name):
                    console.print(f"✅ 已删除本地和远程标签: {tag_name}", style="green")
                else:
                    console.print(f"⚠️ 删除标签时遇到问题，继续执行", style="yellow")
                progress.remove_task(task_delete)
            
            # 更新 Cargo.toml 版本号
            task0 = progress.add_task("📝 更新 Cargo.toml 版本号...", total=None)
            self.version_manager.update_cargo_version(new_version)
            progress.remove_task(task0)
            
            # 提交更改
            task1 = progress.add_task("📝 提交代码更改...", total=None)
            if not self.git_manager.commit_changes(commit_message):
                console.print("❌ 代码提交失败", style="red")
                sys.exit(1)
            progress.remove_task(task1)
            
            # 创建标签
            task2 = progress.add_task("🏷️  创建版本标签...", total=None)
            tag_message = f"Release version {new_version}"
            if not self.git_manager.create_tag(tag_name, tag_message):
                console.print("❌ 标签创建失败", style="red")
                sys.exit(1)
            progress.remove_task(task2)
            
            # 推送到远程
            task3 = progress.add_task("⬆️  推送到远程仓库...", total=None)
            if not self.git_manager.push_with_tags():
                console.print("❌ 推送失败", style="red")
                sys.exit(1)
            progress.remove_task(task3)
        
        # 显示成功信息
        override_text = " (覆盖发布)" if is_override else ""
        console.print()
        console.print(Panel.fit(
            f"🎉 [bold green]版本 v{new_version}{override_text} 发布成功![/bold green]\n\n"
            f"✅ Cargo.toml 版本已更新\n"
            f"✅ 代码已提交\n"
            f"✅ 标签已创建: {tag_name}{override_text}\n"
            f"✅ 已推送到远程仓库\n\n"
            f"🔗 GitHub Actions将自动构建和发布Docker镜像",
            title="发布完成",
            style="green"
        ))

@click.command()
@click.option('--dry-run', is_flag=True, help='预览模式，不执行实际操作')
def main(dry_run):
    """ImageCompress 自动化版本发布工具"""
    
    if dry_run:
        console.print("🔍 [yellow]预览模式，将不执行实际的Git操作[/yellow]")
    
    try:
        release_manager = ReleaseManager()
        release_manager.run()
    except KeyboardInterrupt:
        console.print("\n❌ 用户取消操作", style="yellow")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n❌ 发布失败: {e}", style="red")
        sys.exit(1)

if __name__ == "__main__":
    main()
