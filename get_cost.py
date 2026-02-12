import boto3
import csv
import datetime
import os

# --- ตั้งค่าวันที่ ---
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)
start_date = yesterday.strftime('%Y-%m-%d')
end_date = today.strftime('%Y-%m-%d')
file_date = yesterday.strftime('%Y%m%d')

client = boto3.client('ce', region_name='us-east-1')
sts_client = boto3.client('sts')
account_id = sts_client.get_caller_identity()["Account"]

filename = f"{file_date}_{account_id}_dailycost.csv"
file_path = os.path.join(os.getcwd(), filename) 

print(f"Fetching Net Costs for Account: {account_id}, Date: {start_date}")

try:
    response = client.get_cost_and_usage(
        TimePeriod={'Start': start_date, 'End': end_date},
        Granularity='DAILY',
        # ดึงทั้ง NetAmortizedCost และ NetUnblendedCost (หลังหักส่วนลด)
        Metrics=['NetAmortizedCost', 'NetUnblendedCost'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
            {'Type': 'DIMENSION', 'Key': 'REGION'} 
        ]
    )
except Exception as e:
    print(f"Error calling Cost Explorer: {e}")
    exit(1)

csv_data = []
total_net_unblended = 0.0
results = response['ResultsByTime'][0]
report_date = results['TimePeriod']['Start']

for group in results['Groups']:
    service_name = group['Keys'][0]
    location = group['Keys'][1]
    
    # ดึงค่า Cost ต่างๆ
    net_amortized = float(group['Metrics']['NetAmortizedCost']['Amount'])
    net_unblended = float(group['Metrics']['NetUnblendedCost']['Amount'])
    currency = group['Metrics']['NetUnblendedCost']['Unit']
    
    # ถ้าทุกค่าเป็น 0 ให้ข้ามไป
    if net_amortized == 0 and net_unblended == 0:
        continue

    total_net_unblended += net_unblended
    
    # เพิ่มข้อมูลลง List (เพิ่มคอลัมน์ Net Unblended เข้าไป)
    csv_data.append([
        report_date, 
        account_id, 
        f"{net_amortized:.2f}", 
        f"{net_unblended:.2f}", 
        currency, 
        location, 
        service_name
    ])

# --- เขียนไฟล์ CSV ---
# เพิ่ม Header 'net_unblended_cost (after discount)'
header = ['report_date', 'AWS Account ID', 'net_amortized_cost', 'net_unblended_cost', 'currency', 'location', 'service name']

with open(file_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(csv_data)

print(f"Report saved to: {file_path}")
print(f"Total Net Cost (After Discount): {total_net_unblended:.2f} {currency}")