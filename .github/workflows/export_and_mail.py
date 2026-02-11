import boto3

import csv

import smtplib

import os

from datetime import datetime, timedelta

from email.mime.multipart import MIMEMultipart

from email.mime.base import MIMEBase

from email.mime.text import MIMEText

from email import encoders


# --- ส่วนของการดึงข้อมูลจาก AWS ---

def get_billing():

client = boto3.client(

'ce',

aws_access_key_id=os.getenv('AKIASJAVRL76BKOTOBTH'),

aws_secret_access_key=os.getenv('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'),

region_name='ap-southeast-1'

)


yesterday = datetime.now() - timedelta(1)

start_date = yesterday.strftime('%Y-%m-%d')

end_date = datetime.now().strftime('%Y-%m-%d')


response = client.get_cost_and_usage(

TimePeriod={'Start': start_date, 'End': end_date},

Granularity='DAILY',

Metrics=['UnblendedCost', 'AmortizedCost'],

GroupBy=[{'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'},

{'Type': 'DIMENSION', 'Key': 'SERVICE'}]

)


acc_id = response['ResultsByTime'][0]['Groups'][0]['Keys'][0]

file_date = yesterday.strftime('%Y%m%d')

filename = f"{file_date}_{acc_id}_dailycost.csv"


with open(filename, 'w', newline='', encoding='utf-8') as f:

writer = csv.writer(f)

writer.writerow(['report_date', 'account_id', 'actual_cost', 'discounted_cost', 'currency', 'service'])


for group in response['ResultsByTime'][0]['Groups']:

writer.writerow([

start_date, group['Keys'][0],

group['Metrics']['UnblendedCost']['Amount'],

group['Metrics']['AmortizedCost']['Amount'],

group['Metrics']['UnblendedCost']['Unit'],

group['Keys'][1]

])

return filename


# --- ส่วนของการส่งอีเมล ---

def send_email(filename):

sender = os.getenv('EMAIL_USER')

password = os.getenv('EMAIL_PASS') # App Password 16 หลัก

receiver = os.getenv('EMAIL_RECEIVER')


msg = MIMEMultipart()

msg['From'] = sender

msg['To'] = receiver

msg['Subject'] = f"AWS Daily Billing Report - {filename}"


body = "รายละเอียดค่าใช้จ่าย AWS รายวันตามแนบครับ"

msg.attach(MIMEText(body, 'plain'))


with open(filename, "rb") as attachment:

part = MIMEBase("application", "octet-stream")

part.set_payload(attachment.read())

encoders.encode_base64(part)

part.add_header("Content-Disposition", f"attachment; filename= {filename}")

msg.attach(part)


server = smtplib.SMTP('smtp.gmail.com', 587)

server.starttls()

server.login(sender, password)

server.send_message(msg)

server.quit()


if __name__ == "__main__":

fname = get_billing()

send_email(fname)