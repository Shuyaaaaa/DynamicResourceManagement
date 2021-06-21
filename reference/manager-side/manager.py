import math
import time
import json
import boto3
import config
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

# ref: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.ServiceResource.create_instances

# Steps to create a new instance: 
    # 1. create a instance 
    # 2. Waits until it is running 
    # 3. Register the new instance to ELB target group 
    # 4. Waits until the registration is complete

# Steps to terminate a running instance: 
    # 1. Get the ID of the instance to derminate 
    # 2. Deregister the instance from the ELB target group 
    # 3. Waits until the deregistration is complete 
    # 4. Terminate the instance
    # 5. Waits until the instance is terminated



def get_detail(id):
    ec2 = boto3.resource('ec2') # A resource representing Amazon Elastic Compute Cloud (EC2)
    # Find all running instances
    instance = ec2.instances.filter(
        Filters = [
            {
                'Name': 'instance-id',
                'Values': [id]
            },
        ]
    )
    return instance  

def select_running_inst():
    ec2 = boto3.resource('ec2') # A resource representing Amazon Elastic Compute Cloud (EC2)
    # Find all running instances
    instances = ec2.instances.filter(
        Filters = [
            {'Name': 'placement-group-name',
           'Values': [config.placement_group]},

            {'Name': 'instance-state-name',
           'Values': ['running']},
           
            {'Name': 'image-id', # The ID of the image used to launch the instance (AKA: AMI-ID)
            'Values': [config.image_id]}, # The ami used to create workers, in one worker group all workers should have same ami
        ]
    )
    return instances  # Return a list of running Instance resources (workers)


# Add a new EC2 instance(worker)
def create_new_instance():
    ec2 = boto3.resource('ec2') # A resource representing Amazon Elastic Compute Cloud (EC2)
    instances = select_running_inst() # Select all running workers
    
    # Full load check, maximum szie of worker pool is 10
    inst_id = []
    for instance in instances:  # assign attributes to their specified lists
        inst_id.append(instance.id)
    if len(inst_id) >= 10:
        print('Worker pool is fully loaded! ', len(inst_id)," are running!")
        # alert = None
        # return alert # Return an alert of full load
    
    # Create a new worker instance 
    instance = ec2.create_instances(
        ImageId=config.image_id,   # The ID of the AMI
        InstanceType='t2.small',  # T2 small instance
        KeyName=config.key_pair,  # The name of the key pair
        MinCount=1,  # The maximum number of instances to launch
        MaxCount=1,  # The minimum number of instances to launch
        Monitoring= {'Enabled': True}, # Indicates detailed monitoring is enabled
        Placement={'AvailabilityZone': 'us-east-1b', 
                    'GroupName': config.placement_group, } ,# US East (N. Virginia)
        SecurityGroups=[config.security_group,],  # Name of the Security group
        UserData=config.user_data,
        TagSpecifications=[
            {
                'ResourceType': 'instance',  # The type of resource to tag
                'Tags':[
                    {
                        'Key': 'Name',
                        'Value': 'manually_add_worker' # Tag this worker is added manually
                    },
                ]
            },
        ]
    )
    instance = instance[0] # only one instance contained in the list(linstance)
    print('New instance',instance,' is added.')
    # Waits until the instance is running
    instance.wait_until_running( 
                Filters=[
                    {
                        'Name': 'instance-id',
                        'Values': [instance.id]
                    },
                ],
            )
    print('New Instance', instance,' is running')
    # register the new instance to ELB target group
    elb = boto3.client('elbv2')  # client represnting the Elastic Load Balancer
                                         # elb is to support classic elb, elbv2 is for application elb
    print('Registering the new instance to ELB target group')
    elb.register_targets( # registers the specific targets with the specific target group
        TargetGroupArn=config.ARN, # The Amazon Resource Name of the target group
        Targets=[
            {
                'Id': instance.id,  # ID of the target (instance) to register
            },
        ]
    )
    
    # Waiting for complete registering
    # Describe the health of specified targets until a successful state is reached
    waiter = elb.get_waiter('target_in_service') # return an object that can wait for some condition
    waiter.wait(
        TargetGroupArn=config.ARN, # The Amazon Resource Name of the target group
        Targets=[
            {
                'Id': instance.id,  # ID of the target (instance)  
            },
        ],
    ) # Up to now, a new created instance is running and successfully registered in ELB target group
    print('New instance ', instance.id, 'is registered')


