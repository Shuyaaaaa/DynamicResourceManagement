# configuration file, contains the essential info for instances and load balancer
import os

image_id = 'ami-0c366b89d9d83d2ec'  # image(AMI) -ID to create new worker instance
key_pair = '1779_assignment2'       # EC2 Key Pair name
placement_group = 'workerpool'      # Name of the placement group for workers
manager_group = 'manager'           # Name of the placement group for manager
security_group = 'assignment2'      # Name of security group
ARN = 'arn:aws:elasticloadbalancing:us-east-1:374728096479:targetgroup/workerpool/a63abb37c600c8d9' # Amazon Resource Name(ARN) of the target group
manager_id = ''                     # Manager instance ID
ELB_DNS = 'http://assignment2-972156928.us-east-1.elb.amazonaws.com:5000/' # Load balancer DNS name
ELB_ARN = 'arn:aws:elasticloadbalancing:us-east-1:374728096479:loadbalancer/app/assignment2/386aeb1bd8985c92'  # ARN of Load balancer
ELB_name = 'assignment2' # Name of the load balancer
ELB_demension = "app/assignment2/386aeb1bd8985c92"
target_group_dimension = "targetgroup/workerpool/a63abb37c600c8d9"
user_data = '''#!/bin/bash -e
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
echo BEGIN
hostname
echo END
echo BEGIN
cd home/ec2-user/ImageTextDetector_WebApp
source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 wsgi:app
echo END'''

SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or  \
                                'mysql+pymysql://admin:ECE1779project@client.cdytawkmxeyk.us-east-1.rds.amazonaws.com/ece1779'
SQLALCHEMY_TRACK_MODIFICATIONS = False

S3_BUCKET = 'imageuserpool'
S3_KEY = 'AKIAVOP4I7LPWOEEWOAI'
S3_SECRET = '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'