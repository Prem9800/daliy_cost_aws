import boto3
import csv
import datetime
import os
import smtplib
from email.message import EmailMessage

def get_aws_cost():
    # 1. ตั้งค่าวันที่และชื่อไฟล์
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    start_date = yesterday.strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    file_date = yesterday.strftime('%Y%m%d')

    # 2. เชื่อมต่อ AWS Services
    # หมายเหตุ: Cost Explorer API ต้องระบุ region เป็น us-east-1 เสมอ
    client = boto3.client('ce', region_name='us-east-1')
    sts_client = boto3.client('sts')
    
    try:
        account_id = sts_client.get_caller_identity()["Account"]
    except Exception as e:
        print(f"AWS Auth Error: {e}")
        return

    filename = f"{file_date}_{account_id}_dailycost.csv"
    file_path = os.path.join(os.getcwd(), filename)

    print(f"Fetching costs for Account: {account_id} ({start_date})")

    # 3. ดึงข้อมูลจาก AWS Cost Explorer
    try:
        response = client.get_cost_and_usage(
            TimePeriod={'Start': start_date, 'End': end_date},
            Granularity='DAILY',
            Metrics=['NetAmortizedCost', 'NetUnblendedCost'], # ดึงทั้งแบบกระจายตัวและหลังหักส่วนลด
            GroupBy=[
                {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                {'Type': 'DIMENSION', 'Key': 'REGION'}
            ]
        )
    except Exception as e:
        print(f"Error calling AWS CE: {e}")
        return

    # 4. ประมวลผลข้อมูลลง CSV
    csv_data = []
    total_cost = 0.0
    results = response['ResultsByTime'][0]
    
    for group in results['Groups']:
        service = group['Keys'][0]
        region = group['Keys'][1]
        amortized = float(group['Metrics']['NetAmortizedCost']['Amount'])
        net_unblended = float(group['Metrics']['NetUnblendedCost']['Amount'])
        currency = group['Metrics']['NetUnblendedCost']['Unit']

        if amortized == 0 and net_unblended == 0:
            continue

        total_cost += net_unblended
        csv_data.append([start_date, account_id, f"{amortized:.2f}", f"{net_unblended:.2f}", currency, region, service])

    # 5. บันทึกไฟล์ CSV
    header = ['Date', 'AccountID', 'AmortizedCost', 'NetUnblendedCost', 'Currency', 'Region', 'Service']
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(csv_data)

    print(f"CSV created: {file_path}")
    
    # 6. ส่งอีเมล
    send_email(file_path, start_date, total_cost, currency)

def send_email(file_path, report_date, total_amount, currency):
    # ดึงค่าจาก Environment Variables (ที่ตั้งไว้ใน GitHub Secrets)
    email_user = os.environ.get('MAIL_USERNAME')
    email_pass = os.environ.get('MAIL_PASSWORD')
    receiver_email = email_user # ส่งหาตัวเอง หรือเปลี่ยนเป็นเมลอื่นก็ได้

    if not email_user or not email_pass:
        print("Email credentials not found. Skipping email step.")
        return

    msg = EmailMessage()
    msg['Subject'] = f"🚀 AWS Daily Cost Report: {report_date}"
    msg['From'] = email_user
    msg['To'] = receiver_email
    
    body = f"""
    สวัสดีครับ,
    
    สรุปค่าใช้จ่าย AWS ประจำวันที่: {report_date}
    ยอดรวมหลังหักส่วนลด (Net Unblended Cost): {total_amount:.2f} {currency}
    
    รายละเอียดเพิ่มเติมระบุอยู่ในไฟล์ CSV ที่แนบมาพร้อมกันนี้
    """
    msg.set_content(body)

    # แนบไฟล์ CSV
    with open(file_path, 'rb') as f:
        file_data = f.read()
        msg.add_attachment(
            file_data, 
            maintype='application', 
            subtype='octet-stream', 
            filename=os.path.basename(file_path)
        )

    # เชื่อมต่อ SMTP Gmail
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_user, email_pass)
            smtp.send_message(msg)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    get_aws_cost()