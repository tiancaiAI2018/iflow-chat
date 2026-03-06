import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

def send_ppt_email():
    """发送PPT文件到指定邮箱"""
    # 邮件配置
    smtp_server = "smtp.126.com"
    smtp_port = 465
    smtp_user = "wsadfg142536@126.com"
    smtp_password = "ZVes6dnvmUYV6iZM"
    
    # 收件人和PPT文件
    to_email = "106105357@qq.com"
    ppt_path = "/root/.iflow-bot/workspace/mybot/ppt/刻晴角色介绍_高级版.pptx"
    
    # 创建邮件
    message = MIMEMultipart()
    message["From"] = smtp_user
    message["To"] = to_email
    message["Subject"] = "【iFlow】刻晴角色介绍PPT"
    
    # 邮件正文
    body = """
您好！

这是您请求的刻晴角色介绍PPT，共10页，包含：
- 角色简介
- 背景故事
- 技能介绍（元素战技和元素爆发）
- 命之座效果
- 战斗定位
- 装备推荐
- 配队推荐

感谢使用iFlow服务！

iFlow AI 助手
"""
    message.attach(MIMEText(body, "plain", "utf-8"))
    
    # 添加PPT附件
    with open(ppt_path, "rb") as attachment:
        part = MIMEBase("application", "vnd.openxmlformats-officedocument.presentationml.presentation")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename=Keqing_Introduction.pptx"
        )
        message.attach(part)
    
    print(f"正在发送邮件到 {to_email}...")
    print(f"附件大小: {os.path.getsize(ppt_path) / 1024 / 1024:.2f} MB")
    
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=300) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to_email, message.as_string())
        print("邮件发送成功！")
        return True
    except Exception as e:
        print(f"发送失败: {e}")
        return False

if __name__ == "__main__":
    send_ppt_email()