import React, { useState } from 'react';
import './TaskManager.css';

interface TaskCreatorProps {
  onCreate: (description: string) => Promise<void>;
  isCreating: boolean;
}

const TaskCreator: React.FC<TaskCreatorProps> = ({ onCreate, isCreating }) => {
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!description.trim()) {
      setError('请输入任务描述');
      return;
    }

    setError(null);
    
    try {
      await onCreate(description.trim());
      setDescription('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建任务失败');
    }
  };

  const examplePrompts = [
    '每天早上9点提醒我查看股票',
    '每周五下午5点提醒我写周报',
    '每小时提醒我喝水',
    '每月1号上午10点提醒我交房租',
  ];

  return (
    <div className="task-creator">
      <div className="creator-header">
        <h3>创建定时任务</h3>
        <p className="creator-hint">使用自然语言描述你的任务，AI 会自动解析时间和内容</p>
      </div>

      <form onSubmit={handleSubmit} className="creator-form">
        <div className="input-wrapper">
          <input
            type="text"
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
              setError(null);
            }}
            placeholder="例如：每天早上9点提醒我查看股票"
            disabled={isCreating}
            className={error ? 'error' : ''}
          />
          <button
            type="submit"
            disabled={isCreating || !description.trim()}
            className="create-btn"
          >
            {isCreating ? (
              <>
                <span className="btn-loading"></span>
                创建中...
              </>
            ) : (
              '创建任务'
            )}
          </button>
        </div>

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            {error}
          </div>
        )}
      </form>

      <div className="example-prompts">
        <div className="examples-title">示例：</div>
        <div className="examples-list">
          {examplePrompts.map((prompt, index) => (
            <button
              key={index}
              className="example-btn"
              onClick={() => setDescription(prompt)}
              type="button"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      <div className="creator-tips">
        <h4>支持的格式</h4>
        <ul>
          <li><strong>每天</strong>：每天早上8点、每天下午3点半</li>
          <li><strong>每周</strong>：每周一早上9点、每周五下午5点</li>
          <li><strong>每月</strong>：每月1号上午10点、每月15号中午12点</li>
          <li><strong>间隔</strong>：每小时、每30分钟、每2小时</li>
        </ul>
      </div>
    </div>
  );
};

export default TaskCreator;
