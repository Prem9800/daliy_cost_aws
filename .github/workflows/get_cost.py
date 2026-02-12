import boto3
import csv
import datetime
import os

# 1. ตั้งค่าและเตรียมวันที่
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)

# Format วันที่สำหรับชื่อไฟล์และ API (yyyy-MM-dd)
start_date = yesterday.strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')
file_date = yesterday.strftime('%Y%m%d')

# 2. เชื่อมต่อ AWS Cost Explorer Client
# ข้อมูล Credential จะถูกดึงจาก Environment Variable โดยอัตโนมัติ
client = boto3.client('ce', region_name='us-east-1') # Cost Explorer endpoint อยู่ที่ us-east-1 เสมอ

# ดึง Account ID (เพื่อใช้ตั้งชื่อไฟล์)
sts_client = boto3.client('sts')
account_id = sts_client.get_caller_identity()["Account"]

print(f"Checking cost for Account: {account_id}, Date: {start_date}")

# 3. ยิง API ดึงข้อมูล
# เราจะ Group ตาม Service และ UsageType เพื่อให้เห็นรายละเอียด
try:
    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='DAILY',
        Metrics=['UnblendedCost'],
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
# Header: วันที่, Account ID, cost, currency, location, service name, resource group(N/A), cost type(N/A)
# หมายเหตุ: API จำกัด GroupBy ได้สูงสุด 2 ตัว ถ้าต้องการมากกว่านี้ต้อง process เพิ่ม
# ในที่นี้เลือก Service กับ Region เป็นหลัก

results = response['ResultsByTime'][0] # เอาวันแรก (เมื่อวาน)
report_date = results['TimePeriod']['Start']

for group in results['Groups']:
    # Keys จะเรียงตาม GroupBy ที่เราส่งไป: [Service, Region]
    service_name = group['Keys'][0]
    location = group['Keys'][1]
    
    amount = group['Metrics']['UnblendedCost']['Amount']
    currency = group['Metrics']['UnblendedCost']['Unit']
    
    # Filter: ตัดยอดที่เป็น 0 ทิ้งเพื่อประหยัดบรรทัด
    if float(amount) == 0:
        continue

    csv_data.append([
        report_date,       # report_date
        account_id,        # AWS Account ID
        amount,            # cost
        currency,          # currency
        location,          # location
        service_name,      # service name
        "N/A",             # resource group (ต้องใช้ Tagging ถึงจะดึงได้)
        "Standard Usage"   # ประเภท cost (ถ้าอยากได้ UsageType ต้องเปลี่ยน GroupBy)
    ])

# 5. เขียนลงไฟล์ CSV
filename = f"{file_date}_{account_id}_dailycost.csv"

header = ['report_date', 'AWS Account ID', 'cost', 'currency', 'location', 'service name', 'resource group', 'cost type']

with open(filename, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(csv_data)

print(f"Successfully generated: {filename}")