# Terminate an instance (worker)
def inst_remove(inst_Id):
    ec2 = boto3.resource('ec2')
    # Deregister the instance
    print('Deregistering instance-ID:', inst_Id)
    elb = boto3.client('elbv2')
    elb.deregister_targets(
        TargetGroupArn=config.ARN, # The Amazon Resource Name of the target group
        Targets=[
            {
                'Id': inst_Id,  # ID of the target (instance) to deregister  
            },
        ]
    )
    # Waiting for complete
    # Describe the health of specified targets until a successful state is reached
    waiter = elb.get_waiter('target_deregistered') # return an object that can wait for some condition
    waiter.wait(
        TargetGroupArn=config.ARN, # The Amazon Resource Name of the target group
        Targets=[
            {
                'Id': inst_Id,  # ID of the target (instance)  to deregister
            },
        ],
    )
    print('Instance-ID: ', inst_Id, 'is deregistered')
    
    # Terminate instances
    print('Terminating instance-ID:', inst_Id)
    # ec2.instances.filter(InstanceIds=[inst_Id]).terminate() # Shuts down the specified instance
    instance = ec2.instances.filter(InstanceIds=[inst_Id])
    if instance is not None:
            for inst in instance: 
                inst.terminate()
                  # Waits until the instance is terminated
                inst.wait_until_terminated(
                    Filters=[
                                {
                                    'Name': 'instance-id',
                                    'Values': [inst.id]
                                },
                            ],
                        )
                print('Instance-ID: ', inst.id, ' is terminated')
                
# Get information from all rnuuing workers
def get_inst_info():
    ec2 = boto3.resource('ec2')
    instances = select_running_inst()  # filter all running instances
    
    # Lists of attributes from running instances
    inst_id = [] # A list contains IDs of all running instances
    inst_base_id = [] # A list contains Image-IDs of all running instances (image-id is the AMI ID used to launch the instance)
    inst_key_name = [] # The name of the key pair
    inst_tag = [] # Tags assigned to the instance, tag contains the name of the instance for this assignment
    inst_type = [] # The type of the instance (Technially, all shoube be t2.small)
    
    for instance in instances:  # assign attributes to their specified lists
        inst_id.append(instance.id) # IDs of all running workers
        inst_base_id.append(instance.image_id)
        inst_key_name.append(instance.key_name)
        inst_tag.append(instance.tags)
        inst_type.append(instance.instance_type)
    
    return inst_id, inst_base_id, inst_key_name, inst_tag, inst_type


# CPU utilization of the worker in past 30 min, resolution is 1 min 
def inst_CPU(inst_id):
    ec2 = boto3.resource('ec2')
    instance = ec2.Instance(inst_id) # Identify the instance by ID
    watch = boto3.client('cloudwatch') # A low-level client representing Amazon CloudWatch
    new_uti =[]
    start, end = 31,30 # fist time interval is 31 to 30
    CPU_utl = []     # list to store CPU utilization in past 30 min
    for k in range(0,30):
        CPU = watch.get_metric_statistics(
                Namespace='AWS/EC2',  # namespace for Amazon EC2
                MetricName='CPUUtilization',  # The percentage of allocated EC2 compute units that are currently in use on the instance. 
                Dimensions=[   # get a specific instance in a multi-deimension instance group
                    {
                        'Name': 'InstanceId',
                        'Value': instance.id
                    },
                ],
                StartTime=datetime.utcnow() - timedelta(seconds=start * 60),  # The time stamp that determines the first data point to return
                EndTime=datetime.utcnow() - timedelta(seconds=end * 60),  # The time stamp that determines the last data point to return.
                Period=60,  # The granularity, in seconds, of the returned data points.
                Statistics=['Average']  # The metric statistics, other than percentile.
            )
        start -= 1 # time interval shifts by 1 min
        end -= 1
        utilization = 0 # used to hold the utilization of each 1 min time interval
        for data in CPU['Datapoints']:
            utilization = round(data['Average'],2) # round off the floating points, only keep last 2 digits
        CPU_utl.append(utilization)


    x_axis =list(range(1, 31)) # time intercal of 30 min, x-axis for CPU utilization chart
    return x_axis, CPU_utl  # return x-axis and y-axis for chart
    
    
