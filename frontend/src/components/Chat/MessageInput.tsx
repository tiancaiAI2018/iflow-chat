import React, { useState, useRef, ChangeEvent } from 'react';
import './Chat.css';

// 附件类型
export interface Attachment {
  id: string;
  file: File;
  preview?: string; // 图片预览URL
  type: 'image' | 'file';
  name: string;
  size: number;
}

interface MessageInputProps {
  onSend: (content: string, attachments: Attachment[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

const MessageInput: React.FC<MessageInputProps> = ({
  onSend,
  disabled = false,
  placeholder = '输入消息...',
}) => {
  const [input, setInput] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 自动调整高度
  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  };

  // 生成唯一ID
  const generateId = () => `attachment-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  // 判断文件类型
  const getFileType = (file: File): 'image' | 'file' => {
    if (file.type.startsWith('image/')) {
      return 'image';
    }
    return 'file';
  };

  // 格式化文件大小
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // 处理文件选择
  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newAttachments: Attachment[] = [];

    Array.from(files).forEach(file => {
      const attachment: Attachment = {
        id: generateId(),
        file,
        type: getFileType(file),
        name: file.name,
        size: file.size,
      };

      // 如果是图片，创建预览URL
      if (attachment.type === 'image') {
        attachment.preview = URL.createObjectURL(file);
      }

      newAttachments.push(attachment);
    });

    setAttachments(prev => [...prev, ...newAttachments]);

    // 清空 input 以便再次选择相同文件
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // 删除附件
  const removeAttachment = (id: string) => {
    setAttachments(prev => {
      const attachment = prev.find(a => a.id === id);
      // 释放预览URL
      if (attachment?.preview) {
        URL.revokeObjectURL(attachment.preview);
      }
      return prev.filter(a => a.id !== id);
    });
  };

  // 发送消息
  const handleSend = () => {
    const trimmedInput = input.trim();
    // 有文本或附件时可以发送
    if ((trimmedInput || attachments.length > 0) && !disabled) {
      onSend(trimmedInput, attachments);
      setInput('');
      // 不要在这里释放 blob URL，因为 Message 组件还需要用它显示图片
      // blob URL 会在页面关闭或组件卸载时自动释放
      setAttachments([]);
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  // 打开文件选择器
  const openFilePicker = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="message-input-wrapper">
      {/* 附件预览区域 */}
      {attachments.length > 0 && (
        <div className="attachments-preview">
          {attachments.map(attachment => (
            <div key={attachment.id} className="attachment-thumbnail">
              {attachment.type === 'image' && attachment.preview ? (
                <img 
                  src={attachment.preview} 
                  alt={attachment.name}
                  className="attachment-image"
                />
              ) : (
                <div className="attachment-file-icon">
                  <span className="file-ext">
                    {attachment.name.split('.').pop()?.toUpperCase() || 'FILE'}
                  </span>
                </div>
              )}
              <button
                className="attachment-remove"
                onClick={() => removeAttachment(attachment.id)}
                title="移除"
              >
                ×
              </button>
              <div className="attachment-name" title={attachment.name}>
                {attachment.name.length > 10 
                  ? `${attachment.name.slice(0, 7)}...` 
                  : attachment.name}
              </div>
            </div>
          ))}
        </div>
      )}
      
      {/* 输入区域 */}
      <div className="message-input-container">
        {/* 附件按钮 */}
        <button
          className="attachment-button"
          onClick={openFilePicker}
          disabled={disabled}
          title="添加附件"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/>
          </svg>
        </button>
        
        {/* 隐藏的文件输入 */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          accept="image/*,.pdf,.doc,.docx,.txt,.py,.js,.ts,.jsx,.tsx,.json,.md,.csv,.xlsx,.xls"
        />
        
        {/* 文本输入 */}
        <textarea
          ref={textareaRef}
          className="message-input"
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            adjustHeight();
          }}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
        />
        
        {/* 发送按钮 */}
        <button
          className="send-button"
          onClick={handleSend}
          disabled={disabled || (!input.trim() && attachments.length === 0)}
        >
          发送
        </button>
      </div>
    </div>
  );
};

export default MessageInput;