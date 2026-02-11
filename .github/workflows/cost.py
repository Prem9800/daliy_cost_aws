import boto3
import csv
from datetime import datetime, timedelta
 
# --- ตั้งค่าสิทธิ์เข้าถึง ---
ACCESS_KEY = 'AKIASJAVRL76BKOTOBTH'
SECRET_KEY = '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'
# ----------------------
 
def get_detailed_billing_report():
    client = boto3.client(
        'ce',
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name='ap-southeast-1'
    )
 
    # 1. กำหนดช่วงเวลา (ดึงข้อมูลของเมื่อวาน)
    yesterday = datetime.now() - timedelta(1)
    start_date = yesterday.strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    # 2. เรียก API ดึงข้อมูล
    # เราจะดึงทั้ง UnblendedCost (ราคาจริง) และ AmortizedCost (ราคาหลังหักส่วนลด/เฉลี่ย)
    response = client.get_cost_and_usage(
        TimePeriod={'Start': start_date, 'End': end_date},
        Granularity='DAILY',
        Metrics=['UnblendedCost', 'AmortizedCost'], 
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'}, # เพื่อเอา Account ID มาทำชื่อไฟล์
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
            {'Type': 'DIMENSION', 'Key': 'REGION'},
            {'Type': 'DIMENSION', 'Key': 'RECORD_TYPE'}
        ]
    )
 
    # 3. วนลูปประมวลผลข้อมูล
    for result in response['ResultsByTime']:
        report_date_str = result['TimePeriod']['Start'] # yyyy-mm-dd
        file_date = report_date_str.replace('-', '')   # yyyyMMdd
        for group in result['Groups']:
            account_id = group['Keys'][0]
            service_name = group['Keys'][1]
            location = group['Keys'][2]
            cost_type = group['Keys'][3]
            # ดึงตัวเลขค่าใช้จ่าย
            unblended_cost = group['Metrics']['UnblendedCost']['Amount']
            amortized_cost = group['Metrics']['AmortizedCost']['Amount']
            currency = group['Metrics']['UnblendedCost']['Unit']
 
            # 4. ตั้งชื่อไฟล์ตามเงื่อนไข: yyyyMMdd_awsAccountID_dailycost.csv
            filename = f"{file_date}_{account_id}_dailycost.csv"
 
            # 5. บันทึกข้อมูลลง CSV (ใช้โหมด 'a' เพื่อเขียนต่อท้ายกรณีมีหลาย Service ใน Account เดียวกัน)
            file_exists = False
            try:
                with open(filename, 'r'): file_exists = True
            except FileNotFoundError:
                file_exists = False
 
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    # หัว Column
                    writer.writerow([
                        'report_date', 'subscription_id', 'actual_cost_unblended', 
                        'discounted_cost_amortized', 'currency', 'location', 
                        'service_name', 'cost_type'
                    ])
                writer.writerow([
                    report_date_str, account_id, unblended_cost, 
                    amortized_cost, currency, location, 
                    service_name, cost_type
                ])
 
    print("สร้าง Report เรียบร้อยแล้ว")
 
if __name__ == "__main__":
    get_detailed_billing_report()