# Terminate all workers and then stop the manager itself
def terminate_and_stop():
    ec2 = boto3.resource('ec2')
    instances = select_running_inst() # get all running workers
    id_to_remove = []
    for instance in instances:
        id_to_remove.append(instance.id) # collect IDs of all running workers
    
    # Deregister and terminate all running instance
    for id in id_to_remove:
        inst_remove(id)  

    # Stop the manager instance
    manager = select_manager()
    for instance in manager:
        instance.stop()        # Stop the manager instance
    # Waits until the instance is stopped
        instance.wait_until_stopped(
            Filters=[
                {
                    'Name': 'instance-id',
                    'Values': [instance.id]
                },
            ],
        )
        print('Manager instance:', instance.id, 'is stopped')

# Once the manager starts, it resizes the worker pool to 1
def resize_worker_pool():
    inst_id = []
    ec2 = boto3.resource('ec2')
    instances = select_running_inst() # Select all running workers
    for instance in instances:
        inst_id.append(instance.id) # IDs of all running workers
        
    if len(inst_id) > 1:
        remove_inst_num = len(inst_id) -1 # num of instances to be removed
        id_to_remove = inst_id[:remove_inst_num] # IDs of instances to be removed
        for id in id_to_remove:
                print('Terminating instance-ID:', id)
                ec2.instances.filter(InstanceIds=[id]).terminate() # Shuts down the specified instance
        print('Worker pool is resized to 1')
    elif len(inst_id ) == 1:
        print('Worker pool size is 1')
    else:
        create_new_instance()
        print('Worker pool is resized to 1')

       
# Get Load Balancer DNS name 
def ELB_DNS():
    elb = boto3.client('elbv2')
    # Describes the specified load balancers
    response = elb.describe_load_balancers(
        LoadBalancerArns=[config.ELB_ARN,],
    )
    LoadBalancers = response['LoadBalancers'] # get the dict
    DNS = LoadBalancers['DNSName'] # get the DNS name
    return DNS # return load balancer DNS name


# Return manager instance
def select_manager():
    ec2 = boto3.resource('ec2') # A resource representing Amazon Elastic Compute Cloud (EC2)
    # Find all running instances
    instances = ec2.instances.filter(
        Filters = [
            {'Name': 'placement-group-name',
           'Values': [config.manager_group]},

            {'Name': 'instance-state-name',
           'Values': ['running']},
        ]
    )
    return instances

# HTTP request rate of the worker in past 30 min, resolution is 1 min 
# def inst_HTTP(inst_id):
#     ec2 = boto3.resource('ec2')
#     instance = ec2.Instance(inst_id) # Identify the instance by ID
#     watch = boto3.client('cloudwatch') # A low-level client representing Amazon CloudWatch
    
#     start, end = 30,29 # fist time interval is 31 to 30
#     http_rate = []     # list to store HTTP request rate in past 30 min
#     new_uti =[]
#     for k in range(0,30):
#         HTTP = watch.get_metric_statistics(
#                 Namespace='AWS/EC2/API',  # namespace for Amazon EC2 & API
#                 MetricName='SuccessfulCalls',  # The number of successful API requests.
#                 Dimensions=[   # get a specific instance in a multi-deimension instance group
#                     {
#                         'Name': 'InstanceId',
#                         'Value': instance.id
#                     },
#                 ],
#                 StartTime=datetime.utcnow() - timedelta(seconds=start * 60),  # The time stamp that determines the first data point to return
#                 EndTime=datetime.utcnow() - timedelta(seconds=end * 60),  # The time stamp that determines the last data point to return.
#                 Period=60,  # The granularity, in seconds, of the returned data points.
#                 Statistics=['Sum']  # The metric statistics, other than percentile.
#             )
#         start -= 1 # time interval shifts by 1 min
#         end -= 1
#         http_count = 0 # used to hold the http request count in each 1 min time interval
#         for data in HTTP['Datapoints']:
#             http_count = float(data['Sum']) # save the count number as an integer
#         http_rate.append(float(http_count))



#     x_axis =list(range(1, 31)) # time intercal of 30 min, x-axis for CPU utilization chart
#     return x_axis, http_rate  # return x-axis and y-axis for chart


