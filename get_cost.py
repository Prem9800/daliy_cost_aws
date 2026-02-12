import boto3
import pandas as pd
from datetime import datetime, timedelta
import os
import smtplib
from email.message import EmailMessage

# --- CONFIGURATION ---
OUTPUT_FOLDER = "." 

def send_email(file_path, report_date, total_unblended, total_net, currency):
    # ดึงค่าจาก GitHub Secrets
    email_user = os.environ.get('MAIL_USERNAME')
    email_pass = os.environ.get('MAIL_PASSWORD')
    receiver_email = email_user # ส่งเข้าเมลตัวเอง

    if not email_user or not email_pass:
        print("Skipping Email: Mail credentials not found.")
        return

    msg = EmailMessage()
    msg['Subject'] = f"📊 AWS Daily Cost: {report_date}"
    msg['From'] = email_user
    msg['To'] = receiver_email
    
    body = f"""
    สวัสดีครับ,
    
    สรุปรายงานค่าใช้จ่าย AWS ประจำวันที่: {report_date}
    
    💰 ยอดรวมก่อนหักส่วนลด (Unblended): {total_unblended:.2f} {currency}
    ✅ ยอดรวมหลังหักส่วนลด (Net Amortized): {total_net:.2f} {currency}
    
    รายละเอียดราย Service และ Usage Type อยู่ในไฟล์แนบครับ
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

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_user, email_pass)
            smtp.send_message(msg)
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def get_detailed_daily_cost():
    # 1. Setup AWS Client (เปลี่ยนจาก Session เพื่อให้รันบน GitHub ได้)
    ce = boto3.client('ce', region_name='us-east-1')
    sts = boto3.client('sts')
    
    try:
        account_id = sts.get_caller_identity()["Account"]
    except Exception as e:
        print(f"❌ AWS Auth Error: {e}")
        return

    # 2. กำหนดช่วงเวลา
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
    total_unblended = 0.0
    total_net = 0.0
    currency = "USD"
    
    for result in response['ResultsByTime']:
        report_date_val = result['TimePeriod']['Start']
        for group in result['Groups']:
            service_name = group['Keys'][0]
            usage_type = group['Keys'][1]
            un_cost = float(group['Metrics']['UnblendedCost']['Amount'])
            n_cost = float(group['Metrics']['AmortizedCost']['Amount'])
            unit = group['Metrics']['UnblendedCost']['Unit']
            currency = unit

            if un_cost == 0 and n_cost == 0:
                continue

            total_unblended += un_cost
            total_net += n_cost

            # Logic แกะ Region แบบที่คุณเขียนไว้
            location_guess = "Global/Unknown"
            if "-" in usage_type:
                prefix = usage_type.split("-")[0]
                region_map = {
                    'APN1': 'ap-southeast-1 (Singapore)',
                    'APN2': 'ap-northeast-2 (Seoul)',
                    'USE1': 'us-east-1 (N. Virginia)',
                    'USW2': 'us-west-2 (Oregon)',
                    'EU': 'Europe'
                }
                location_guess = region_map.get(prefix, prefix)

            data_rows.append({
                'report_date': report_date_val,
                'AWS Account ID': account_id,
                'Service': service_name,
                'Usage Type': usage_type,
                'Cost (Unblended)': un_cost,
                'Net Cost (Amortized)': n_cost,
                'currency': unit,
                'Location (Est.)': location_guess
            })

    # 5. Export และ ส่งเมล
    if data_rows:
        df = pd.DataFrame(data_rows)
        filename = f"{file_date_str}_{account_id}_dailycost.csv"
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        
        df.to_csv(file_path, index=False)
        print(f"✅ Exported: {file_path}")
        
        # ส่งอีเมล
        send_email(file_path, start_date, total_unblended, total_net, currency)
    else:
        print("⚠️ No cost data found.")

if __name__ == "__main__":
    get_detailed_daily_cost()