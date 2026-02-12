import boto3
import pandas as pd
from datetime import datetime, timedelta
import os
import smtplib
from email.message import EmailMessage

# --- CONFIGURATION (ปรับให้เข้ากับ GitHub Actions) ---
OUTPUT_FOLDER = "." 

def send_email(file_path, report_date, total_unblended, total_net, currency):
    email_user = os.environ.get('MAIL_USERNAME')
    email_pass = os.environ.get('MAIL_PASSWORD')
    receiver_email = email_user # ส่งหาตัวเอง หรือระบุอีเมลปลายทางที่นี่

    if not email_user or not email_pass:
        print("Skipping Email: MAIL_USERNAME or MAIL_PASSWORD not set.")
        return

    msg = EmailMessage()
    msg['Subject'] = f"📊 AWS Detailed Cost Report: {report_date}"
    msg['From'] = email_user
    msg['To'] = receiver_email
    
    body = f"""
    สวัสดีครับ,
    
    สรุปค่าใช้จ่าย AWS รายละเอียดราย Service และ Usage Type ประจำวันที่: {report_date}
    
    💰 ยอดรวมก่อนหักส่วนลด (Unblended): {total_unblended:.2f} {currency}
    ✅ ยอดรวมหลังหักส่วนลด (Net Amortized): {total_net:.2f} {currency}
    
    รายละเอียดทั้งหมดอยู่ในไฟล์ CSV ที่แนบมาครับ
    """
    msg.set_content(body)

    with open(file_path, 'rb') as f:
        file_data = f.read()
        msg.add_attachment(
            file_data, 
            maintype='application', 
            subtype='octet-stream', 
            filename=os.path.basename(file_path)
        )

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_user, email_pass)
            smtp.send_message(msg)
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def get_detailed_daily_cost():
    # 1. Setup AWS Session (ใช้ Environment Variables อัตโนมัติใน GitHub Actions)
    ce = boto3.client('ce', region_name='us-east-1')
    sts = boto3.client('sts')
    
    try:
        account_id = sts.get_caller_identity()["Account"]
    except Exception as e:
        print(f"AWS Auth Error: {e}")
        return

    # 2. กำหนดช่วงเวลา (เมื่อวาน)
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    start_date = yesterday.strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    file_date_str = yesterday.strftime('%Y%m%d')

    print(f"Fetching DETAILED cost for Account: {account_id}, Date: {start_date}...")

    # 3. เรียก API AWS Cost Explorer
    response = ce.get_cost_and_usage(
        TimePeriod={'Start': start_date, 'End': end_date},
        Granularity='DAILY',
        Metrics=['UnblendedCost', 'AmortizedCost'], 
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
            {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'} 
        ]
    )

    # 4. แปลงข้อมูล
    data_rows = []
    total_unblended_sum = 0.0
    total_net_sum = 0.0
    currency_unit = "USD