def average_CPU_uti(instances):
    
    CPU_utl= []  # list to save cpu utilization of all running workers
    instance_id = [] # save instance IDs of all running workers
    
    # loop through all instances in worker group
    for instance in instances:
        instance_id.append(instance.id)
        watch = boto3.client('cloudwatch') # A low-level client representing Amazon CloudWatch
        
        # CPU utilization in 2 min
        CPU = watch.get_metric_statistics(
            Namespace='AWS/EC2',  # namespace for Amazon EC2
            MetricName='CPUUtilization',  # The percentage of allocated EC2 compute units that are currently in use on the instance. 
            Dimensions=[   # get a specific instance in a multi-deimension instance group
                {
                    'Name': 'InstanceId',
                    'Value': instance.id
                },
            ],
             StartTime=datetime.utcnow() - timedelta(seconds=2 * 60),  # The time stamp that determines the first data point to return
             EndTime=datetime.utcnow() - timedelta(seconds=0 * 60),  # The time stamp that determines the last data point to return.
             Period=60,  # The granularity, in seconds, of the returned data points.
             Statistics=['Average']  # The metric statistics, other than percentile.
        )
        
        # gather all CPU average utilization 
        for data in CPU['Datapoints']:
            utilization = round(data['Average'],2) # round off the floating points, only keep last 2 digits
            CPU_utl.append(utilization)
            
    average_uti = sum(CPU_utl)/len(instance_id) # get average CPU utilizaion in worker group
    print('List of CPU utilization from all running instances: ', CPU_utl)
    print('Average CPU utilization for entire worker group: ', average_uti)
    print('Running instance IDs: ', instance_id)
    return instance_id, average_uti



def full_load_check(instance_id):
    if len(instance_id) == 10:  # Full load alert 
        print('Worker pool is fully loaded!', len(instance_id), 'instances are running.')
        
    elif len(instance_id) == 1:
        print('Worker pool reached minimum size! only ', len(instance_id), 'instances are running.')


# instance creation function for auto-sacling       
def create_new_instance_auto():
    ec2 = boto3.resource('ec2') # A resource representing Amazon Elastic Compute Cloud (EC2)
    instances = select_running_inst() # Select all running workers
    
    # Create a new worker instance 
    instance = ec2.create_instances(
        ImageId=config.image_id,   # The ID of the AMI
        InstanceType='t2.small',  # T2 small instance
        KeyName=config.key_pair,  # The name of the key pair
        MinCount=1,  # The maximum number of instances to launch
        MaxCount=1,  # The minimum number of instances to launch
        Monitoring= {'Enabled': True}, # Indicates detailed monitoring is enabled
        Placement={'AvailabilityZone': 'us-east-1b', 
                    'GroupName': config.placement_group, } ,# US East (N. Virginia)
        SecurityGroups=[config.security_group,],  # Name of the Security group
        UserData=config.user_data,
        TagSpecifications=[
            {
                'ResourceType': 'instance',  # The type of resource to tag
                'Tags':[
                    {
                        'Key': 'Name',
                        'Value': 'auto_add_worker' # Tag this worker is added manually
                    },
                ]
            },
        ]
    )
    instance = instance[0] # only one instance contained in the list(linstance)
    print('New instance',instance,' is added.')
    # Waits until the instance is running
    instance.wait_until_running( 
                Filters=[
                    {
                        'Name': 'instance-id',
                        'Values': [instance.id]
                    },
                ],
            )
    print('New Instance', instance,' is running')
    # register the new instance to ELB target group
    elb = boto3.client('elbv2')  # client represnting the Elastic Load Balancer
                                         # elb is to support classic elb, elbv2 is for application elb
    print('Registering the new instance to ELB target group')
    elb.register_targets( # registers the specific targets with the specific target group
        TargetGroupArn=config.ARN, # The Amazon Resource Name of the target group
        Targets=[
            {
                'Id': instance.id,  # ID of the target (instance) to register
            },
        ]
    )
    
    # Waiting for complete registering
    # Describe the health of specified targets until a successful state is reached
    waiter = elb.get_waiter('target_in_service') # return an object that can wait for some condition
    waiter.wait(
        TargetGroupArn=config.ARN, # The Amazon Resource Name of the target group
        Targets=[
            {
                'Id': instance.id,  # ID of the target (instance)  
            },
        ],
    ) # Up to now, a new created instance is running and successfully registed in ELB target group
    print('New instance ', instance.id, 'is registered')



