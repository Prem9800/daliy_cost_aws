import boto3
import csv
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta

def send_email(file_path, filename):
    sender = os.getenv('EMAIL_SENDER')
    password = os.getenv('EMAIL_PASSWORD')
    receiver = os.getenv('EMAIL_RECEIVER')

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = f"AWS Daily Billing Report (Cost vs Net Cost) - {filename}"

    body = f"รายงานค่าใช้จ่าย AWS รายวันสำหรับ {filename} (รวมข้อมูล Unblended และ Net Unblended Cost)"
    msg.attach(MIMEText(body, 'plain'))

    with open(file_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename= {filename}")
        msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def get_aws_billing():
    client = boto3.client('ce', region_name='us-east-1')
    sts = boto3.client('sts')
    account_id = sts.get_caller_identity().get('Account')
    
    yesterday = (datetime.now() - timedelta(1)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    file_date = (datetime.now() - timedelta(1)).strftime('%Y%m%d')

    # ดึงทั้ง UnblendedCost (ราคาป้าย) และ NetUnblendedCost (จ่ายจริงหลังหักส่วนลด)
    response = client.get_cost_and_usage(
        TimePeriod={'Start': yesterday, 'End': today},
        Granularity='DAILY',
        Metrics=['UnblendedCost', 'NetUnblendedCost'], 
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
            {'Type': 'DIMENSION', 'Key': 'REGION'}
        ]
    )

    filename = f"{file_date}_{account_id}_dailycost.csv"
    
    # เพิ่มหัวตารางให้มีทั้งสองค่า
    header = [
        'report_date', 'AWS Account ID', 'unblended_cost', 
        'net_unblended_cost', 'currency', 'location', 
        'service_name', 'resource_group'
    ]

    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        
        for day in response['ResultsByTime']:
            date = day['TimePeriod']['Start']
            for group in day['Groups']:
                unblended = group['Metrics']['UnblendedCost']['Amount']
                net_unblended = group['Metrics']['NetUnblendedCost']['Amount']
                unit = group['Metrics']['UnblendedCost']['Unit']
                service = group['Keys'][0]
                region = group['Keys'][1]
                
                writer.writerow([
                    date, account_id, unblended, net_unblended, 
                    unit, region, service, "Default"
                ])
    
    send_email(filename, filename)

if __name__ == "__main__":
    get_aws_billing()