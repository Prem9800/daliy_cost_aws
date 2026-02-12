import boto3
import pandas as pd
from datetime import datetime, timedelta
import os

# --- CONFIGURATION ---
OUTPUT_FOLDER = "." 
AWS_PROFILE = "default" 

def get_detailed_daily_cost():
    # 1. Setup AWS Session
    session = boto3.Session(profile_name=AWS_PROFILE)
    ce = session.client('ce')
    sts = session.client('sts')
    
    account_id = sts.get_caller_identity()["Account"]

    # 2. กำหนดช่วงเวลา (เมื่อวาน)
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    start_date = yesterday.strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    file_date_str = yesterday.strftime('%Y%m%d')

    print(f"Fetching DETAILED cost for Account: {account_id}, Date: {start_date}...")

    # 3. เรียก API AWS Cost Explorer
    # ปรับ GroupBy: ใช้ SERVICE และ USAGE_TYPE (ละเอียดกว่า Region)
    # หมายเหตุ: API อนุญาตให้ GroupBy ได้สูงสุด 2 Dimensions
    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='DAILY',
        Metrics=['UnblendedCost', 'AmortizedCost'], 
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
            {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'} 
        ]
    )

    # 4. แปลงข้อมูล
    data_rows = []
    
    for result in response['ResultsByTime']:
        report_date = result['TimePeriod']['Start']
        
        for group in result['Groups']:
            # Keys: [Service, UsageType]
            service_name = group['Keys'][0]
            usage_type = group['Keys'][1]
            
            # ดึงตัวเลข
            unblended_cost = float(group['Metrics']['UnblendedCost']['Amount']) # ราคาตั้ง
            net_cost = float(group['Metrics']['AmortizedCost']['Amount'])       # ราคาหลังหักส่วนลด/เกลี่ย
            unit = group['Metrics']['UnblendedCost']['Unit']

            # --- LOGIC การกรอง 0 ตามที่คุณขอ ---
            # 1. ถ้า Cost ตั้งต้นเป็น 0 และ Net Cost เป็น 0 -> ไม่แสดง (แปลว่าไม่มีการใช้งาน หรือไม่มีค่าใช้จ่ายเลย)
            # 2. ถ้า Cost ตั้งต้น > 0 แต่ Net Cost = 0 (เช่น ใช้ Credit ฟรี) -> แสดง (Condition นี้จะผ่านบรรทัดล่าง)
            # 3. ถ้า Cost ตั้งต้น = 0 แต่ Net Cost > 0 (Rare case: Tax adjustment) -> แสดง
            
            if unblended_cost == 0 and net_cost == 0:
                continue

            # พยายามแกะ Region จาก Usage Type (เช่น 'APN1-BoxUsage' -> Region คือ APN1/Singapore)
            # วิธีนี้ช่วยประหยัด Dimension Quota
            location_guess = "Global/Unknown"
            if "-" in usage_type:
                prefix = usage_type.split("-")[0]
                # Mapping คร่าวๆ (อาจไม่ครบทุก Region แต่ครอบคลุมตัวหลัก)
                region_map = {
                    'APN1': 'ap-southeast-1 (Singapore)',
                    'APN2': 'ap-northeast-2 (Seoul)',
                    'APS1': 'ap-southeast-1 (Singapore-Legacy)', # บางทีเจอ Code นี้
                    'USE1': 'us-east-1 (N. Virginia)',
                    'USW2': 'us-west-2 (Oregon)',
                    'EU': 'Europe',
                    # ถ้าไม่มี Prefix ที่รู้จัก มักจะเป็น Global Service เช่น IAM, Route53
                }
                location_guess = region_map.get(prefix, prefix) # ถ้าไม่เจอให้ใส่ Prefix เดิมไปก่อน

            row = {
                'report_date': report_date,
                'AWS Account ID': account_id,
                'Service': service_name,
                'Usage Type': usage_type,     # *สำคัญมาก ดูตรงนี้จะรู้ว่าค่าอะไร
                'Location (Est.)': location_guess,
                'Cost (Unblended)': unblended_cost,
                'Net Cost (Amortized)': net_cost,
                'currency': unit,
                'service_name_duplicate': service_name, # เผื่ออยากคง Format เดิม
                'resource_group': 'N/A'
            }
            data_rows.append(row)

    # 5. Export CSV
    if data_rows:
        df = pd.DataFrame(data_rows)
        
        # จัดเรียง Column ให้อ่านง่ายแบบ Professional Report
        columns_order = [
            'report_date', 
            'AWS Account ID', 
            'Service', 
            'Usage Type', 
            'Cost (Unblended)', 
            'Net Cost (Amortized)', 
            'currency', 
            'Location (Est.)',
            'resource_group'
        ]
        
        # เลือกเฉพาะ Column ที่มีใน list (ป้องกัน error)
        valid_columns = [c for c in columns_order if c in df.columns]
        df = df[valid_columns]
        
        filename = f"{file_date_str}_{account_id}_dailycost.csv"
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        
        df.to_csv(file_path, index=False)
        print(f"Exported: {file_path}")
        print(f"Total Rows: {len(df)}")
    else:
        print("No cost data found (Check your date range or permissions).")

if __name__ == "__main__":
    get_detailed_daily_cost()