# HTTP request rate of the worker in past 30 min, resolution is 1 min 
def inst_HTTP(inst_id):
    ec2 = boto3.resource('ec2')
    instance = ec2.Instance(inst_id) # Identify the instance by ID
    watch = boto3.client('cloudwatch') # A low-level client representing Amazon CloudWatch
    
    start, end = 30,29 # fist time interval is 31 to 30
    http_rate = []     # list to store HTTP request rate in past 30 min
    for k in range(0,30):
        HTTP = watch.get_metric_statistics(
                Namespace='AWS/ApplicationELB',  # namespace 
                MetricName='RequestCountPerTarget',  # The average number of requests received by each target in a target group.
                Dimensions=[   # get a specific target group
                    {
                        'Name': 'TargetGroup',
                        'Value': config.target_group_dimension
                    },
                ],
                StartTime=datetime.utcnow() - timedelta(seconds=start * 60),  # The time stamp that determines the first data point to return
                EndTime=datetime.utcnow() - timedelta(seconds=end * 60),  # The time stamp that determines the last data point to return.
                Period=60,  # The granularity, in seconds, of the returned data points.
                Statistics=['Sum']  # The metric statistics, other than percentile.
        )
        start -= 1 # time interval shifts by 1 min
        end -= 1
        http_count = 0 # used to hold the http request count in each 1 min time interval
        for data in HTTP['Datapoints']:
            http_count = int(data['Sum']) # save the count number as an integer
        http_rate.append(http_count)
        
        x_axis =list(range(1, 31)) # time intercal of 30 min, x-axis for http request rate chart
    return x_axis, http_rate  # return x-axis and y-axis for chart


# count the  number of instances in past 30 minutes
def get_poolsize_laod():
    
    ec2 = boto3.resource('ec2')
    watch = boto3.client('cloudwatch') # A low-level client representing Amazon CloudWatch
    
    start, end = 11,10 # fist time interval is 11 to 10
    inst_num = []     # list to store HTTP request rate in past 10 min
    CPU_utl = []     # list to store CPU utilization in past 10 min
    new_uti1 =[]
    new_uti2 =[]
    for k in range(0,10):
        HOST = watch.get_metric_statistics(
                Namespace='AWS/ApplicationELB',  # namespace 
                MetricName='HealthyHostCount',  # 	The number of targets that are considered healthy
                Dimensions=[   # get a specific target group
                    {
                        'Name': 'TargetGroup',
                        'Value': config.target_group_dimension
                    },
                    {
                        'Name': 'LoadBalancer',
                        'Value': config.ELB_demension
                    }
                ],
                StartTime=datetime.utcnow() - timedelta(seconds=start * 60),  # The time stamp that determines the first data point to return
                EndTime=datetime.utcnow() - timedelta(seconds=end * 60),  # The time stamp that determines the last data point to return.
                Period=60,  # The granularity, in seconds, of the returned data points.
                Statistics=['Average']  # The metric statistics, other than percentile.
            )
        
        CPU = watch.get_metric_statistics(
            Namespace='AWS/EC2',  # namespace for Amazon EC2
            MetricName='CPUUtilization',  # The percentage of allocated EC2 compute units that are currently in use on the instance. 
            Dimensions=[   # get a specific instance in a multi-deimension instance group
                {
                    'Name': 'ImageId',
                    'Value': config.image_id
                },
            ],
            StartTime=datetime.utcnow() - timedelta(seconds=start * 60),  # The time stamp that determines the first data point to return
            EndTime=datetime.utcnow() - timedelta(seconds=end * 60),  # The time stamp that determines the last data point to return.
            Period=60,  # The granularity, in seconds, of the returned data points.
            Statistics=['Average']  # The metric statistics, other than percentile.
        )
        
        # used to hold the number of running instances in each 1 min time interval
        for data in HOST['Datapoints']:
            inst_count = int(data['Average']) # save the count number as an integer
            inst_num.append(inst_count)
        
        # gather all CPU average utilization 
        for data in CPU['Datapoints']:
            utilization = round(data['Average'],2) # round off the floating points, only keep last 2 digits
            CPU_utl.append(utilization)
        
        # CPU_utl[k] = CPU_utl[k]/inst_num[k] # get the average CPU utilization for all running workers
        start -= 1 # time interval shifts by 1 min
        end -= 1

        
    x_axis =list(range(1, 11)) # time intercal of 10 min, x-axis for http request rate chart
    print("lennnnnnnnnxxxxxxxxxx", str(len(inst_num)),"bbbbbbbbb",inst_num, "aaaaaaaaaaa",CPU_utl)

    return x_axis, inst_num, CPU_utl  # return x-axis and y-axis for chart