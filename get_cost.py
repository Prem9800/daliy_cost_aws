import boto3
import csv
import datetime
import os

# 1. ตั้งค่าและเตรียมวันที่
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)

start_date = yesterday.strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')
file_date = yesterday.strftime('%Y%m%d')

# 2. เชื่อมต่อ AWS Client
client = boto3.client('ce', region_name='us-east-1')
sts_client = boto3.client('sts')
account_id = sts_client.get_caller_identity()["Account"]

print(f"Checking Net Amortized Cost for Account: {account_id}, Date: {start_date}")

# 3. ยิง API ดึงข้อมูล (ปรับ Metrics เป็น NetAmortizedCost)
try:
    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='DAILY',
        Metrics=['NetAmortizedCost'],  # <--- จุดที่ 1: เปลี่ยนจาก UnblendedCost
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
            {'Type': 'DIMENSION', 'Key': 'REGION'} 
        ]
    )
except Exception as e:
    print(f"Error calling AWS API: {e}")
    exit(1)

# 4. เตรียมข้อมูลสำหรับ CSV
csv_data = []
results = response['ResultsByTime'][0]
report_date = results['TimePeriod']['Start']

for group in results['Groups']:
    service_name = group['Keys'][0]
    location = group['Keys'][1]
    
    # จุดที่ 2: เปลี่ยนชื่อ Key ตาม Metrics ที่ดึงมา
    amount = group['Metrics']['NetAmortizedCost']['Amount']
    currency = group['Metrics']['NetAmortizedCost']['Unit']
    
    # กรองยอด 0 ออก (แต่ถ้ามีส่วนลด/Credit จนยอดติดลบ จะ