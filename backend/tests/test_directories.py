"""
iFlow 对话网页应用 - 目录列表路由测试

测试目录树结构 API
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.database import get_db, Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from backend.models.user import User
from backend.services.auth import create_access_token, hash_password
from backend.routers.directories import WORKSPACE_ROOT, get_directory_tree


# ==================== Fixtures ====================

@pytest.fixture(scope="function")
async def db_session():
    """创建测试数据库会话（使用内存数据库）"""
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    
    # 创建表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 创建会话
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with test_session_maker() as session:
        yield session
    
    # 清理
    await test_engine.dispose()


@pytest.fixture(scope="function")
async def client(db_session):
    """创建测试客户端"""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session):
    """创建测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """生成认证头"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def temp_workspace():
    """创建临时工作目录"""
    temp_dir = tempfile.mkdtemp()
    
    # 创建测试目录结构
    os.makedirs(os.path.join(temp_dir, "project1", "src"))
    os.makedirs(os.path.join(temp_dir, "project1", "tests"))
    os.makedirs(os.path.join(temp_dir, "project2"))
    os.makedirs(os.path.join(temp_dir, "empty_dir"))
    
    # 创建一些文件（应该被忽略）
    with open(os.path.join(temp_dir, "project1", "README.md"), "w") as f:
        f.write("test")
    
    # 创建隐藏目录（应该被忽略）
    os.makedirs(os.path.join(temp_dir, ".hidden"))
    
    yield temp_dir
    
    # 清理
    shutil.rmtree(temp_dir, ignore_errors=True)


# ==================== 获取目录列表测试 ====================

@pytest.mark.asyncio
async def test_get_directories_success(client, test_user):
    """测试获取目录列表成功"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        "/api/directories/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "directories" in data
    assert data["root_path"] == WORKSPACE_ROOT
    assert isinstance(data["directories"], list)


@pytest.mark.asyncio
async def test_get_directories_unauthorized(client):
    """测试未认证获取目录列表"""
    response = await client.get("/api/directories/")
    
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_directory_tree_structure(temp_workspace):
    """测试目录树结构正确性"""
    # 使用临时目录测试
    directories = get_directory_tree(temp_workspace)
    
    # 验证结构
    assert len(directories) == 3  # project1, project2, empty_dir
    
    # 验证隐藏目录被忽略
    dir_names = [d.name for d in directories]
    assert ".hidden" not in dir_names
    
    # 验证 project1 有子目录
    project1 = next((d for d in directories if d.name == "project1"), None)
    assert project1 is not None
    assert project1.children is not None
    assert len(project1.children) == 2  # src, tests
    
    # 验证空目录
    empty_dir = next((d for d in directories if d.name == "empty_dir"), None)
    assert empty_dir is not None
    assert empty_dir.children is None or len(empty_dir.children) == 0


@pytest.mark.asyncio
async def test_get_directory_tree_max_depth(temp_workspace):
    """测试目录树递归深度限制"""
    # 创建深层目录
    deep_path = temp_workspace
    for i in range(5):
        deep_path = os.path.join(deep_path, f"level{i}")
        os.makedirs(deep_path)
    
    # 测试默认深度（3层）
    directories = get_directory_tree(temp_workspace, max_depth=3)
    
    # 验证不会无限递归
    def count_depth(nodes, current=0):
        if not nodes:
            return current
        max_child_depth = current
        for node in nodes:
            if node.children:
                child_depth = count_depth(node.children, current + 1)
                max_child_depth = max(max_child_depth, child_depth)
        return max_child_depth
    
    depth = count_depth(directories)
    assert depth <= 3


@pytest.mark.asyncio
async def test_get_directory_tree_hidden_dirs_ignored(temp_workspace):
    """测试隐藏目录被正确忽略"""
    # 创建更多隐藏目录
    os.makedirs(os.path.join(temp_workspace, ".git"))
    os.makedirs(os.path.join(temp_workspace, ".venv"))
    os.makedirs(os.path.join(temp_workspace, "project1", ".hidden_subdir"))
    
    directories = get_directory_tree(temp_workspace)
    
    # 验证所有隐藏目录都被忽略
    def check_no_hidden(nodes):
        for node in nodes:
            assert not node.name.startswith('.')
            if node.children:
                check_no_hidden(node.children)
    
    check_no_hidden(directories)


@pytest.mark.asyncio
async def test_get_subdirectories_success(client, test_user, temp_workspace):
    """测试获取子目录成功"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    # 使用临时目录路径
    with patch('backend.routers.directories.WORKSPACE_ROOT', temp_workspace):
        response = await client.get(
            f"/api/directories/subdirectory?path={temp_workspace}/project1",
            headers={"Authorization": f"Bearer {token}"}
        )
    
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["directories"]) == 2  # src, tests


@pytest.mark.asyncio
async def test_get_subdirectories_outside_workspace(client, test_user):
    """测试获取工作目录外的子目录被拒绝"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        "/api/directories/subdirectory?path=/etc",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert "工作目录范围内" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_subdirectories_not_found(client, test_user):
    """测试获取不存在的子目录"""
    token = create_access_token({"sub": test_user.id, "username": test_user.username})
    
    response = await client.get(
        f"/api/directories/subdirectory?path={WORKSPACE_ROOT}/nonexistent_dir",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404


# ==================== DirectoryNode 模型测试 ====================

@pytest.mark.asyncio
async def test_directory_node_model():
    """测试 DirectoryNode 模型"""
    from backend.routers.directories import DirectoryNode
    
    node = DirectoryNode(
        name="test_dir",
        path="/path/to/test_dir",
        children=[
            DirectoryNode(name="child1", path="/path/to/test_dir/child1"),
            DirectoryNode(name="child2", path="/path/to/test_dir/child2"),
        ]
    )
    
    assert node.name == "test_dir"
    assert node.path == "/path/to/test_dir"
    assert len(node.children) == 2


@pytest.mark.asyncio
async def test_directory_list_response_model():
    """测试 DirectoryListResponse 模型"""
    from backend.routers.directories import DirectoryListResponse, DirectoryNode
    
    response = DirectoryListResponse(
        success=True,
        directories=[
            DirectoryNode(name="dir1", path="/path/dir1"),
            DirectoryNode(name="dir2", path="/path/dir2"),
        ],
        root_path="/path"
    )
    
    assert response.success is True
    assert len(response.directories) == 2
    assert response.root_path == "/path"
