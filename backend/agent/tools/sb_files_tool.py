from daytona_sdk.process import SessionExecuteRequest
from typing import Optional

from agentpress.tool import ToolResult, openapi_schema, xml_schema
from sandbox.sandbox import SandboxToolsBase, Sandbox, get_or_start_sandbox
from utils.files_utils import EXCLUDED_FILES, EXCLUDED_DIRS, EXCLUDED_EXT, should_exclude_file, clean_path
from agentpress.thread_manager import ThreadManager
from utils.logger import logger
import os

class SandboxFilesTool(SandboxToolsBase):
    """Tool for executing file system operations in a Daytona sandbox. All operations are performed relative to the /workspace directory."""

    def __init__(self, project_id: str, thread_manager: ThreadManager):
        super().__init__(project_id, thread_manager)
        self.SNIPPET_LINES = 4  # Number of context lines to show around edits
        self.workspace_path = "/workspace"  # Ensure we're always operating in /workspace

    def clean_path(self, path: str) -> str:
        """Clean and normalize a path to be relative to /workspace"""
        return clean_path(path, self.workspace_path)

    def _should_exclude_file(self, rel_path: str) -> bool:
        """Check if a file should be excluded based on path, name, or extension"""
        return should_exclude_file(rel_path)

    def _file_exists(self, path: str) -> bool:
        """Check if a file exists in the sandbox"""
        try:
            self.sandbox.fs.get_file_info(path)
            return True
        except Exception:
            return False

    async def get_workspace_state(self) -> dict:
        """Get the current workspace state by reading all files"""
        files_state = {}
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            files = self.sandbox.fs.list_files(self.workspace_path)
            for file_info in files:
                rel_path = file_info.name
                
                # Skip excluded files and directories
                if self._should_exclude_file(rel_path) or file_info.is_dir:
                    continue

                try:
                    full_path = f"{self.workspace_path}/{rel_path}"
                    content = self.sandbox.fs.download_file(full_path).decode()
                    files_state[rel_path] = {
                        "content": content,
                        "is_dir": file_info.is_dir,
                        "size": file_info.size,
                        "modified": file_info.mod_time
                    }
                except Exception as e:
                    print(f"Error reading file {rel_path}: {e}")
                except UnicodeDecodeError:
                    print(f"Skipping binary file: {rel_path}")

            return files_state
        
        except Exception as e:
            print(f"Error getting workspace state: {str(e)}")
            return {}


    # def _get_preview_url(self, file_path: str) -> Optional[str]:
    #     """Get the preview URL for a file if it's an HTML file."""
    #     if file_path.lower().endswith('.html') and self._sandbox_url:
    #         return f"{self._sandbox_url}/{(file_path.replace('/workspace/', ''))}"
    #     return None

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file with the provided contents at a given path in the workspace. The path must be relative to /workspace (e.g., 'src/main.py' for /workspace/src/main.py)",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to be created, relative to /workspace (e.g., 'src/main.py')"
                    },
                    "file_contents": {
                        "type": "string",
                        "description": "The content to write to the file"
                    },
                    "permissions": {
                        "type": "string",
                        "description": "File permissions in octal format (e.g., '644')",
                        "default": "644"
                    }
                },
                "required": ["file_path", "file_contents"]
            }
        }
    })
    @xml_schema(
        tag_name="create-file",
        mappings=[
            {"param_name": "file_path", "node_type": "attribute", "path": "."},
            {"param_name": "file_contents", "node_type": "content", "path": "."}
        ],
        example='''
        <create-file file_path="src/main.py">
        File contents go here
        </create-file>
        '''
    )
    async def create_file(self, file_path: str, file_contents: str, permissions: str = "644") -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            file_path = self.clean_path(file_path)
            full_path = f"{self.workspace_path}/{file_path}"
            if self._file_exists(full_path):
                return self.fail_response(f"File '{file_path}' already exists. Use update_file to modify existing files.")
            
            # Create parent directories if needed
            parent_dir = '/'.join(full_path.split('/')[:-1])
            if parent_dir:
                self.sandbox.fs.create_folder(parent_dir, "755")
            
            # Write the file content
            self.sandbox.fs.upload_file(full_path, file_contents.encode())
            self.sandbox.fs.set_file_permissions(full_path, permissions)
            
            # Get preview URL if it's an HTML file
            # preview_url = self._get_preview_url(file_path)
            message = f"File '{file_path}' created successfully."
            # if preview_url:
            #     message += f"\n\nYou can preview this HTML file at the automatically served HTTP server: {preview_url}"
            
            return self.success_response(message)
        except Exception as e:
            return self.fail_response(f"Error creating file: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "str_replace",
            "description": "Replace specific text in a file. The file path must be relative to /workspace (e.g., 'src/main.py' for /workspace/src/main.py). Use this when you need to replace a unique string that appears exactly once in the file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the target file, relative to /workspace (e.g., 'src/main.py')"
                    },
                    "old_str": {
                        "type": "string",
                        "description": "Text to be replaced (must appear exactly once)"
                    },
                    "new_str": {
                        "type": "string",
                        "description": "Replacement text"
                    }
                },
                "required": ["file_path", "old_str", "new_str"]
            }
        }
    })
    @xml_schema(
        tag_name="str-replace",
        mappings=[
            {"param_name": "file_path", "node_type": "attribute", "path": "."},
            {"param_name": "old_str", "node_type": "element", "path": "old_str"},
            {"param_name": "new_str", "node_type": "element", "path": "new_str"}
        ],
        example='''
        <str-replace file_path="src/main.py">
            <old_str>text to replace (must appear exactly once in the file)</old_str>
            <new_str>replacement text that will be inserted instead</new_str>
        </str-replace>
        '''
    )
    async def str_replace(self, file_path: str, old_str: str, new_str: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            file_path = self.clean_path(file_path)
            full_path = f"{self.workspace_path}/{file_path}"
            if not self._file_exists(full_path):
                return self.fail_response(f"File '{file_path}' does not exist")
            
            content = self.sandbox.fs.download_file(full_path).decode()
            old_str = old_str.expandtabs()
            new_str = new_str.expandtabs()
            
            occurrences = content.count(old_str)
            if occurrences == 0:
                return self.fail_response(f"String '{old_str}' not found in file")
            if occurrences > 1:
                lines = [i+1 for i, line in enumerate(content.split('\n')) if old_str in line]
                return self.fail_response(f"Multiple occurrences found in lines {lines}. Please ensure string is unique")
            
            # Perform replacement
            new_content = content.replace(old_str, new_str)
            self.sandbox.fs.upload_file(full_path, new_content.encode())
            
            # Show snippet around the edit
            replacement_line = content.split(old_str)[0].count('\n')
            start_line = max(0, replacement_line - self.SNIPPET_LINES)
            end_line = replacement_line + self.SNIPPET_LINES + new_str.count('\n')
            snippet = '\n'.join(new_content.split('\n')[start_line:end_line + 1])
            
            # Get preview URL if it's an HTML file
            # preview_url = self._get_preview_url(file_path)
            message = f"Replacement successful."
            # if preview_url:
            #     message += f"\n\nYou can preview this HTML file at: {preview_url}"
            
            return self.success_response(message)
            
        except Exception as e:
            return self.fail_response(f"Error replacing string: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "full_file_rewrite",
            "description": "Completely rewrite an existing file with new content. The file path must be relative to /workspace (e.g., 'src/main.py' for /workspace/src/main.py). Use this when you need to replace the entire file content or make extensive changes throughout the file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to be rewritten, relative to /workspace (e.g., 'src/main.py')"
                    },
                    "file_contents": {
                        "type": "string",
                        "description": "The new content to write to the file, replacing all existing content"
                    },
                    "permissions": {
                        "type": "string",
                        "description": "File permissions in octal format (e.g., '644')",
                        "default": "644"
                    }
                },
                "required": ["file_path", "file_contents"]
            }
        }
    })
    @xml_schema(
        tag_name="full-file-rewrite",
        mappings=[
            {"param_name": "file_path", "node_type": "attribute", "path": "."},
            {"param_name": "file_contents", "node_type": "content", "path": "."}
        ],
        example='''
        <full-file-rewrite file_path="src/main.py">
        This completely replaces the entire file content.
        Use when making major changes to a file or when the changes
        are too extensive for str-replace.
        All previous content will be lost and replaced with this text.
        </full-file-rewrite>
        '''
    )
    async def full_file_rewrite(self, file_path: str, file_contents: str, permissions: str = "644") -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            file_path = self.clean_path(file_path)
            full_path = f"{self.workspace_path}/{file_path}"
            if not self._file_exists(full_path):
                return self.fail_response(f"File '{file_path}' does not exist. Use create_file to create a new file.")
            
            self.sandbox.fs.upload_file(full_path, file_contents.encode())
            self.sandbox.fs.set_file_permissions(full_path, permissions)
            
            # Get preview URL if it's an HTML file
            # preview_url = self._get_preview_url(file_path)
            message = f"File '{file_path}' completely rewritten successfully."
            # if preview_url:
            #     message += f"\n\nYou can preview this HTML file at: {preview_url}"
            
            return self.success_response(message)
        except Exception as e:
            return self.fail_response(f"Error rewriting file: {str(e)}")

    @openapi_schema({
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file at the given path. The path must be relative to /workspace (e.g., 'src/main.py' for /workspace/src/main.py)",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to be deleted, relative to /workspace (e.g., 'src/main.py')"
                    }
                },
                "required": ["file_path"]
            }
        }
    })
    @xml_schema(
        tag_name="delete-file",
        mappings=[
            {"param_name": "file_path", "node_type": "attribute", "path": "."}
        ],
        example='''
        <delete-file file_path="src/main.py">
        </delete-file>
        '''
    )
    async def delete_file(self, file_path: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            file_path = self.clean_path(file_path)
            full_path = f"{self.workspace_path}/{file_path}"
            if not self._file_exists(full_path):
                return self.fail_response(f"File '{file_path}' does not exist")
            
            self.sandbox.fs.delete_file(full_path)
            return self.success_response(f"File '{file_path}' deleted successfully.")
        except Exception as e:
            return self.fail_response(f"Error deleting file: {str(e)}")
        
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder at the given path. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Path to the folder to be created, relative to /workspace (e.g., 'src')"
                    }
                },
                "required": ["folder_path"]
            }
        }
    })
    @xml_schema(
        tag_name="create-folder",
        mappings=[
            {"param_name": "folder_path", "node_type": "attribute", "path": "."}
        ],
        example='''
        <create-folder folder_path="src">
        '''
    )
    async def create_folder(self, folder_path: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            folder_path = self.clean_path(folder_path)
            full_path = f"{self.workspace_path}/{folder_path}"
            if self._file_exists(full_path):
                return self.fail_response(f"Folder '{folder_path}' already exists")
            
            self.sandbox.fs.create_folder(full_path)
            return self.success_response(f"Folder '{folder_path}' created successfully.")
        except Exception as e:
            return self.fail_response(f"Error creating folder: {str(e)}")
    
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "delete_folder",
            "description": "Delete a folder at the given path. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_path": {
                        "type": "string",
                        "description": "Path to the folder to be deleted, relative to /workspace (e.g., 'src')"
                    }
                },
                "required": ["folder_path"]
            }
        }
    })
    @xml_schema(
        tag_name="delete-folder",
        mappings=[
            {"param_name": "folder_path", "node_type": "attribute", "path": "."}
        ],
        example='''
        <delete-folder folder_path="src">
        '''
    )
    async def delete_folder(self, folder_path: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()

            folder_path = self.clean_path(folder_path)
            full_path = f"{self.workspace_path}/{folder_path}"
            if not self._file_exists(full_path):
                return self.fail_response(f"Folder '{folder_path}' does not exist")
            
            self.sandbox.fs.delete_folder(full_path)
            return self.success_response(f"Folder '{folder_path}' deleted successfully.")
        except Exception as e:
            return self.fail_response(f"Error deleting folder: {str(e)}")
        
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files and folders in the given path. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to list, relative to /workspace (e.g., 'src')"
                    }
                },
                "required": ["path"]
            }   
        }
    })
    @xml_schema(
        tag_name="list-files",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."}
        ],
        example='''
        <list-files path="src">
        '''
    )
    async def list_files(self, path: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            path = self.clean_path(path)
            full_path = f"{self.workspace_path}/{path}"
            if not self._file_exists(full_path):
                return self.fail_response(f"Path '{path}' does not exist")
            
            files = self.sandbox.fs.list_files(full_path)
            return self.success_response(f"Files in '{path}': {files}")
        except Exception as e:
            return self.fail_response(f"Error listing files: {str(e)}")
        
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "clone_git_repo",
            "description": "Clone a Git repository into the workspace. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {
                        "type": "string",
                        "description": "URL of the Git repository to clone"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to clone the repository to, relative to /workspace (e.g., 'src')"
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch to clone (default: main)",
                        "default": "main"
                    }
                },
                "required": ["repo_url", "path"]
            }
        }
    })
    @xml_schema(
        tag_name="clone-git-repo",
        mappings=[
            {"param_name": "repo_url", "node_type": "attribute", "path": "."},
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "branch", "node_type": "attribute", "path": "."}
        ],
        example='''
        <clone-git-repo repo_url="https://github.com/user/repo.git">
        <path>src</path>
        <branch>main</branch>
        </clone-git-repo>
        '''
    )
    async def clone_git_repo(self, repo_url: str, path: str, branch: str = "main") -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            # Clone the repository
            self.sandbox.git.clone_repository(repo_url, path, branch)
            return self.success_response(f"Repository cloned successfully.")
        except Exception as e:
            return self.fail_response(f"Error cloning repository: {str(e)}")
    
    # clone with auth
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "clone_git_repo_with_auth",
            "description": "Clone a Git repository into the workspace with authentication. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {
                        "type": "string",
                        "description": "URL of the Git repository to clone"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to clone the repository to, relative to /workspace (e.g., 'src')"
                    },
                    "auth_token": {
                        "type": "string",
                        "description": "Authentication token for the repository"
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch to clone (default: main)",
                        "default": "main"
                    }
                },
                "required": ["repo_url", "path", "auth_token"]
            }
        }
    })
    @xml_schema(
        tag_name="clone-git-repo-with-auth",
        mappings=[
            {"param_name": "repo_url", "node_type": "attribute", "path": "."},
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "auth_token", "node_type": "attribute", "path": "."},
            {"param_name": "branch", "node_type": "attribute", "path": "."}
        ],
        example='''
        <clone-git-repo-with-auth repo_url="https://github.com/user/repo.git">
        <path>src</path>
        <auth_token>your_auth_token</auth_token>
        <branch>main</branch>
        </clone-git-repo-with-auth>
        '''
    )
    async def clone_git_repo_with_auth(self, repo_url: str, path: str, auth_token: str, branch: str = "main") -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            # Clone the repository with authentication
            self.sandbox.git.clone_repository(repo_url, path, auth_token, branch)
            return self.success_response(f"Repository cloned successfully.")
        except Exception as e:
            return self.fail_response(f"Error cloning repository: {str(e)}")
        
    # get repo status
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "get_repo_status",
            "description": "Get the status of a Git repository. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to get the status of, relative to /workspace (e.g., 'src')"
                    }
                },
                "required": ["path"]
            }
        }
    })
    @xml_schema(
        tag_name="get-repo-status",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."}
        ],
        example='''
        <get-repo-status path="src">
        '''
    )
    async def get_repo_status(self, path: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            # Get the status of the repository
            status = self.sandbox.git.get_repository_status(path)
            return self.success_response(f"Repository status: {status}")
        except Exception as e:
            return self.fail_response(f"Error getting repository status: {str(e)}")
    
    # add file to repo
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "add_file_to_repo",
            "description": "Add a file to a Git repository. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to add the file to, relative to /workspace (e.g., 'src')"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to add, relative to /workspace (e.g., 'src/main.py' for /workspace/src/main.py)"
                    }
                },
                "required": ["path", "file_path"]
            }
        }
    })
    @xml_schema(
        tag_name="add-file-to-repo",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "file_path", "node_type": "attribute", "path": "."}
        ],
        example='''
        <add-file-to-repo path="src">
        <file_path>src/main.py</file_path>
        </add-file-to-repo>
        '''
    )
    async def add_file_to_repo(self, path: str, file_path: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            # Add the file to the repository
            self.sandbox.git.add_file(path, file_path)
            return self.success_response(f"File added to repository successfully.")
        except Exception as e:
            return self.fail_response(f"Error adding file to repository: {str(e)}")
        
    # create branch
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "create_branch",
            "description": "Create a new branch in a Git repository. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to create the branch in, relative to /workspace (e.g., 'src')"
                    },
                    "branch_name": {
                        "type": "string",
                        "description": "Name of the new branch to create"
                    }
                },
                "required": ["path", "branch_name"]
            }
        }
    })
    @xml_schema(
        tag_name="create-branch",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "branch_name", "node_type": "attribute", "path": "."}
        ],
        example='''
        <create-branch path="src">
        <branch_name>new_branch</branch_name>
        </create-branch>
        '''
    )
    async def create_branch(self, path: str, branch_name: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()
            
            # Create the branch
            self.sandbox.git.create_branch(path, branch_name)
            return self.success_response(f"Branch '{branch_name}' created successfully.")
        except Exception as e:
            return self.fail_response(f"Error creating branch: {str(e)}")
        
    # checkout branch
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "checkout_branch",
            "description": "Checkout a branch in a Git repository. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to checkout the branch in, relative to /workspace (e.g., 'src')"
                    },
                    "branch_name": {
                        "type": "string",
                        "description": "Name of the branch to checkout"
                    }
                },
                "required": ["path", "branch_name"]
            }
        }
    })
    @xml_schema(
        tag_name="checkout-branch",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "branch_name", "node_type": "attribute", "path": "."}
        ],
        example='''
        <checkout-branch path="src">
        <branch_name>new_branch</branch_name>
        </checkout-branch>
        '''
    )
    async def checkout_branch(self, path: str, branch_name: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()

            # Checkout the branch
            self.sandbox.git.checkout_branch(path, branch_name)
            return self.success_response(f"Branch '{branch_name}' checked out successfully.")
        except Exception as e:
            return self.fail_response(f"Error checking out branch: {str(e)}")
        
    # commit
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "commit",
            "description": "Commit changes to a Git repository. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to commit in, relative to /workspace (e.g., 'src')"
                    },
                    "message": {
                        "type": "string",
                        "description": "Commit message"
                    }
                },
                "required": ["path", "message"]
            }
        }
    })
    @xml_schema(
        tag_name="commit",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "message", "node_type": "attribute", "path": "."}
        ],
        example='''
        <commit path="src">
        <message>Commit message</message>
        </commit>
        '''
    )
    async def commit(self, path: str, message: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()

            # Commit the changes
            self.sandbox.git.commit(path, message)
            return self.success_response(f"Changes committed successfully.")
        except Exception as e:
            return self.fail_response(f"Error committing changes: {str(e)}")
        
    # push
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "push",
            "description": "Push changes to a Git repository. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to push in, relative to /workspace (e.g., 'src')"
                    },
                    "branch_name": {
                        "type": "string",
                        "description": "Name of the branch to push"
                    }
                },
                "required": ["path", "branch_name"]
            }
        }
    })
    @xml_schema(
        tag_name="push",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "branch_name", "node_type": "attribute", "path": "."}
        ],
        example='''
        <push path="src">
        <branch_name>main</branch_name>
        </push>
        '''
    )
    async def push(self, path: str, branch_name: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()

            # Push the changes
            self.sandbox.git.push(path, branch_name)
            return self.success_response(f"Changes pushed successfully.")
        except Exception as e:
            return self.fail_response(f"Error pushing changes: {str(e)}")
        
    # pull
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "pull",
            "description": "Pull changes from a Git repository. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to pull in, relative to /workspace (e.g., 'src')"
                    },
                    "branch_name": {
                        "type": "string",
                        "description": "Name of the branch to pull"
                    }
                },
                "required": ["path", "branch_name"]
            }
        }
    })
    @xml_schema(
        tag_name="pull",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "branch_name", "node_type": "attribute", "path": "."}
        ],
        example='''
        <pull path="src">
        <branch_name>main</branch_name>
        </pull>
        '''
    )
    async def pull(self, path: str, branch_name: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()

            # Pull the changes
            self.sandbox.git.pull(path, branch_name)
            return self.success_response(f"Changes pulled successfully.")
        except Exception as e:
            return self.fail_response(f"Error pulling changes: {str(e)}")
        
    # merge
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "merge",
            "description": "Merge a branch into the current branch. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to merge in, relative to /workspace (e.g., 'src')"
                    },
                        "branch_name": {
                        "type": "string",
                        "description": "Name of the branch to merge"
                    }
                },
                "required": ["path", "branch_name"]
            }
        }
    })
    @xml_schema(
        tag_name="merge",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "branch_name", "node_type": "attribute", "path": "."}
        ],
        example='''
        <merge path="src">
        <branch_name>main</branch_name>
        </merge>
        '''
    )
    async def merge(self, path: str, branch_name: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()

            # Merge the branch
            self.sandbox.git.merge(path, branch_name)
            return self.success_response(f"Branch '{branch_name}' merged successfully.")
        except Exception as e:
            return self.fail_response(f"Error merging branch: {str(e)}")
        
    # fetch
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "fetch",
            "description": "Fetch changes from a Git repository. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to fetch in, relative to /workspace (e.g., 'src')"
                    }
                },
                "required": ["path"]
            }
        }
    })
    @xml_schema(
        tag_name="fetch",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."}
        ],
        example='''
        <fetch path="src">
        </fetch>
        '''
    )
    async def fetch(self, path: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()

            # Fetch the changes
            self.sandbox.git.fetch(path)
            return self.success_response(f"Changes fetched successfully.")
        except Exception as e:
            return self.fail_response(f"Error fetching changes: {str(e)}")
        
    # add
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add changes to a Git repository. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to add in, relative to /workspace (e.g., 'src')"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to add, relative to /workspace (e.g., 'src/main.py')"
                    }
                },
                "required": ["path", "file_path"]
            }
        }
    })
    @xml_schema(
        tag_name="add",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "file_path", "node_type": "attribute", "path": "."}
        ],
        example='''
        <add path="src">
        <file_path>src/main.py</file_path>
        </add>
        '''
    )
    async def add(self, path: str, file_path: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()

            # Add the file to the repository
            self.sandbox.git.add(path, file_path)
            return self.success_response(f"File added to repository successfully.")
        except Exception as e:
            return self.fail_response(f"Error adding file to repository: {str(e)}")
        
    # checkout
    @openapi_schema({
        "type": "function",
        "function": {
            "name": "checkout",
            "description": "Checkout a branch in a Git repository. The path must be relative to /workspace (e.g., 'src' for /workspace/src)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the repository to checkout in, relative to /workspace (e.g., 'src')"
                    },
                    "branch_name": {
                        "type": "string",
                        "description": "Name of the branch to checkout"
                    }
                },
                "required": ["path", "branch_name"]
            }
        }
    })
    @xml_schema(
        tag_name="checkout",
        mappings=[
            {"param_name": "path", "node_type": "attribute", "path": "."},
            {"param_name": "branch_name", "node_type": "attribute", "path": "."}
        ],
        example='''
        <checkout path="src">
        <branch_name>main</branch_name>
        </checkout>
        '''
    )
    async def checkout(self, path: str, branch_name: str) -> ToolResult:
        try:
            # Ensure sandbox is initialized
            await self._ensure_sandbox()

            # Checkout the branch
            self.sandbox.git.checkout(path, branch_name)
            return self.success_response(f"Branch '{branch_name}' checked out successfully.")
        except Exception as e:
            return self.fail_response(f"Error checking out branch: {str(e)}")
        
    
    # @openapi_schema({
    #     "type": "function",
    #     "function": {
    #         "name": "read_file",
    #         "description": "Read and return the contents of a file. This tool is essential for verifying data, checking file contents, and analyzing information. Always use this tool to read file contents before processing or analyzing data. The file path must be relative to /workspace.",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "file_path": {
    #                     "type": "string",
    #                     "description": "Path to the file to read, relative to /workspace (e.g., 'src/main.py' for /workspace/src/main.py). Must be a valid file path within the workspace."
    #                 },
    #                 "start_line": {
    #                     "type": "integer",
    #                     "description": "Optional starting line number (1-based). Use this to read specific sections of large files. If not specified, reads from the beginning of the file.",
    #                     "default": 1
    #                 },
    #                 "end_line": {
    #                     "type": "integer",
    #                     "description": "Optional ending line number (inclusive). Use this to read specific sections of large files. If not specified, reads to the end of the file.",
    #                     "default": None
    #                 }
    #             },
    #             "required": ["file_path"]
    #         }
    #     }
    # })
    # @xml_schema(
    #     tag_name="read-file",
    #     mappings=[
    #         {"param_name": "file_path", "node_type": "attribute", "path": "."},
    #         {"param_name": "start_line", "node_type": "attribute", "path": ".", "required": False},
    #         {"param_name": "end_line", "node_type": "attribute", "path": ".", "required": False}
    #     ],
    #     example='''
    #     <!-- Example 1: Read entire file -->
    #     <read-file file_path="src/main.py">
    #     </read-file>

    #     <!-- Example 2: Read specific lines (lines 10-20) -->
    #     <read-file file_path="src/main.py" start_line="10" end_line="20">
    #     </read-file>

    #     <!-- Example 3: Read from line 5 to end -->
    #     <read-file file_path="config.json" start_line="5">
    #     </read-file>

    #     <!-- Example 4: Read last 10 lines -->
    #     <read-file file_path="logs/app.log" start_line="-10">
    #     </read-file>
    #     '''
    # )
    # async def read_file(self, file_path: str, start_line: int = 1, end_line: Optional[int] = None) -> ToolResult:
    #     """Read file content with optional line range specification.
        
    #     Args:
    #         file_path: Path to the file relative to /workspace
    #         start_line: Starting line number (1-based), defaults to 1
    #         end_line: Ending line number (inclusive), defaults to None (end of file)
            
    #     Returns:
    #         ToolResult containing:
    #         - Success: File content and metadata
    #         - Failure: Error message if file doesn't exist or is binary
    #     """
    #     try:
    #         file_path = self.clean_path(file_path)
    #         full_path = f"{self.workspace_path}/{file_path}"
            
    #         if not self._file_exists(full_path):
    #             return self.fail_response(f"File '{file_path}' does not exist")
            
    #         # Download and decode file content
    #         content = self.sandbox.fs.download_file(full_path).decode()
            
    #         # Split content into lines
    #         lines = content.split('\n')
    #         total_lines = len(lines)
            
    #         # Handle line range if specified
    #         if start_line > 1 or end_line is not None:
    #             # Convert to 0-based indices
    #             start_idx = max(0, start_line - 1)
    #             end_idx = end_line if end_line is not None else total_lines
    #             end_idx = min(end_idx, total_lines)  # Ensure we don't exceed file length
                
    #             # Extract the requested lines
    #             content = '\n'.join(lines[start_idx:end_idx])
            
    #         return self.success_response({
    #             "content": content,
    #             "file_path": file_path,
    #             "start_line": start_line,
    #             "end_line": end_line if end_line is not None else total_lines,
    #             "total_lines": total_lines
    #         })
            
    #     except UnicodeDecodeError:
    #         return self.fail_response(f"File '{file_path}' appears to be binary and cannot be read as text")
    #     except Exception as e:
    #         return self.fail_response(f"Error reading file: {str(e)}")

