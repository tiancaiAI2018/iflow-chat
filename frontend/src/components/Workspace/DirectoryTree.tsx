import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import type { DirectoryNode } from '../../types';
import './DirectoryTree.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

interface DirectoryTreeProps {
  /** 选中的目录路径 */
  selectedPath: string | null;
  /** 选择回调 */
  onSelect: (path: string) => void;
  /** 是否禁用 */
  disabled?: boolean;
}

/**
 * 目录树组件
 * - 支持树形结构展示
 * - 支持展开/折叠子目录
 * - 单选模式，只能选择 workspace 目录及其子目录
 */
const DirectoryTree: React.FC<DirectoryTreeProps> = ({
  selectedPath,
  onSelect,
  disabled = false,
}) => {
  const [directories, setDirectories] = useState<DirectoryNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());

  // 加载目录数据
  const loadDirectories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get<{ success: boolean; directories: DirectoryNode[]; root_path: string }>(
        `${API_BASE_URL}/directories`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      );
      if (response.data.success) {
        setDirectories(response.data.directories);
      }
    } catch (err) {
      setError('加载目录失败');
      console.error('Failed to load directories:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDirectories();
  }, [loadDirectories]);

  // 切换展开状态
  const toggleExpand = (path: string) => {
    setExpandedPaths(prev => {
      const newSet = new Set(prev);
      if (newSet.has(path)) {
        newSet.delete(path);
      } else {
        newSet.add(path);
      }
      return newSet;
    });
  };

  // 选择目录
  const handleSelect = (path: string) => {
    if (!disabled) {
      onSelect(path);
    }
  };

  // 渲染目录节点
  const renderNode = (node: DirectoryNode, depth: number = 0): React.ReactNode => {
    const isExpanded = expandedPaths.has(node.path);
    const isSelected = selectedPath === node.path;
    const hasChildren = node.children && node.children.length > 0;

    return (
      <div key={node.path} className="directory-node">
        <div
          className={`directory-item ${isSelected ? 'selected' : ''} ${disabled ? 'disabled' : ''}`}
          style={{ paddingLeft: `${depth * 20 + 12}px` }}
          onClick={() => handleSelect(node.path)}
        >
          {/* 展开/折叠按钮 */}
          {hasChildren && (
            <button
              className="expand-btn"
              onClick={(e) => {
                e.stopPropagation();
                toggleExpand(node.path);
              }}
            >
              <span className={`expand-icon ${isExpanded ? 'expanded' : ''}`}>▶</span>
            </button>
          )}
          {/* 没有子目录时占位 */}
          {!hasChildren && <span className="expand-placeholder" />}

          {/* 目录图标 */}
          <span className="directory-icon">📁</span>

          {/* 目录名称 */}
          <span className="directory-name">{node.name}</span>

          {/* 选中标记 */}
          {isSelected && <span className="selected-mark">✓</span>}
        </div>

        {/* 子目录 */}
        {hasChildren && isExpanded && (
          <div className="directory-children">
            {node.children!.map(child => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  // 加载状态
  if (loading) {
    return (
      <div className="directory-tree-loading">
        <div className="loading-spinner"></div>
        <span>加载目录中...</span>
      </div>
    );
  }

  // 错误状态
  if (error) {
    return (
      <div className="directory-tree-error">
        <span className="error-icon">⚠️</span>
        <span>{error}</span>
        <button onClick={loadDirectories}>重试</button>
      </div>
    );
  }

  // 空状态
  if (directories.length === 0) {
    return (
      <div className="directory-tree-empty">
        <span className="empty-icon">📂</span>
        <span>暂无目录</span>
      </div>
    );
  }

  return (
    <div className="directory-tree">
      <div className="directory-tree-header">
        <span className="header-icon">🗂️</span>
        <span className="header-text">选择工作目录</span>
      </div>
      <div className="directory-tree-content">
        {/* 根目录选项 */}
        <div
          className={`directory-item root-item ${selectedPath === '/root/.iflow-bot/workspace' ? 'selected' : ''} ${disabled ? 'disabled' : ''}`}
          onClick={() => handleSelect('/root/.iflow-bot/workspace')}
        >
          <span className="expand-placeholder" />
          <span className="directory-icon">🏠</span>
          <span className="directory-name">workspace (根目录)</span>
          {selectedPath === '/root/.iflow-bot/workspace' && <span className="selected-mark">✓</span>}
        </div>

        {/* 子目录列表 */}
        {directories.map(node => renderNode(node, 0))}
      </div>
    </div>
  );
};

export default DirectoryTree;
