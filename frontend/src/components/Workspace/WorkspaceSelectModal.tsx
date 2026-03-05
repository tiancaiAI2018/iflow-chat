import React, { useState } from 'react';
import DirectoryTree from './DirectoryTree';
import './WorkspaceSelectModal.css';

interface WorkspaceSelectModalProps {
  /** 是否显示 */
  isOpen: boolean;
  /** 关闭回调 */
  onClose: () => void;
  /** 确认选择回调 */
  onConfirm: (workingDirectory: string) => void;
  /** 默认工作目录 */
  defaultDirectory?: string;
  /** 是否正在创建 */
  isCreating?: boolean;
}

/**
 * 工作目录选择对话框
 * 创建新会话时，用户需要选择一个工作目录
 */
const WorkspaceSelectModal: React.FC<WorkspaceSelectModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  defaultDirectory = '/root/.iflow-bot/workspace',
  isCreating = false,
}) => {
  const [selectedPath, setSelectedPath] = useState<string | null>(defaultDirectory);

  const handleConfirm = () => {
    if (selectedPath) {
      onConfirm(selectedPath);
    }
  };

  const handleCancel = () => {
    onClose();
  };

  // 点击遮罩关闭
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="workspace-modal-overlay" onClick={handleOverlayClick}>
      <div className="workspace-modal">
        {/* 标题 */}
        <div className="workspace-modal-header">
          <h3 className="workspace-modal-title">选择工作目录</h3>
          <button className="workspace-modal-close" onClick={handleCancel} disabled={isCreating}>
            ×
          </button>
        </div>

        {/* 说明 */}
        <div className="workspace-modal-description">
          请选择新会话的工作目录，iFlow 将在该目录下执行任务。
        </div>

        {/* 目录树 */}
        <div className="workspace-modal-content">
          <DirectoryTree
            selectedPath={selectedPath}
            onSelect={setSelectedPath}
            disabled={isCreating}
          />
        </div>

        {/* 已选择路径显示 */}
        {selectedPath && (
          <div className="workspace-modal-selected">
            <span className="selected-label">已选择：</span>
            <span className="selected-path">{selectedPath}</span>
          </div>
        )}

        {/* 底部按钮 */}
        <div className="workspace-modal-footer">
          <button
            className="workspace-modal-btn cancel"
            onClick={handleCancel}
            disabled={isCreating}
          >
            取消
          </button>
          <button
            className="workspace-modal-btn confirm"
            onClick={handleConfirm}
            disabled={!selectedPath || isCreating}
          >
            {isCreating ? '创建中...' : '确认创建'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default WorkspaceSelectModal;
