import boto3
import time
from datetime import datetime, timedelta
import config# load base image-ID, key pair name, manager instance-ID, etc...
from manager import select_running_inst, create_new_instance_auto, inst_remove, average_CPU_uti, full_load_check

threshold_max = 30  # maximum CUP utilization per worker
threshold_min = 10  # minimum CUP utilization per worker
ratio_expand = 1.25 # ratio to expand the worker pool
ratio_shrink = 0.75 # ratio to shrink the worker pool

# ref for CPU utilization: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html

# loop to check the average CUP utilization every 1 minute    
def hanlder():
    print("auto scalling activated")
    ec2 = boto3.resource('ec2') # bulid coonnection to ec2 instance
    instances = select_running_inst() # get all running workers, return as a instances collection: list(instance)
    
    instance_id, average_uti = average_CPU_uti(instances) # return IDs of all running instances and the average CPU utilization
    print('Average CPU utilization is: ', average_uti)
    full_load_check(instance_id) # load checking, full load is 10 workers, minimum load is 1 worker
    # average_uti = 40
    # Case #1, Avergae CPU > maximum threshold value, add more instances
    if average_uti > threshold_max and len(instance_id) < 10: # The maximum size of the worker pool is 10
        new_inst_num = int(len(instance_id)*(float(ratio_expand)-1)+1)  # number of new instances to create
        
        if (len(instance_id) + new_inst_num) > 10: # limit the maximum num of workers to 10
            new_inst_num = 10 - len(instance_id)
        print('Auto adding ', new_inst_num, 'new instances')
        
        # Create more instances
        for i in range(new_inst_num):
            instance = create_new_instance_auto() # create a new instance and register to the target group
              
    # Case #2, Avergae CPU < minimum threshold value, reduce instance(s)
    if average_uti < threshold_min and len(instance_id) > 1:
        remove_inst_num = int(len(instance_id)*(1-float(ratio_shrink))+1)  # number of instances to be removed
        print('Auto terminating ', remove_inst_num, 'instances')
        
        if len(instance_id) - int(remove_inst_num) == 0:
            remove_inst_num = 1

        
        if remove_inst_num > 0 and (len(instance_id) - remove_inst_num) >= 1:  # minimum size of the worker pool is 1
            id_to_remove = instance_id[:remove_inst_num]
            print('IDs of the instances to be removed: ', id_to_remove)
            
            # Terminate and deregister the instance(s)
            for id in id_to_remove:
                inst_remove(id)
            
    # Sleep for 1 min, the period of CPU utilization checking is 1 minute
    # time.sleep(60)

def CustimizedHandler(thre_max, thre_min, ratio_exp, ratio_shi):
    threshold_max = thre_max  # maximum CUP utilization per worker
    threshold_min = thre_min  # minimum CUP utilization per worker
    ratio_expand = ratio_exp # ratio to expand the worker pool
    ratio_shrink = ratio_shi # ratio to shrink the worker pool
    print("NEW customized auto scalling activated", "treshold_max is ", str(thre_max), "treshold_min is ", str(thre_min), "ratio_expand is ", str(ratio_expand), "ratio_shrink is", str(ratio_shrink))
    ec2 = boto3.resource('ec2') # bulid coonnection to ec2 instance
    instances = select_running_inst() # get all running workers, return as a instances collection: list(instance)
    
    instance_id, average_uti = average_CPU_uti(instances) # return IDs of all running instances and the average CPU utilization
    print('Average CPU utilization is: ', average_uti)
    # average_uti = 40
    full_load_check(instance_id) # load checking, full load is 10 workers, minimum load is 1 worker

    # Case #1, Avergae CPU > maximum threshold value, add more instances
    if float(average_uti) > float(threshold_max) and len(instance_id) < 10: # The maximum size of the worker pool is 10
        # print("its greaterrrr anddddddddd", str(threshold_max))
        new_inst_num = int(len(instance_id)*(float(ratio_expand)-1)+1)  # number of new instances to create
        # print("new instance nummmmmm ", new_inst_num)
        if (len(instance_id) + new_inst_num) > 10: # limit the maximum num of workers to 10
            new_inst_num = 10 - len(instance_id)
        time.sleep(1)
        # print("new instance222222222222 nummmmmm ", new_inst_num)
        print('Auto adding ', new_inst_num, 'new instances')
        
        # Create more instances
        for i in range(new_inst_num):
            instance = create_new_instance_auto() # create a new instance and register to the target group
              
    # Case #2, Avergae CPU < minimum threshold value, reduce instance(s)
    if float(average_uti) < float(threshold_min) and len(instance_id) > 1:
        remove_inst_num = int(len(instance_id)*(1-float(ratio_shrink))+1)  # number of instances to be removed
        print('Auto terminating ', remove_inst_num, 'instances')
        if len(instance_id) - int(remove_inst_num) == 0:
            remove_inst_num = 1

        
        if remove_inst_num > 0 and (len(instance_id) - remove_inst_num) >= 1:  # minimum size of the worker pool is 1
            instance_id.reverse()
            id_to_remove = instance_id[:remove_inst_num]
            print('IDs of the instances to be removed: ', id_to_remove)
            
            # Terminate and deregister the instance(s)
            for id in id_to_remove:
                inst_remove(id)
    # Sleep for 1 min, the period of CPU utilization checking is 1 minute
    # time.sleep(60)