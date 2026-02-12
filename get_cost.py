import boto3
import csv
import datetime
import os

# --- ส่วนเดิม ---
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)
start_date = yesterday.strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')
file_date = yesterday.strftime('%Y%m%d')

client = boto3.client('ce', region_name='us-east-1')
sts_client = boto3.client('sts')
account_id = sts_client.get_caller_identity()["Account"]

# --- ปรับปรุงตรงนี้: ระบุตำแหน่งไฟล์ให้ชัดเจน ---
filename = f"{file_date}_{account_id}_dailycost.csv"
# ใช้ os.getcwd() เพื่อหาโฟลเดอร์ปัจจุบันที่ทำงานอยู่
file_path = os.path.join(os.getcwd(), filename) 

print(f"Checking cost for Account: {account_id}, Date: {start_date}")

try:
    response = client.get_cost_and_usage(
        TimePeriod={'Start': start_date, 'End': end_date},
        Granularity='DAILY',
        Metrics=['NetAmortizedCost'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
            {'Type': 'DIMENSION', 'Key': 'REGION'} 
        ]
    )
except Exception as e:
    print(f"Error: {e}")
    exit(1)

csv_data = []
results = response['ResultsByTime'][0]
report_date = results['TimePeriod']['Start']

for group in results['Groups']:
    service_name = group['Keys'][0]
    location = group['Keys'][1]
    amount = group['Metrics']['NetAmortizedCost']['Amount']
    currency = group['Metrics']['NetAmortizedCost']['Unit']
    
    if float(amount) == 0:
        continue

    csv_data.append([report_date, account_id, f"{float(amount):.2f}", currency, location, service_name, "N/A", "Net Amortized Cost"])

# --- ปรับปรุงตรงนี้: ใช้ file_path แทน filename ---
header = ['report_date', 'AWS Account ID', 'cost', 'currency', 'location', 'service name', 'resource group', 'cost type']
with open(file_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(csv_data)

print(f"File created successfully at: {file_path}")